"""故障检测器模块

实现各种故障检测算法，包括统计检测器和变化点检测器。
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import numpy as np

from myeap.fdc.models import DetectionResult

logger = logging.getLogger(__name__)


class FaultDetector(ABC):
    """故障检测器基类

    所有故障检测器必须继承此类并实现detect和update_baseline方法。

    Example:
        detector = StatisticalDetector(z_threshold=3.0)
        result = detector.detect(data, baseline)
    """

    @abstractmethod
    def detect(
        self, data: np.ndarray, baseline: Optional[np.ndarray] = None
    ) -> DetectionResult:
        """检测故障

        Args:
            data: 待检测的时间序列数据
            baseline: 基线数据（可选）

        Returns:
            DetectionResult: 检测结果
        """
        pass

    @abstractmethod
    def update_baseline(self, data: np.ndarray) -> None:
        """更新基线

        Args:
            data: 用于更新基线的数据
        """
        pass

    def reset(self) -> None:
        """重置检测器状态"""
        pass


class StatisticalDetector(FaultDetector):
    """统计故障检测器

    基于统计方法的故障检测：
    - Z-score检测：检测偏离基线的异常点
    - 使用移动窗口维护基线统计信息

    Attributes:
        z_threshold: Z-score阈值，超过此值视为异常
        window_size: 移动窗口大小
    """

    def __init__(self, z_threshold: float = 3.0, window_size: int = 100):
        """初始化统计检测器

        Args:
            z_threshold: Z-score阈值（默认3.0）
            window_size: 移动窗口大小（默认100）
        """
        self.z_threshold = z_threshold
        self.window_size = window_size
        self.baseline_mean: Optional[float] = None
        self.baseline_std: Optional[float] = None
        self._history: List[float] = []

    def detect(
        self, data: np.ndarray, baseline: Optional[np.ndarray] = None
    ) -> DetectionResult:
        """使用Z-score方法检测异常

        Args:
            data: 待检测的时间序列数据
            baseline: 基线数据（可选）

        Returns:
            DetectionResult: 检测结果
        """
        if baseline is not None:
            self.update_baseline(baseline)

        if self.baseline_mean is None or self.baseline_std is None:
            return DetectionResult(is_anomaly=False, score=0.0)

        # 计算Z-score
        z_scores = np.abs((data - self.baseline_mean) / (self.baseline_std + 1e-10))
        max_z = float(np.max(z_scores))

        is_anomaly = max_z > self.z_threshold
        score = min(max_z / self.z_threshold, 1.0) if is_anomaly else 0.0

        # 找出异常点索引
        anomaly_indices = np.where(z_scores > self.z_threshold)[0].tolist()

        return DetectionResult(
            is_anomaly=bool(is_anomaly),
            score=float(score),
            z_scores=z_scores.tolist(),
            anomaly_indices=anomaly_indices,
        )

    def update_baseline(self, data: np.ndarray) -> None:
        """更新基线统计信息

        使用移动窗口更新基线。

        Args:
            data: 用于更新基线的数据
        """
        self._history.extend(data.tolist() if hasattr(data, "tolist") else list(data))

        # 保持历史记录在窗口大小内
        if len(self._history) > self.window_size * 2:
            self._history = self._history[-self.window_size * 2 :]

        # 使用移动窗口更新基线
        if len(data) >= self.window_size:
            self.baseline_mean = float(np.mean(data[-self.window_size :]))
            self.baseline_std = float(np.std(data[-self.window_size :]))
        else:
            self.baseline_mean = float(np.mean(data))
            self.baseline_std = float(np.std(data))

    def reset(self) -> None:
        """重置检测器状态"""
        self.baseline_mean = None
        self.baseline_std = None
        self._history.clear()


class ChangePointDetector(FaultDetector):
    """变化点检测器

    使用CUSUM和Page-Hinkley算法检测数据中的突变点。

    Attributes:
        threshold: 检测阈值
        drift: 漂移参数
        min_samples: 最小样本数
    """

    def __init__(
        self,
        threshold: float = 5.0,
        drift: float = 0.5,
        min_samples: int = 30,
    ):
        """初始化变化点检测器

        Args:
            threshold: 检测阈值（默认5.0）
            drift: 漂移参数（默认0.5）
            min_samples: 最小样本数（默认30）
        """
        self.threshold = threshold
        self.drift = drift
        self.min_samples = min_samples

        self.cusum_pos = 0.0
        self.cusum_neg = 0.0
        self.mean = 0.0
        self.sample_count = 0
        self.change_points: List[int] = []

    def detect(
        self, data: np.ndarray, baseline: Optional[np.ndarray] = None
    ) -> DetectionResult:
        """检测数据中的变化点

        Args:
            data: 待检测的时间序列数据
            baseline: 基线数据（可选）

        Returns:
            DetectionResult: 检测结果
        """
        if baseline is not None:
            self._init_from_baseline(baseline)

        if self.sample_count < self.min_samples:
            return DetectionResult(is_anomaly=False, score=0.0)

        # 逐点检测
        change_detected = False
        max_score = 0.0
        change_point_index = None

        for i, value in enumerate(data):
            # 更新均值估计
            self.sample_count += 1
            delta = value - self.mean
            self.mean += delta / self.sample_count

            # CUSUM检测
            self.cusum_pos = max(0, self.cusum_pos + value - self.mean - self.drift)
            self.cusum_neg = max(0, self.cusum_neg - value + self.mean - self.drift)

            cusum_score = max(self.cusum_pos, self.cusum_neg) / self.threshold

            if cusum_score > max_score:
                max_score = cusum_score

            if cusum_score >= 1.0:
                change_detected = True
                change_point_index = i
                self.change_points.append(i)
                self.cusum_pos = 0.0
                self.cusum_neg = 0.0

        return DetectionResult(
            is_anomaly=change_detected,
            score=min(max_score, 1.0),
            change_point_index=change_point_index,
        )

    def update_baseline(self, data: np.ndarray) -> None:
        """更新基线

        Args:
            data: 用于更新基线的数据
        """
        self._init_from_baseline(data)

    def _init_from_baseline(self, baseline: np.ndarray) -> None:
        """从基线数据初始化

        Args:
            baseline: 基线数据
        """
        self.mean = float(np.mean(baseline))
        self.sample_count = len(baseline)
        self.cusum_pos = 0.0
        self.cusum_neg = 0.0

    def reset(self) -> None:
        """重置检测器状态"""
        self.cusum_pos = 0.0
        self.cusum_neg = 0.0
        self.mean = 0.0
        self.sample_count = 0
        self.change_points.clear()


class IsolationDetector(FaultDetector):
    """隔离度检测器

    基于隔离森林思想的异常检测算法。

    Attributes:
        n_estimators: 树的数量
        max_samples: 最大样本数
        contamination: 污染比例
    """

    def __init__(
        self,
        n_estimators: int = 100,
        max_samples: int = 256,
        contamination: float = 0.1,
    ):
        """初始化隔离度检测器

        Args:
            n_estimators: 树的数量（默认100）
            max_samples: 最大样本数（默认256）
            contamination: 污染比例（默认0.1）
        """
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.contamination = contamination
        self._trees: List[Dict[str, Any]] = []
        self._is_fitted = False

    def fit(self, data: np.ndarray) -> None:
        """训练检测器

        Args:
            data: 训练数据
        """
        self._build_trees(data)
        self._is_fitted = True

    def detect(
        self, data: np.ndarray, baseline: Optional[np.ndarray] = None
    ) -> DetectionResult:
        """检测异常

        Args:
            data: 待检测的时间序列数据
            baseline: 基线数据（可选）

        Returns:
            DetectionResult: 检测结果
        """
        if not self._is_fitted:
            if baseline is not None:
                self.fit(baseline)
            else:
                return DetectionResult(is_anomaly=False, score=0.0)

        # 计算异常分数
        scores = self._compute_anomaly_scores(data)
        max_score = float(np.max(scores))

        # 根据污染比例确定阈值
        threshold = np.percentile(scores, (1 - self.contamination) * 100)

        is_anomaly = max_score > threshold
        score = min(max_score / (threshold + 1e-10), 1.0) if is_anomaly else 0.0

        return DetectionResult(
            is_anomaly=bool(is_anomaly),
            score=float(score),
            anomaly_indices=np.where(scores > threshold)[0].tolist(),
        )

    def update_baseline(self, data: np.ndarray) -> None:
        """更新基线

        Args:
            data: 用于更新基线的数据
        """
        self.fit(data)

    def _build_trees(self, data: np.ndarray) -> None:
        """构建隔离树

        Args:
            data: 训练数据
        """
        self._trees.clear()

        # 采样数据
        n_samples = min(len(data), self.max_samples)
        indices = np.random.choice(len(data), n_samples, replace=False)
        samples = data[indices]

        for _ in range(self.n_estimators):
            tree = self._build_isolation_tree(samples)
            self._trees.append(tree)

    def _build_isolation_tree(self, data: np.ndarray) -> Dict[str, Any]:
        """构建单棵隔离树

        Args:
            data: 数据

        Returns:
            Dict: 树结构
        """
        if len(data) <= 1 or self._tree_depth >= 10:
            return {"leaf": True, "size": len(data)}

        # 随机选择特征和分割点
        feature_idx = np.random.randint(0, data.shape[1])
        max_val = float(np.max(data[:, feature_idx]))
        min_val = float(np.min(data[:, feature_idx]))

        if max_val == min_val:
            return {"leaf": True, "size": len(data)}

        split_val = float(np.random.uniform(min_val, max_val))

        # 分割数据
        left_mask = data[:, feature_idx] < split_val
        right_mask = ~left_mask

        return {
            "leaf": False,
            "feature_idx": feature_idx,
            "split_val": split_val,
            "left": self._build_isolation_tree(data[left_mask])
            if np.any(left_mask)
            else {"leaf": True, "size": 0},
            "right": self._build_isolation_tree(data[right_mask])
            if np.any(right_mask)
            else {"leaf": True, "size": 0},
        }

    _tree_depth = 0

    def _compute_path_length(self, point: np.ndarray, tree: Dict) -> int:
        """计算点到叶节点的路径长度

        Args:
            point: 数据点
            tree: 树节点

        Returns:
            int: 路径长度
        """
        if tree.get("leaf", False):
            return tree.get("size", 1)

        feature_idx = tree["feature_idx"]
        split_val = tree["split_val"]

        if point[feature_idx] < split_val:
            return 1 + self._compute_path_length(point, tree["left"])
        else:
            return 1 + self._compute_path_length(point, tree["right"])

    def _compute_anomaly_scores(self, data: np.ndarray) -> np.ndarray:
        """计算异常分数

        Args:
            data: 数据

        Returns:
            np.ndarray: 异常分数
        """
        scores = np.zeros(len(data))

        for point in data:
            path_lengths = []
            for tree in self._trees:
                length = self._compute_path_length(point, tree)
                path_lengths.append(length)

            # 计算异常分数
            avg_length = np.mean(path_lengths)
            c = 2 * (np.log(self.max_samples - 1) + 0.5772156649) - (
                2 * (self.max_samples - 1) / self.max_samples
            )
            score = 2 ** (-avg_length / c)
            scores[np.where(np.all(data == point, axis=1))[0][0]] = score

        return scores

    def reset(self) -> None:
        """重置检测器状态"""
        self._trees.clear()
        self._is_fitted = False


class TrendDetector(FaultDetector):
    """趋势检测器

    检测数据中的趋势变化，用于识别漂移型故障。

    Attributes:
        slope_threshold: 斜率阈值
        window_size: 窗口大小
    """

    def __init__(
        self,
        slope_threshold: float = 0.1,
        window_size: int = 50,
        r_squared_threshold: float = 0.8,
    ):
        """初始化趋势检测器

        Args:
            slope_threshold: 斜率阈值（默认0.1）
            window_size: 窗口大小（默认50）
            r_squared_threshold: 决定系数阈值（默认0.8）
        """
        self.slope_threshold = slope_threshold
        self.window_size = window_size
        self.r_squared_threshold = r_squared_threshold
        self.baseline_slope = 0.0
        self.baseline_intercept = 0.0

    def detect(
        self, data: np.ndarray, baseline: Optional[np.ndarray] = None
    ) -> DetectionResult:
        """检测趋势变化

        Args:
            data: 待检测的时间序列数据
            baseline: 基线数据（可选）

        Returns:
            DetectionResult: 检测结果
        """
        if len(data) < self.window_size:
            return DetectionResult(is_anomaly=False, score=0.0)

        # 计算当前数据的趋势
        x = np.arange(len(data))
        try:
            from scipy import stats

            slope, intercept, r_value, _, _ = stats.linregress(x, data)
            r_squared = float(r_value**2)
        except Exception:
            return DetectionResult(is_anomaly=False, score=0.0)

        # 如果有基线，比较趋势变化
        if baseline is not None and len(baseline) >= self.window_size:
            x_base = np.arange(len(baseline))
            try:
                base_slope, _, base_r_value, _, _ = stats.linregress(x_base, baseline)
                slope_diff = abs(slope - base_slope)
            except Exception:
                slope_diff = abs(slope)
        else:
            slope_diff = abs(slope)

        # 检测趋势异常
        is_anomaly = slope_diff > self.slope_threshold and r_squared > self.r_squared_threshold
        score = min(slope_diff / self.slope_threshold, 1.0) if is_anomaly else 0.0

        return DetectionResult(
            is_anomaly=bool(is_anomaly),
            score=float(score),
        )

    def update_baseline(self, data: np.ndarray) -> None:
        """更新基线趋势

        Args:
            data: 基线数据
        """
        if len(data) >= self.window_size:
            x = np.arange(len(data))
            try:
                from scipy import stats

                self.baseline_slope, self.baseline_intercept, _, _, _ = stats.linregress(
                    x, data[-self.window_size :]
                )
            except Exception:
                pass


class CompositeDetector(FaultDetector):
    """组合检测器

    组合多个检测器进行综合判断。

    Attributes:
        detectors: 检测器列表
        weights: 各检测器的权重
        fusion_method: 融合方法 ("and", "or", "weighted")
    """

    def __init__(
        self,
        detectors: Optional[List[FaultDetector]] = None,
        weights: Optional[List[float]] = None,
        fusion_method: str = "weighted",
    ):
        """初始化组合检测器

        Args:
            detectors: 检测器列表
            weights: 各检测器的权重
            fusion_method: 融合方法 ("and", "or", "weighted")
        """
        self.detectors = detectors or []
        self.weights = weights or [1.0] * len(self.detectors)
        self.fusion_method = fusion_method

        # 归一化权重
        total_weight = sum(self.weights)
        if total_weight > 0:
            self.weights = [w / total_weight for w in self.weights]

    def add_detector(self, detector: FaultDetector, weight: float = 1.0) -> None:
        """添加检测器

        Args:
            detector: 检测器实例
            weight: 权重
        """
        self.detectors.append(detector)
        self.weights.append(weight)

        # 重新归一化权重
        total_weight = sum(self.weights)
        self.weights = [w / total_weight for w in self.weights]

    def detect(
        self, data: np.ndarray, baseline: Optional[np.ndarray] = None
    ) -> DetectionResult:
        """组合检测

        Args:
            data: 待检测的时间序列数据
            baseline: 基线数据（可选）

        Returns:
            DetectionResult: 组合后的检测结果
        """
        if not self.detectors:
            return DetectionResult(is_anomaly=False, score=0.0)

        results = [detector.detect(data, baseline) for detector in self.detectors]

        if self.fusion_method == "and":
            is_anomaly = all(r.is_anomaly for r in results)
            score = min([r.score for r in results]) if is_anomaly else 0.0
        elif self.fusion_method == "or":
            is_anomaly = any(r.is_anomaly for r in results)
            score = max([r.score for r in results])
        else:  # weighted
            is_anomaly = any(r.is_anomaly for r in results)
            score = sum(r.score * w for r, w in zip(results, self.weights))

        return DetectionResult(
            is_anomaly=bool(is_anomaly),
            score=float(score),
        )

    def update_baseline(self, data: np.ndarray) -> None:
        """更新所有检测器的基线

        Args:
            data: 基线数据
        """
        for detector in self.detectors:
            detector.update_baseline(data)

    def reset(self) -> None:
        """重置所有检测器"""
        for detector in self.detectors:
            detector.reset()
