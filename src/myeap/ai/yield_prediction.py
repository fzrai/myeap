"""良率预测模块

基于工艺参数预测批次良率。

主要功能：
- 基于统计回归的良率预测
- 特征重要性分析
- 预测置信区间计算

Example:
    >>> import numpy as np
    >>> from myeap.ai.yield_prediction import YieldPredictor
    >>> yp = YieldPredictor()
    >>> yp.add_process_parameter("temperature", 150.0, target=150, tol=5)
    >>> result = yp.predict_yield("batch-001", {"temperature": 152.0})
"""

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional, Tuple

import numpy as np

from myeap.ai.models import (
    PredictionConfidence,
    ProcessParameter,
    TrainingResult,
    YieldPrediction,
    AnalysisStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class FeatureImportance:
    """特征重要性

    表示工艺参数对良率的影响程度。

    Attributes:
        parameter_name: 参数名称
        importance_score: 重要性分数
        correlation: 与良率的相关系数
        optimal_range: 最优范围 (min, max)
    """

    parameter_name: str
    importance_score: float
    correlation: float = 0.0
    optimal_range: Optional[Tuple[float, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "parameter_name": self.parameter_name,
            "importance_score": self.importance_score,
            "correlation": self.correlation,
            "optimal_range": list(self.optimal_range) if self.optimal_range else None,
        }


@dataclass
class BatchYieldRecord:
    """批次良率记录

    记录单个批次的工艺参数和良率结果。

    Attributes:
        batch_id: 批次标识
        yield_rate: 实际良率
        process_params: 工艺参数值
        timestamp: 生产时间
        product_type: 产品类型
    """

    batch_id: str
    yield_rate: float
    process_params: Dict[str, float] = field(default_factory=dict)
    timestamp: Optional[datetime] = None
    product_type: str = ""

    def to_feature_array(self, param_order: List[str]) -> np.ndarray:
        """转换为特征数组

        Args:
            param_order: 参数顺序列表

        Returns:
            np.ndarray: 特征数组
        """
        values = [self.process_params.get(p, 0.0) for p in param_order]
        return np.array(values)


def get_default_process_parameters() -> List[ProcessParameter]:
    """获取默认工艺参数列表

    返回半导体制造业中常见的工艺参数。

    Returns:
        List[ProcessParameter]: 默认工艺参数列表
    """
    return [
        ProcessParameter(name="temperature", value=0, unit="C", target=150, tolerance_upper=5, tolerance_lower=5),
        ProcessParameter(name="pressure", value=0, unit="mTorr", target=100, tolerance_upper=10, tolerance_lower=10),
        ProcessParameter(name="rf_power", value=0, unit="W", target=500, tolerance_upper=25, tolerance_lower=25),
        ProcessParameter(name="gas_flow", value=0, unit="sccm", target=200, tolerance_upper=10, tolerance_lower=10),
        ProcessParameter(name="process_time", value=0, unit="s", target=60, tolerance_upper=2, tolerance_lower=2),
    ]


class YieldPredictor:
    """良率预测器

    基于工艺参数的统计回归模型预测批次良率。

    Attributes:
        min_samples: 最少训练样本数
        confidence_width: 置信区间宽度因子

    Example:
        >>> yp = YieldPredictor()
        >>> yp.add_yield_record("batch-001", 0.95, {"temp": 150, "pressure": 100})
        >>> result = yp.predict_yield("batch-002", {"temp": 152, "pressure": 102})
    """

    def __init__(self, min_samples: int = 10, confidence_width: float = 0.05):
        """初始化良率预测器

        Args:
            min_samples: 最少训练样本数
            confidence_width: 置信区间宽度因子
        """
        self.min_samples = min_samples
        self.confidence_width = confidence_width

        # 工艺参数定义
        self._parameters: Dict[str, ProcessParameter] = {}

        # 历史良率记录
        self._yield_records: List[BatchYieldRecord] = []

        # 回归系数
        self._coefficients: Optional[np.ndarray] = None
        self._intercept: float = 0.0

        # 参数顺序（用于特征向量构建）
        self._param_order: List[str] = []

        # 特征重要性
        self._feature_importance: Dict[str, FeatureImportance] = {}

        # 性能指标
        self._r_squared: float = 0.0
        self._rmse: float = 0.0

    def add_process_parameter(
        self,
        name: str,
        value: float,
        target: Optional[float] = None,
        unit: str = "",
        tolerance_upper: Optional[float] = None,
        tolerance_lower: Optional[float] = None,
        importance: float = 1.0,
    ) -> ProcessParameter:
        """添加或更新工艺参数定义

        Args:
            name: 参数名称
            value: 当前值
            target: 目标值
            unit: 单位
            tolerance_upper: 上公差
            tolerance_lower: 下公差
            importance: 重要性权重

        Returns:
            ProcessParameter: 工艺参数对象
        """
        param = ProcessParameter(
            name=name,
            value=value,
            unit=unit,
            target=target,
            tolerance_upper=tolerance_upper,
            tolerance_lower=tolerance_lower,
            importance=importance,
        )
        self._parameters[name] = param
        if name not in self._param_order:
            self._param_order.append(name)
        return param

    def remove_process_parameter(self, name: str) -> bool:
        """移除工艺参数

        Args:
            name: 参数名称

        Returns:
            bool: 是否成功移除
        """
        if name in self._parameters:
            del self._parameters[name]
            if name in self._param_order:
                self._param_order.remove(name)
            return True
        return False

    def add_yield_record(
        self,
        batch_id: str,
        yield_rate: float,
        process_params: Dict[str, float],
        timestamp: Optional[datetime] = None,
        product_type: str = "",
    ) -> BatchYieldRecord:
        """添加良率记录

        Args:
            batch_id: 批次标识
            yield_rate: 实际良率 (0-1)
            process_params: 工艺参数值字典
            timestamp: 时间戳
            product_type: 产品类型

        Returns:
            BatchYieldRecord: 良率记录
        """
        record = BatchYieldRecord(
            batch_id=batch_id,
            yield_rate=float(np.clip(yield_rate, 0.0, 1.0)),
            process_params=process_params,
            timestamp=timestamp or datetime.now(),
            product_type=product_type,
        )
        self._yield_records.append(record)

        # 动态更新参数顺序
        for key in process_params:
            if key not in self._param_order:
                self._param_order.append(key)

        logger.debug(f"Added yield record for batch {batch_id}: {yield_rate:.2%}")
        return record

    def add_batch_records(self, records: List[BatchYieldRecord]) -> None:
        """批量添加良率记录

        Args:
            records: 良率记录列表
        """
        for record in records:
            self._yield_records.append(record)
            for key in record.process_params:
                if key not in self._param_order:
                    self._param_order.append(key)

    def train(self) -> TrainingResult:
        """训练良率预测模型

        使用历史数据训练线性回归模型。

        Returns:
            TrainingResult: 训练结果
        """
        import time

        start_time = time.time()

        if len(self._yield_records) < self.min_samples:
            return TrainingResult(
                model_name="yield_predictor",
                status=AnalysisStatus.FAILED,
                metrics={"error": f"需要至少{self.min_samples}个样本，当前仅{len(self._yield_records)}个"},
                data_points_count=len(self._yield_records),
            )

        # 构建特征矩阵
        if not self._param_order:
            return TrainingResult(
                model_name="yield_predictor",
                status=AnalysisStatus.FAILED,
                metrics={"error": "没有定义工艺参数"},
                data_points_count=len(self._yield_records),
            )

        X_list = []
        y_list = []

        for record in self._yield_records:
            try:
                features = record.to_feature_array(self._param_order)
                X_list.append(features)
                y_list.append(record.yield_rate)
            except (KeyError, ValueError):
                continue

        if len(X_list) < self.min_samples:
            return TrainingResult(
                model_name="yield_predictor",
                status=AnalysisStatus.FAILED,
                metrics={"error": "有效样本不足"},
                data_points_count=len(X_list),
            )

        X = np.array(X_list)
        y = np.array(y_list)

        # 添加截距项
        X_with_bias = np.column_stack([np.ones(len(X)), X])

        # 最小二乘法求解
        try:
            theta = np.linalg.lstsq(X_with_bias, y, rcond=None)[0]
            self._intercept = float(theta[0])
            self._coefficients = theta[1:]
        except np.linalg.LinAlgError:
            return TrainingResult(
                model_name="yield_predictor",
                status=AnalysisStatus.FAILED,
                metrics={"error": "矩阵求解失败"},
                data_points_count=len(X_list),
            )

        # 计算性能指标
        y_pred = X_with_bias @ theta
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        self._r_squared = float(1 - ss_res / (ss_tot + 1e-10))
        self._rmse = float(np.sqrt(np.mean((y - y_pred) ** 2)))

        # 计算特征重要性
        self._calculate_feature_importance(X, y)

        elapsed = time.time() - start_time

        logger.info(
            f"Yield predictor trained: {len(X_list)} samples, "
            f"R^2={self._r_squared:.3f}, RMSE={self._rmse:.4f}"
        )

        return TrainingResult(
            model_name="yield_predictor",
            status=AnalysisStatus.COMPLETED,
            training_time_seconds=elapsed,
            metrics={
                "r_squared": self._r_squared,
                "rmse": self._rmse,
                "parameters_count": len(self._param_order),
            },
            data_points_count=len(X_list),
        )

    def predict_yield(
        self,
        batch_id: str,
        process_params: Dict[str, float],
    ) -> YieldPrediction:
        """预测批次良率

        Args:
            batch_id: 批次标识
            process_params: 工艺参数值字典

        Returns:
            YieldPrediction: 良率预测结果
        """
        # 确定参数顺序
        param_order = self._param_order or list(process_params.keys())

        # 构建特征向量
        features = np.array([process_params.get(p, 0.0) for p in param_order])

        # 如果模型已训练，使用回归模型预测
        if self._coefficients is not None and len(self._coefficients) > 0:
            # 确保特征长度匹配
            if len(features) <= len(self._coefficients):
                coeff = self._coefficients[:len(features)]
                predicted = float(self._intercept + np.dot(features, coeff))
            else:
                predicted = float(self._intercept + np.dot(features[:len(self._coefficients)], self._coefficients))
        else:
            # 无训练模型时，基于参数偏离度估算
            predicted = self._estimate_from_deviations(features, param_order)

        # 限幅到[0, 1]
        predicted = float(np.clip(predicted, 0.05, 0.999))

        # 计算置信区间
        if self._rmse > 0:
            ci_half = self.confidence_width + self._rmse
        else:
            ci_half = self.confidence_width
        ci_lower = max(0.0, predicted - ci_half)
        ci_upper = min(1.0, predicted + ci_half)

        # 确定置信度等级
        if self._rmse > 0 and predicted > 0:
            cv = self._rmse / predicted
            if cv < 0.05:
                confidence = PredictionConfidence.HIGH
            elif cv < 0.15:
                confidence = PredictionConfidence.MEDIUM
            else:
                confidence = PredictionConfidence.LOW
        elif self._coefficients is not None:
            confidence = PredictionConfidence.HIGH
        else:
            confidence = PredictionConfidence.LOW

        # 计算特征贡献
        feature_contributions = {}
        if self._coefficients is not None and len(self._coefficients) > 0:
            for i, name in enumerate(param_order):
                if i < len(self._coefficients):
                    feature_contributions[name] = float(self._coefficients[i] * features[i])

        # 关键影响因素
        influence_factors = self._get_key_influences(features, param_order)

        return YieldPrediction(
            batch_id=batch_id,
            predicted_yield=predicted,
            confidence_interval=(ci_lower, ci_upper),
            key_influence_factors=influence_factors,
            feature_contributions=feature_contributions,
            confidence_level=confidence,
        )

    def _estimate_from_deviations(
        self,
        features: np.ndarray,
        param_order: List[str],
    ) -> float:
        """基于参数偏离度估算良率

        Args:
            features: 特征向量
            param_order: 参数顺序

        Returns:
            float: 估算良率
        """
        base_yield = 0.95
        total_penalty = 0.0

        for i, name in enumerate(param_order):
            param = self._parameters.get(name)
            if param is not None and param.target is not None:
                deviation = abs((features[i] - param.target) / (param.target + 1e-10))
                tolerance = ((param.tolerance_upper or 0) + (param.tolerance_lower or 0)) / 2
                if tolerance > 0:
                    normalized_dev = deviation / (tolerance / (param.target + 1e-10) + 1e-10)
                    total_penalty += normalized_dev * 0.02 * param.importance

        return max(0.05, base_yield - total_penalty)

    def _calculate_feature_importance(
        self,
        X: np.ndarray,
        y: np.ndarray,
    ) -> None:
        """计算特征重要性

        通过相关系数和回归权重综合分析特征重要性。

        Args:
            X: 特征矩阵
            y: 目标值
        """
        self._feature_importance.clear()

        for i, name in enumerate(self._param_order[: X.shape[1]]):
            xi = X[:, i]

            # 计算相关系数
            if np.std(xi) > 0:
                corr = float(np.corrcoef(xi, y)[0, 1])
            else:
                corr = 0.0

            # 计算重要性分数
            if self._coefficients is not None and i < len(self._coefficients):
                importance = abs(float(self._coefficients[i])) * np.std(xi)
            else:
                importance = abs(corr)

            # 估算最优范围 (基于高良率样本)
            high_yield_mask = y >= np.percentile(y, 75) if len(y) >= 4 else np.ones(len(y), dtype=bool)
            if np.any(high_yield_mask):
                optimal_min = float(np.min(xi[high_yield_mask]))
                optimal_max = float(np.max(xi[high_yield_mask]))
                optimal_range = (optimal_min, optimal_max)
            else:
                optimal_range = None

            self._feature_importance[name] = FeatureImportance(
                parameter_name=name,
                importance_score=importance,
                correlation=corr,
                optimal_range=optimal_range,
            )

    def _get_key_influences(
        self,
        features: np.ndarray,
        param_order: List[str],
    ) -> List[Tuple[str, float]]:
        """获取关键影响因素

        Args:
            features: 特征向量
            param_order: 参数顺序

        Returns:
            List[Tuple[str, float]]: (因素名, 影响值) 排序列表
        """
        influences = []

        for i, name in enumerate(param_order):
            imp = self._feature_importance.get(name)
            if imp:
                # 计算当前值距离最优范围的距离
                score = imp.importance_score
                if imp.optimal_range and i < len(features):
                    optimal_min, optimal_max = imp.optimal_range
                    val = features[i]
                    if val < optimal_min:
                        score *= 1.0 + (optimal_min - val) / (optimal_min + 1e-10)
                    elif val > optimal_max:
                        score *= 1.0 + (val - optimal_max) / (optimal_max + 1e-10)
                influences.append((name, score))
            elif self._coefficients is not None and i < len(self._coefficients):
                score = abs(float(self._coefficients[i] * features[i]))
                influences.append((name, score))

        # 按影响值降序排序
        influences.sort(key=lambda x: x[1], reverse=True)
        return influences[:5]

    def get_feature_importance(self, parameter_name: str) -> Optional[FeatureImportance]:
        """获取指定参数的特征重要性

        Args:
            parameter_name: 参数名称

        Returns:
            Optional[FeatureImportance]: 特征重要性，不存在返回None
        """
        return self._feature_importance.get(parameter_name)

    def get_all_feature_importance(self) -> Dict[str, FeatureImportance]:
        """获取所有特征重要性

        Returns:
            Dict[str, FeatureImportance]: 所有特征重要性
        """
        return self._feature_importance.copy()

    def predict_yield_batch(
        self,
        batches: List[Tuple[str, Dict[str, float]]],
    ) -> List[YieldPrediction]:
        """批量预测多个批次的良率

        Args:
            batches: 批次列表 [(batch_id, process_params), ...]

        Returns:
            List[YieldPrediction]: 良率预测结果列表
        """
        results = []
        for batch_id, params in batches:
            result = self.predict_yield(batch_id, params)
            results.append(result)
        return results

    def get_sensitivity_analysis(
        self,
        parameter_name: str,
        base_params: Dict[str, float],
        variation_range: float = 0.2,
        steps: int = 10,
    ) -> List[Tuple[float, float]]:
        """参数灵敏度分析

        分析单个参数变化对良率的影响。

        Args:
            parameter_name: 参数名称
            base_params: 基础参数值
            variation_range: 变化范围比例 (0-1)
            steps: 变化步数

        Returns:
            List[Tuple[float, float]]: (参数值, 预测良率) 列表
        """
        if parameter_name not in base_params:
            return []

        base_value = base_params[parameter_name]
        min_val = base_value * (1 - variation_range)
        max_val = base_value * (1 + variation_range)

        results = []
        for i in range(steps + 1):
            val = min_val + (max_val - min_val) * i / steps
            params = base_params.copy()
            params[parameter_name] = val
            pred = self.predict_yield(f"sensitivity_{parameter_name}_{i}", params)
            results.append((val, pred.predicted_yield))

        return results

    def get_statistics(self) -> Dict[str, Any]:
        """获取预测器统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            "record_count": len(self._yield_records),
            "parameter_count": len(self._param_order),
            "param_order": self._param_order,
            "is_trained": self._coefficients is not None,
            "r_squared": self._r_squared,
            "rmse": self._rmse,
            "feature_importance": {
                name: imp.to_dict()
                for name, imp in self._feature_importance.items()
            },
        }

    def reset(self) -> None:
        """重置预测器状态"""
        self._parameters.clear()
        self._yield_records.clear()
        self._coefficients = None
        self._intercept = 0.0
        self._param_order.clear()
        self._feature_importance.clear()
        self._r_squared = 0.0
        self._rmse = 0.0
        logger.info("YieldPredictor reset")
