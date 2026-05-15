"""控制图测试

测试各种控制图的计算和功能。
"""

import sys
from datetime import datetime
from pathlib import Path

import numpy as np

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from myeap.spc.charts import (
    ControlChart,
    ChartType,
    calculate_x_bar_r_limits,
    calculate_x_bar_s_limits,
    calculate_x_mr_limits,
    calculate_c_limits,
    calculate_u_limits,
    calculate_p_limits,
    calculate_np_limits,
    calculate_ewma_limits,
    calculate_cusum_limits,
)


class TestXBarRChart:
    """测试X-bar R控制图"""

    def test_x_bar_r_limits_calculation(self):
        """测试X-bar R图限值计算"""
        np.random.seed(42)

        # 创建5组数据，每组4个样本
        data = np.array([
            [98, 102, 101, 99],
            [100, 101, 99, 100],
            [101, 100, 102, 101],
            [99, 100, 101, 100],
            [100, 99, 101, 100],
        ])

        limits = calculate_x_bar_r_limits(data)

        # 验证限值关系
        assert limits.ucl > limits.cl > limits.lcl
        # R图限值
        assert limits.ucl_secondary is not None
        assert limits.lcl_secondary is not None
        assert limits.ucl_secondary > limits.lcl_secondary

    def test_x_bar_r_chart_data(self):
        """测试X-bar R图数据添加"""
        chart = ControlChart(
            chart_id="x_bar_r_test",
            chart_type=ChartType.X_BAR_R,
            auto_update_limits=False,
        )

        # 添加组数据
        for i in range(5):
            group_data = [100 + np.random.randn() for _ in range(4)]
            for value in group_data:
                chart.add_point(value, datetime.now(), group_id=f"group_{i}")

        assert len(chart.data) == 20


class TestXMRChart:
    """测试X-MR控制图"""

    def test_x_mr_limits_calculation(self):
        """测试X-MR图限值计算"""
        np.random.seed(42)

        # 创建30个单值数据
        data = np.random.normal(100, 2, 30)

        limits = calculate_x_mr_limits(data)

        # 验证限值关系
        assert limits.ucl > limits.cl > limits.lcl
        # MR图限值
        assert limits.ucl_secondary is not None
        assert limits.lcl_secondary == 0

    def test_x_mr_chart_update_limits(self):
        """测试X-MR图限值更新"""
        chart = ControlChart(
            chart_id="x_mr_test",
            chart_type=ChartType.X_MR,
            min_samples=20,
        )

        np.random.seed(42)
        for _ in range(25):
            chart.add_point(100 + np.random.randn())

        # 手动更新限值 (引擎会做这个)
        limits = chart.update_limits()
        assert limits is not None
        assert limits.ucl > limits.cl > limits.lcl


class TestAttributeCharts:
    """测试计数型控制图"""

    def test_c_chart_limits(self):
        """测试C图限值计算"""
        np.random.seed(42)

        # 泊松分布的缺陷数
        data = np.random.poisson(10, 50)

        limits = calculate_c_limits(data)

        assert limits.ucl > limits.cl >= 0
        assert limits.lcl >= 0
        assert limits.cl == np.mean(data)

    def test_u_chart_limits(self):
        """测试U图限值计算"""
        np.random.seed(42)

        # 缺陷数
        defects = np.random.poisson(5, 30)
        # 单位数
        units = np.random.randint(1, 10, 30)

        limits = calculate_u_limits(defects, units)

        assert limits.ucl > limits.cl >= 0
        assert limits.lcl >= 0

    def test_p_chart_limits(self):
        """测试P图限值计算"""
        np.random.seed(42)

        # 不合格数
        defectives = np.random.binomial(100, 0.05, 40)
        # 样本大小
        sample_sizes = np.full(40, 100)

        limits = calculate_p_limits(defectives, sample_sizes)

        assert limits.ucl > limits.cl >= 0
        assert limits.lcl >= 0

    def test_np_chart_limits(self):
        """测试NP图限值计算"""
        np.random.seed(42)

        # 不合格数 (样本大小固定为100)
        data = np.random.binomial(100, 0.05, 40)

        limits = calculate_np_limits(data, sample_size=100)

        assert limits.ucl > limits.cl >= 0
        assert limits.lcl >= 0


class TestAdvancedCharts:
    """测试高级控制图"""

    def test_ewma_limits(self):
        """测试EWMA图限值计算"""
        np.random.seed(42)

        data = np.random.normal(100, 2, 50)

        limits = calculate_ewma_limits(data, lambda_=0.2)

        assert limits.ucl > limits.cl > limits.lcl
        assert limits.cl == np.mean(data)

    def test_ewma_with_target(self):
        """测试带目标值的EWMA图"""
        np.random.seed(42)

        data = np.random.normal(100, 2, 50)

        limits = calculate_ewma_limits(data, lambda_=0.2, target=100)

        assert limits.cl == 100

    def test_cusum_limits(self):
        """测试CUSUM图限值计算"""
        np.random.seed(42)

        data = np.random.normal(100, 2, 50)

        limits = calculate_cusum_limits(data, target=100)

        assert limits.ucl > 0
        assert limits.lcl < 0
        assert limits.cl == 0


class TestChartStatistics:
    """测试图表统计功能"""

    def test_statistics_calculation(self):
        """测试统计计算"""
        chart = ControlChart(
            chart_id="stats_test",
            chart_type=ChartType.X_MR,
            auto_update_limits=False,
        )

        np.random.seed(42)
        for _ in range(20):
            chart.add_point(100 + np.random.randn())

        stats = chart.statistics

        assert stats is not None
        assert abs(stats.mean - 100) < 0.5  # 应该接近100
        assert stats.std > 0
        assert stats.min <= stats.mean <= stats.max
        assert stats.median is not None
        assert stats.sample_count == 20


def run_chart_tests():
    """运行控制图测试"""
    import traceback

    test_classes = [
        TestXBarRChart,
        TestXMRChart,
        TestAttributeCharts,
        TestAdvancedCharts,
        TestChartStatistics,
    ]

    passed = 0
    failed = 0
    errors = []

    for test_class in test_classes:
        print(f"\n=== {test_class.__name__} ===")
        instance = test_class()

        for method_name in dir(instance):
            if method_name.startswith("test_"):
                try:
                    method = getattr(instance, method_name)
                    method()
                    print(f"  PASS: {method_name}")
                    passed += 1
                except Exception as e:
                    print(f"  FAIL: {method_name}: {e}")
                    failed += 1
                    errors.append((test_class.__name__, method_name, str(e)))

    print(f"\n{'='*50}")
    print(f"Total: {passed + failed}, Passed: {passed}, Failed: {failed}")

    if errors:
        print("\nFailed tests:")
        for cls_name, method_name, error in errors:
            print(f"  {cls_name}.{method_name}: {error}")

    return failed == 0


if __name__ == "__main__":
    success = run_chart_tests()
    sys.exit(0 if success else 1)
