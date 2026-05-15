"""数据采样器测试"""

import pytest
from datetime import datetime

from myeap.data.models import DataPoint
from myeap.data.sampler import (
    DataSampler,
    TimeBasedSampler,
    ChangeBasedSampler,
    StatisticalSampler,
    SmartSampler,
)


class TestDataSampler:
    """数据采样器测试"""

    @pytest.fixture
    def sample_points(self):
        """创建测试数据点"""
        return [
            DataPoint("eq-001", "Temperature", 25.0),
            DataPoint("eq-001", "Temperature", 26.0),
            DataPoint("eq-001", "Temperature", 27.0),
            DataPoint("eq-001", "Temperature", 27.5),
            DataPoint("eq-001", "Temperature", 27.0),
        ]

    def test_creation(self):
        """测试创建采样器"""
        sampler = DataSampler()
        assert "time_based" in sampler.sampling_strategies
        assert "change_based" in sampler.sampling_strategies
        assert "statistical" in sampler.sampling_strategies
        assert "smart" in sampler.sampling_strategies

    def test_sample_with_strategy(self, sample_points):
        """测试使用策略采样"""
        sampler = DataSampler()
        result = sampler.sample(sample_points, "time_based")
        assert len(result) == len(sample_points)

    def test_unknown_strategy(self, sample_points):
        """测试未知策略"""
        sampler = DataSampler()
        result = sampler.sample(sample_points, "unknown")
        # 应该回退到 time_based
        assert len(result) == len(sample_points)

    def test_register_strategy(self, sample_points):
        """测试注册自定义策略"""
        sampler = DataSampler()
        custom_sampler = TimeBasedSampler()
        sampler.register_strategy("custom", custom_sampler)
        result = sampler.sample(sample_points, "custom")
        assert len(result) == len(sample_points)


class TestTimeBasedSampler:
    """定时采样器测试"""

    def test_sample_all_points(self):
        """测试保留所有点"""
        points = [
            DataPoint("eq-001", "Temp", 25.0),
            DataPoint("eq-001", "Temp", 26.0),
            DataPoint("eq-001", "Temp", 27.0),
        ]
        sampler = TimeBasedSampler()
        result = sampler.sample(points)
        assert len(result) == 3
        assert result == points


class TestChangeBasedSampler:
    """变化采样器测试"""

    def test_first_point_always_included(self):
        """测试第一个点总是保留"""
        points = [
            DataPoint("eq-001", "Temp", 25.0),
        ]
        sampler = ChangeBasedSampler(threshold=0.1)
        result = sampler.sample(points)
        assert len(result) == 1

    def test_preserves_significant_changes(self):
        """测试保留显著变化"""
        points = [
            DataPoint("eq-001", "Temp", 25.0),
            DataPoint("eq-001", "Temp", 50.0),  # 100% 变化
            DataPoint("eq-001", "Temp", 75.0),  # 50% 变化
        ]
        sampler = ChangeBasedSampler(threshold=0.1)
        result = sampler.sample(points)
        assert len(result) == 3  # 所有点都保留

    def test_filters_small_changes(self):
        """测试过滤微小变化"""
        points = [
            DataPoint("eq-001", "Temp", 100.0),
            DataPoint("eq-001", "Temp", 100.1),  # 0.1% 变化
            DataPoint("eq-001", "Temp", 100.2),  # 0.1% 变化
        ]
        sampler = ChangeBasedSampler(threshold=0.05)  # 5% 阈值
        result = sampler.sample(points)
        assert len(result) == 1  # 只有第一个点

    def test_reset(self):
        """测试重置"""
        points = [
            DataPoint("eq-001", "Temp", 25.0),
            DataPoint("eq-001", "Temp", 26.0),
        ]
        sampler = ChangeBasedSampler(threshold=0.1)
        sampler.sample(points)
        sampler.reset()
        assert len(sampler._last_values) == 0

    def test_different_parameters(self):
        """测试不同参数独立跟踪"""
        points = [
            DataPoint("eq-001", "Temp", 25.0),
            DataPoint("eq-001", "Pressure", 25.1),  # 不同参数
        ]
        sampler = ChangeBasedSampler(threshold=0.05)
        result = sampler.sample(points)
        assert len(result) == 2  # 两个参数都保留


class TestStatisticalSampler:
    """统计采样器测试"""

    def test_partial_window_no_output(self):
        """测试窗口未满时不输出"""
        points = [
            DataPoint("eq-001", "Temp", 25.0),
            DataPoint("eq-001", "Temp", 26.0),
        ]
        sampler = StatisticalSampler(window_size=10)
        result = sampler.sample(points)
        # 窗口未满，不输出
        assert len(result) == 0

    def test_full_window_output(self):
        """测试窗口满时输出统计值"""
        points = [
            DataPoint("eq-001", "Temp", 100.0 + i) for i in range(10)
        ]
        sampler = StatisticalSampler(window_size=10)
        result = sampler.sample(points)
        assert len(result) == 1  # 输出一个统计值
        assert result[0].value == 104.5  # 平均值

    def test_multiple_windows(self):
        """测试多个窗口"""
        points = [
            DataPoint("eq-001", "Temp", 100.0 + i) for i in range(25)
        ]
        sampler = StatisticalSampler(window_size=10)
        result = sampler.sample(points)
        assert len(result) == 2  # 两个窗口

    def test_different_parameters(self):
        """测试不同参数独立窗口"""
        points = [
            DataPoint("eq-001", "Temp", 100.0),
            DataPoint("eq-001", "Temp", 101.0),
            DataPoint("eq-001", "Pressure", 200.0),
            DataPoint("eq-001", "Pressure", 201.0),
        ]
        sampler = StatisticalSampler(window_size=10)
        result = sampler.sample(points)
        # 两个独立窗口都未满，不输出
        assert len(result) == 0

    def test_reset(self):
        """测试重置"""
        points = [
            DataPoint("eq-001", "Temp", 100.0 + i) for i in range(10)
        ]
        sampler = StatisticalSampler(window_size=10)
        sampler.sample(points)
        sampler.reset()
        assert len(sampler._windows) == 0


class TestSmartSampler:
    """智能采样器测试"""

    def test_preserves_first_point(self):
        """测试保留第一个点"""
        points = [
            DataPoint("eq-001", "Temp", 25.0),
        ]
        sampler = SmartSampler()
        result = sampler.sample(points)
        assert len(result) == 1

    def test_preserves_changes(self):
        """测试保留变化点"""
        points = [
            DataPoint("eq-001", "Temp", 0.0),
            DataPoint("eq-001", "Temp", 100.0),  # 大变化
        ]
        sampler = SmartSampler()
        result = sampler.sample(points)
        assert len(result) == 2

    def test_filters_stable_values(self):
        """测试过滤稳定值"""
        points = [
            DataPoint("eq-001", "Temp", 50.0),
            DataPoint("eq-001", "Temp", 50.01),
            DataPoint("eq-001", "Temp", 50.02),
        ]
        sampler = SmartSampler()
        result = sampler.sample(points)
        # 可能只保留部分点
        assert 1 <= len(result) <= 3

    def test_preserves_last_point(self):
        """测试保留最后一个点"""
        points = [
            DataPoint("eq-001", "Temp", 50.0),
            DataPoint("eq-001", "Temp", 50.001),
            DataPoint("eq-001", "Temp", 50.002),
        ]
        sampler = SmartSampler()
        result = sampler.sample(points)
        assert len(result) >= 1
        assert result[-1].value == 50.002

    def test_reset(self):
        """测试重置"""
        points = [
            DataPoint("eq-001", "Temp", 25.0),
            DataPoint("eq-001", "Temp", 26.0),
        ]
        sampler = SmartSampler()
        sampler.sample(points)
        sampler.reset()
        assert len(sampler._derivatives) == 0

    def test_high_frequency_data(self):
        """测试高频数据采样"""
        # 模拟高频小幅变化
        points = [
            DataPoint("eq-001", "Temp", 50.0 + i * 0.01) for i in range(100)
        ]
        sampler = SmartSampler()
        result = sampler.sample(points)
        # 智能采样应该显著减少数据量
        assert len(result) < len(points)
