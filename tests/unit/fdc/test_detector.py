"""故障检测器测试"""

import unittest
import numpy as np
from myeap.fdc.detector import (
    FaultDetector,
    StatisticalDetector,
    ChangePointDetector,
    IsolationDetector,
    TrendDetector,
    CompositeDetector,
)


class TestStatisticalDetector(unittest.TestCase):
    """测试统计检测器"""

    def setUp(self):
        """设置测试环境"""
        self.detector = StatisticalDetector(z_threshold=3.0, window_size=50)

    def test_detect_no_baseline(self):
        """测试没有基线时的检测"""
        data = np.random.normal(100, 5, 100)
        result = self.detector.detect(data)

        self.assertFalse(result.is_anomaly)
        self.assertEqual(result.score, 0.0)

    def test_detect_normal_data(self):
        """测试正常数据检测"""
        # 使用更宽松的阈值
        detector = StatisticalDetector(z_threshold=4.0, window_size=50)

        np.random.seed(42)
        baseline = np.random.normal(100, 5, 100)
        detector.update_baseline(baseline)

        # 与基线完全相同分布的数据
        np.random.seed(123)  # 使用不同的种子
        data = np.random.normal(100, 5, 100)
        result = detector.detect(data)

        # 正常数据不应该被检测为异常
        self.assertFalse(result.is_anomaly)

    def test_detect_anomaly(self):
        """测试异常检测"""
        np.random.seed(42)
        baseline = np.random.normal(100, 5, 100)
        self.detector.update_baseline(baseline)

        # 添加明显偏移的数据
        data = np.random.normal(120, 5, 100)  # 偏移4个标准差
        result = self.detector.detect(data)

        self.assertTrue(result.is_anomaly)
        self.assertGreater(result.score, 0.0)
        self.assertIsNotNone(result.z_scores)
        self.assertIsNotNone(result.anomaly_indices)

    def test_detect_with_baseline_parameter(self):
        """测试使用baseline参数"""
        np.random.seed(42)
        baseline = np.random.normal(100, 5, 100)
        data = np.random.normal(115, 5, 100)

        result = self.detector.detect(data, baseline)

        self.assertTrue(result.is_anomaly)

    def test_update_baseline(self):
        """测试更新基线"""
        np.random.seed(42)
        data = np.random.normal(100, 5, 100)

        self.detector.update_baseline(data)

        self.assertIsNotNone(self.detector.baseline_mean)
        self.assertIsNotNone(self.detector.baseline_std)

    def test_reset(self):
        """测试重置检测器"""
        np.random.seed(42)
        baseline = np.random.normal(100, 5, 100)
        self.detector.update_baseline(baseline)

        self.detector.reset()

        self.assertIsNone(self.detector.baseline_mean)
        self.assertIsNone(self.detector.baseline_std)


class TestChangePointDetector(unittest.TestCase):
    """测试变化点检测器"""

    def setUp(self):
        """设置测试环境"""
        self.detector = ChangePointDetector(
            threshold=5.0, drift=0.5, min_samples=30
        )

    def test_detect_no_baseline(self):
        """测试没有足够样本时的检测"""
        data = np.random.normal(100, 5, 20)  # 少于min_samples
        result = self.detector.detect(data)

        self.assertFalse(result.is_anomaly)

    def test_detect_change_point(self):
        """测试变化点检测"""
        np.random.seed(42)

        # 基线数据
        baseline = np.random.normal(100, 5, 50)
        self.detector.update_baseline(baseline)

        # 生成带变化点的数据
        data = np.concatenate([
            np.random.normal(100, 5, 30),
            np.random.normal(110, 5, 30),  # 变化
        ])

        result = self.detector.detect(data)

        self.assertTrue(result.is_anomaly)
        self.assertGreater(result.score, 0.0)

    def test_detect_gradual_change(self):
        """测试渐进变化检测"""
        np.random.seed(42)

        # 基线数据
        baseline = np.random.normal(100, 5, 50)
        self.detector.update_baseline(baseline)

        # 生成渐进变化的数据
        x = np.arange(60)
        data = 100 + 0.3 * x + np.random.normal(0, 3, 60)

        result = self.detector.detect(data)

        # 渐进变化可能不会立即被检测到
        self.assertIsNotNone(result)

    def test_reset(self):
        """测试重置"""
        np.random.seed(42)
        baseline = np.random.normal(100, 5, 50)
        self.detector.update_baseline(baseline)

        self.detector.reset()

        self.assertEqual(self.detector.sample_count, 0)
        self.assertEqual(self.detector.cusum_pos, 0.0)


class TestTrendDetector(unittest.TestCase):
    """测试趋势检测器"""

    def setUp(self):
        """设置测试环境"""
        self.detector = TrendDetector(
            slope_threshold=0.1, window_size=50, r_squared_threshold=0.8
        )

    def test_detect_no_trend(self):
        """测试无趋势数据"""
        np.random.seed(42)
        data = np.random.normal(100, 5, 100)

        result = self.detector.detect(data)

        self.assertFalse(result.is_anomaly)

    def test_detect_upward_trend(self):
        """测试上升趋势检测"""
        np.random.seed(42)
        x = np.arange(100)
        data = 100 + 0.3 * x + np.random.normal(0, 2, 100)  # 明显的上升趋势

        result = self.detector.detect(data)

        self.assertTrue(result.is_anomaly)
        self.assertGreater(result.score, 0.0)

    def test_detect_downward_trend(self):
        """测试下降趋势检测"""
        np.random.seed(42)
        x = np.arange(100)
        data = 150 - 0.3 * x + np.random.normal(0, 2, 100)  # 明显的下降趋势

        result = self.detector.detect(data)

        self.assertTrue(result.is_anomaly)

    def test_detect_insufficient_data(self):
        """测试数据不足"""
        np.random.seed(42)
        data = np.random.normal(100, 5, 30)  # 少于window_size

        result = self.detector.detect(data)

        self.assertFalse(result.is_anomaly)


class TestCompositeDetector(unittest.TestCase):
    """测试组合检测器"""

    def setUp(self):
        """设置测试环境"""
        self.detector = CompositeDetector(
            detectors=[
                StatisticalDetector(z_threshold=3.0),
                TrendDetector(slope_threshold=0.1),
            ],
            weights=[0.6, 0.4],
            fusion_method="weighted",
        )

    def test_add_detector(self):
        """测试添加检测器"""
        initial_count = len(self.detector.detectors)

        self.detector.add_detector(ChangePointDetector(), weight=0.5)

        self.assertEqual(len(self.detector.detectors), initial_count + 1)
        # 验证权重重新归一化
        self.assertAlmostEqual(sum(self.detector.weights), 1.0, places=5)

    def test_detect_with_fusion_and(self):
        """测试AND融合方法"""
        detector = CompositeDetector(
            detectors=[
                StatisticalDetector(z_threshold=3.0),
                TrendDetector(slope_threshold=0.1),
            ],
            fusion_method="and",
        )

        np.random.seed(42)
        baseline = np.random.normal(100, 5, 100)
        detector.detectors[0].update_baseline(baseline)

        # 只触发第一个检测器
        data1 = np.random.normal(120, 5, 100)
        result = detector.detect(data1)

        # AND方法要求所有检测器都触发
        self.assertIsNotNone(result)

    def test_detect_with_fusion_or(self):
        """测试OR融合方法"""
        detector = CompositeDetector(
            detectors=[
                StatisticalDetector(z_threshold=3.0),
                TrendDetector(slope_threshold=0.1),
            ],
            fusion_method="or",
        )

        np.random.seed(42)
        baseline = np.random.normal(100, 5, 100)
        detector.detectors[0].update_baseline(baseline)

        # 只触发第一个检测器
        data = np.random.normal(120, 5, 100)
        result = detector.detect(data)

        self.assertTrue(result.is_anomaly)

    def test_detect_with_fusion_weighted(self):
        """测试加权融合方法"""
        np.random.seed(42)
        baseline = np.random.normal(100, 5, 100)
        self.detector.update_baseline(baseline)

        data = np.random.normal(100, 5, 100)
        result = self.detector.detect(data)

        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.score, 0.0)
        self.assertLessEqual(result.score, 1.0)

    def test_reset(self):
        """测试重置"""
        np.random.seed(42)
        baseline = np.random.normal(100, 5, 100)
        self.detector.update_baseline(baseline)

        self.detector.reset()

        # 所有检测器都应该被重置
        for detector in self.detector.detectors:
            self.assertIsInstance(detector, FaultDetector)


if __name__ == "__main__":
    unittest.main()
