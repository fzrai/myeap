"""特征提取模块

从时间序列数据中提取特征，用于故障检测和分类。
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
from scipy import signal, stats

logger = logging.getLogger(__name__)


@dataclass
class FeatureVector:
    """特征向量

    包含从时间序列数据中提取的各种特征。

    Attributes:
        mean: 均值
        std: 标准差
        skewness: 偏度
        kurtosis: 峰度
        slope: 线性回归斜率
        intercept: 线性回归截距
        r_squared: 决定系数
        max_derivative: 最大导数
        min_derivative: 最小导数
        zero_crossings: 零交叉点数量
        dominant_frequency: 主导频率
        spectral_entropy: 谱熵
        stability_score: 稳定性评分 (0-1)
        peak_to_peak: 峰峰值
        rms: 均方根值
    """

    # 统计特征
    mean: float = 0.0
    std: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0

    # 趋势特征
    slope: float = 0.0
    intercept: float = 0.0
    r_squared: float = 0.0

    # 动态特征
    max_derivative: float = 0.0
    min_derivative: float = 0.0
    zero_crossings: int = 0

    # 频域特征
    dominant_frequency: float = 0.0
    spectral_entropy: float = 0.0

    # 稳定性特征
    stability_score: float = 0.0

    # 额外特征
    peak_to_peak: float = 0.0
    rms: float = 0.0

    @staticmethod
    def from_time_series(data: np.ndarray) -> "FeatureVector":
        """从时间序列提取特征

        Args:
            data: 时间序列数据

        Returns:
            FeatureVector: 特征向量
        """
        if len(data) < 3:
            logger.warning("Insufficient data points for feature extraction")
            return FeatureVector()

        # 统计特征
        mean = float(np.mean(data))
        std = float(np.std(data))
        skewness = float(stats.skew(data))
        kurtosis = float(stats.kurtosis(data))

        # 趋势特征 (线性回归)
        x = np.arange(len(data))
        try:
            slope, intercept, r_value, _, _ = stats.linregress(x, data)
            r_squared = float(r_value ** 2)
        except Exception:
            slope, intercept, r_squared = 0.0, float(data[0]), 0.0

        # 动态特征
        derivatives = np.diff(data)
        if len(derivatives) > 0:
            max_derivative = float(np.max(np.abs(derivatives)))
            min_derivative = float(np.min(np.abs(derivatives)))
            zero_crossings = int(np.sum(np.diff(np.sign(data - mean)) != 0))
        else:
            max_derivative, min_derivative, zero_crossings = 0.0, 0.0, 0

        # 频域特征
        try:
            fft = np.fft.fft(data)
            power_spectrum = np.abs(fft) ** 2
            freqs = np.fft.fftfreq(len(data))

            # 主导频率 (排除DC分量)
            positive_freqs = freqs[1 : len(freqs) // 2]
            positive_power = power_spectrum[1 : len(power_spectrum) // 2]

            if len(positive_power) > 0:
                dominant_freq_idx = np.argmax(positive_power)
                dominant_frequency = float(abs(positive_freqs[dominant_freq_idx]))
            else:
                dominant_frequency = 0.0

            # 谱熵
            power_norm = power_spectrum / (np.sum(power_spectrum) + 1e-10)
            spectral_entropy = float(
                -np.sum(power_norm * np.log2(power_norm + 1e-10))
            )
        except Exception:
            logger.warning("Error computing frequency domain features")
            dominant_frequency = 0.0
            spectral_entropy = 0.0

        # 稳定性评分 (0-1)
        stability_score = float(1.0 / (1.0 + std))

        # 峰峰值
        peak_to_peak = float(np.max(data) - np.min(data))

        # 均方根值
        rms = float(np.sqrt(np.mean(data**2)))

        return FeatureVector(
            mean=mean,
            std=std,
            skewness=skewness,
            kurtosis=kurtosis,
            slope=slope,
            intercept=intercept,
            r_squared=r_squared,
            max_derivative=max_derivative,
            min_derivative=min_derivative,
            zero_crossings=zero_crossings,
            dominant_frequency=dominant_frequency,
            spectral_entropy=spectral_entropy,
            stability_score=stability_score,
            peak_to_peak=peak_to_peak,
            rms=rms,
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "mean": self.mean,
            "std": self.std,
            "skewness": self.skewness,
            "kurtosis": self.kurtosis,
            "slope": self.slope,
            "intercept": self.intercept,
            "r_squared": self.r_squared,
            "max_derivative": self.max_derivative,
            "min_derivative": self.min_derivative,
            "zero_crossings": self.zero_crossings,
            "dominant_frequency": self.dominant_frequency,
            "spectral_entropy": self.spectral_entropy,
            "stability_score": self.stability_score,
            "peak_to_peak": self.peak_to_peak,
            "rms": self.rms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeatureVector":
        """从字典创建特征向量"""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

    def distance_to(self, other: "FeatureVector") -> float:
        """计算到另一个特征向量的欧氏距离"""
        self_dict = self.to_dict()
        other_dict = other.to_dict()

        sum_squared = 0.0
        for key in self_dict:
            if key in other_dict:
                diff = self_dict[key] - other_dict[key]
                sum_squared += diff * diff

        return float(np.sqrt(sum_squared))

    def normalize(self, min_vals: Dict[str, float], max_vals: Dict[str, float]) -> None:
        """归一化特征值到[0, 1]范围"""
        self_dict = self.to_dict()
        for key, value in self_dict.items():
            if key in min_vals and key in max_vals:
                range_val = max_vals[key] - min_vals[key]
                if range_val > 0:
                    normalized = (value - min_vals[key]) / range_val
                    setattr(self, key, float(normalized))


class FeatureExtractor:
    """特征提取器

    用于从各种数据源提取特征。

    Example:
        extractor = FeatureExtractor()
        features = extractor.extract_from_array(data)
    """

    def __init__(self, window_size: int = 100):
        """初始化特征提取器

        Args:
            window_size: 滑动窗口大小
        """
        self.window_size = window_size

    def extract_from_array(self, data: np.ndarray) -> FeatureVector:
        """从numpy数组提取特征

        Args:
            data: 时间序列数据

        Returns:
            FeatureVector: 特征向量
        """
        return FeatureVector.from_time_series(data)

    def extract_batch(
        self, data_dict: Dict[str, np.ndarray]
    ) -> Dict[str, FeatureVector]:
        """批量提取特征

        Args:
            data_dict: 参数名到时间序列的映射

        Returns:
            Dict[str, FeatureVector]: 参数名到特征向量的映射
        """
        return {
            param: FeatureVector.from_time_series(data)
            for param, data in data_dict.items()
        }

    def extract_drift_features(
        self, data: np.ndarray, baseline: np.ndarray
    ) -> Dict[str, float]:
        """提取漂移特征

        Args:
            data: 当前数据
            baseline: 基线数据

        Returns:
            Dict[str, float]: 漂移特征字典
        """
        current_features = FeatureVector.from_time_series(data)
        baseline_features = FeatureVector.from_time_series(baseline)

        return {
            "mean_shift": abs(current_features.mean - baseline_features.mean),
            "std_ratio": (
                current_features.std / baseline_features.std
                if baseline_features.std > 0
                else 0
            ),
            "slope_difference": (
                current_features.slope - baseline_features.slope
            ),
            "stability_degradation": (
                baseline_features.stability_score - current_features.stability_score
            ),
        }

    def extract_spike_features(self, data: np.ndarray) -> Dict[str, float]:
        """提取尖峰特征

        Args:
            data: 时间序列数据

        Returns:
            Dict[str, float]: 尖峰特征字典
        """
        mean = np.mean(data)
        std = np.std(data)
        z_scores = np.abs((data - mean) / (std + 1e-10))

        return {
            "max_z_score": float(np.max(z_scores)),
            "spike_count": int(np.sum(z_scores > 3.0)),
            "max_deviation": float(np.max(np.abs(data - mean))),
            "spike_ratio": float(np.sum(z_scores > 3.0) / len(data)),
        }

    def extract_oscillation_features(
        self, data: np.ndarray
    ) -> Dict[str, float]:
        """提取振荡特征

        Args:
            data: 时间序列数据

        Returns:
            Dict[str, float]: 振荡特征字典
        """
        # 使用自相关检测振荡
        autocorr = np.correlate(data - np.mean(data), data - np.mean(data), mode="full")
        autocorr = autocorr[len(autocorr) // 2 :]

        # 找到第一个局部最大值
        try:
            from scipy.signal import argrelmax

            peaks = argrelmax(autocorr[: min(len(autocorr), 100)])[0]
            if len(peaks) > 0:
                oscillation_period = float(peaks[0])
            else:
                oscillation_period = 0.0
        except Exception:
            oscillation_period = 0.0

        features = FeatureVector.from_time_series(data)

        return {
            "spectral_entropy": features.spectral_entropy,
            "zero_crossings": float(features.zero_crossings),
            "oscillation_period": oscillation_period,
            "dominant_frequency": features.dominant_frequency,
        }


def compute_similarity(
    features1: FeatureVector, features2: FeatureVector, method: str = "euclidean"
) -> float:
    """计算两个特征向量的相似度

    Args:
        features1: 第一个特征向量
        features2: 第二个特征向量
        method: 相似度计算方法 ("euclidean", "cosine", "manhattan")

    Returns:
        float: 相似度值
    """
    if method == "euclidean":
        return features1.distance_to(features2)
    elif method == "cosine":
        dict1 = features1.to_dict()
        dict2 = features2.to_dict()
        dot_product = sum(dict1[k] * dict2[k] for k in dict1 if k in dict2)
        norm1 = np.sqrt(sum(dict1[k] ** 2 for k in dict1))
        norm2 = np.sqrt(sum(dict2[k] ** 2 for k in dict2))
        if norm1 > 0 and norm2 > 0:
            return float(1 - dot_product / (norm1 * norm2))
        return 1.0
    elif method == "manhattan":
        dict1 = features1.to_dict()
        dict2 = features2.to_dict()
        return float(sum(abs(dict1[k] - dict2[k]) for k in dict1 if k in dict2))
    else:
        raise ValueError(f"Unknown similarity method: {method}")
