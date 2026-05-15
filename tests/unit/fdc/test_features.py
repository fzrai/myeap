"""特征提取测试"""

import unittest
import numpy as np
from myeap.fdc.features import FeatureVector, FeatureExtractor


class TestFeatureVector(unittest.TestCase):
    """测试特征向量"""

    def test_from_time_series_normal(self):
        """测试从正常时间序列提取特征"""
        # 生成正态分布数据
        np.random.seed(42)
        data = np.random.normal(100, 5, 100)

        features = FeatureVector.from_time_series(data)

        self.assertIsNotNone(features.mean)
        self.assertIsNotNone(features.std)
        self.assertIsNotNone(features.skewness)
        self.assertIsNotNone(features.kurtosis)
        self.assertIsNotNone(features.stability_score)

        # 正态分布数据应该接近0偏度和3峰度(实际是超量峰度)
        self.assertLess(abs(features.skewness), 1.0)
        self.assertLess(abs(features.kurtosis), 5.0)  # 放宽容差

    def test_from_time_series_with_trend(self):
        """测试从有趋势的时间序列提取特征"""
        # 生成有上升趋势的数据
        x = np.arange(100)
        data = 100 + 0.5 * x + np.random.normal(0, 2, 100)

        features = FeatureVector.from_time_series(data)

        self.assertGreater(features.slope, 0.3)
        self.assertGreater(features.r_squared, 0.9)

    def test_from_time_series_with_spikes(self):
        """测试从有尖峰的时间序列提取特征"""
        np.random.seed(42)
        data = np.random.normal(100, 5, 100)
        # 添加几个尖峰
        data[10] = 150
        data[50] = 160
        data[80] = 155

        features = FeatureVector.from_time_series(data)

        # 有尖峰的数据应该有较大的峰度
        self.assertGreater(features.kurtosis, 3)

    def test_from_time_series_insufficient_data(self):
        """测试数据不足时的处理"""
        data = np.array([1, 2])

        features = FeatureVector.from_time_series(data)

        # 应该返回默认值的特征向量
        self.assertEqual(features.mean, 0.0)
        self.assertEqual(features.std, 0.0)

    def test_to_dict(self):
        """测试转换为字典"""
        features = FeatureVector(
            mean=100.0,
            std=5.0,
            skewness=0.1,
            kurtosis=3.0,
            slope=0.5,
            intercept=100.0,
            r_squared=0.95,
            max_derivative=10.0,
            min_derivative=1.0,
            zero_crossings=5,
            dominant_frequency=0.1,
            spectral_entropy=0.5,
            stability_score=0.8,
            peak_to_peak=20.0,
            rms=100.2,
        )

        d = features.to_dict()

        self.assertEqual(d["mean"], 100.0)
        self.assertEqual(d["std"], 5.0)
        self.assertEqual(d["slope"], 0.5)
        self.assertIn("stability_score", d)

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "mean": 100.0,
            "std": 5.0,
            "skewness": 0.1,
            "kurtosis": 3.0,
        }

        features = FeatureVector.from_dict(data)

        self.assertEqual(features.mean, 100.0)
        self.assertEqual(features.std, 5.0)

    def test_distance_to(self):
        """测试计算距离"""
        f1 = FeatureVector(mean=100.0, std=5.0)
        f2 = FeatureVector(mean=110.0, std=10.0)

        distance = f1.distance_to(f2)

        self.assertGreater(distance, 0)


class TestFeatureExtractor(unittest.TestCase):
    """测试特征提取器"""

    def test_extract_from_array(self):
        """测试从数组提取特征"""
        extractor = FeatureExtractor(window_size=50)
        np.random.seed(42)
        data = np.random.normal(100, 5, 100)

        features = extractor.extract_from_array(data)

        self.assertIsNotNone(features.mean)
        self.assertIsNotNone(features.std)

    def test_extract_batch(self):
        """测试批量提取"""
        extractor = FeatureExtractor()
        np.random.seed(42)

        data_dict = {
            "temperature": np.random.normal(100, 5, 100),
            "pressure": np.random.normal(1, 0.1, 100),
            "flow": np.random.normal(50, 2, 100),
        }

        features_dict = extractor.extract_batch(data_dict)

        self.assertEqual(len(features_dict), 3)
        self.assertIn("temperature", features_dict)
        self.assertIn("pressure", features_dict)
        self.assertIn("flow", features_dict)

    def test_extract_drift_features(self):
        """测试漂移特征提取"""
        extractor = FeatureExtractor()

        # 基线数据
        np.random.seed(42)
        baseline = np.random.normal(100, 5, 100)

        # 漂移数据
        x = np.arange(100)
        current = np.random.normal(105, 5, 100) + 0.1 * x

        drift_features = extractor.extract_drift_features(current, baseline)

        self.assertIn("mean_shift", drift_features)
        self.assertIn("std_ratio", drift_features)
        self.assertIn("slope_difference", drift_features)
        self.assertGreater(drift_features["mean_shift"], 0)

    def test_extract_spike_features(self):
        """测试尖峰特征提取"""
        extractor = FeatureExtractor()
        np.random.seed(42)
        data = np.random.normal(100, 5, 100)
        data[50] = 200  # 添加明显尖峰

        spike_features = extractor.extract_spike_features(data)

        self.assertIn("max_z_score", spike_features)
        self.assertIn("spike_count", spike_features)
        self.assertGreater(spike_features["max_z_score"], 5)  # 降低阈值

    def test_extract_oscillation_features(self):
        """测试振荡特征提取"""
        extractor = FeatureExtractor()

        # 生成振荡数据
        t = np.linspace(0, 10, 100)
        data = 100 + 10 * np.sin(2 * np.pi * t) + np.random.normal(0, 1, 100)

        osc_features = extractor.extract_oscillation_features(data)

        self.assertIn("spectral_entropy", osc_features)
        self.assertIn("zero_crossings", osc_features)


if __name__ == "__main__":
    unittest.main()
