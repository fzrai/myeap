"""SPC模块测试

测试SPC引擎的核心功能，包括控制图、规则检查和过程能力分析。
"""

import sys
from datetime import datetime
from pathlib import Path

import numpy as np

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from myeap.spc import (
    ChartType,
    ControlChart,
    ControlLimits,
    ProcessCapability,
    SPCEngine,
    SPCRule,
    SPCViolation,
    check_spc_rules,
    calculate_x_bar_r_limits,
    calculate_x_mr_limits,
    calculate_c_limits,
    calculate_p_limits,
    calculate_capability,
)


class TestControlLimits:
    """测试控制限"""

    def test_control_limits_creation(self):
        """测试控制限创建"""
        limits = ControlLimits(ucl=100, cl=50, lcl=0)
        assert limits.ucl == 100
        assert limits.cl == 50
        assert limits.lcl == 0
        assert limits.range == 100

    def test_control_limits_is_within(self):
        """测试范围检查"""
        limits = ControlLimits(ucl=100, cl=50, lcl=0)
        assert limits.is_within_limits(50) is True
        assert limits.is_within_limits(0) is True
        assert limits.is_within_limits(100) is True
        assert limits.is_within_limits(-1) is False
        assert limits.is_within_limits(101) is False

    def test_control_limits_sigma(self):
        """测试sigma计算"""
        limits = ControlLimits(ucl=106, cl=100, lcl=94)
        assert abs(limits.sigma - 2.0) < 0.001


class TestChartTypes:
    """测试图表类型"""

    def test_chart_type_properties(self):
        """测试图表类型属性"""
        assert ChartType.X_BAR_R.is_variable_chart is True
        assert ChartType.X_BAR_R.is_attribute_chart is False
        assert ChartType.C.is_attribute_chart is True
        assert ChartType.C.is_variable_chart is False

    def test_chart_type_descriptions(self):
        """测试图表类型描述"""
        assert "X-bar" in ChartType.X_BAR_R.description
        assert "R" in ChartType.X_BAR_R.description


class TestControlLimitsCalculation:
    """测试控制限计算"""

    def test_x_bar_r_limits(self):
        """测试X-bar R图限值计算"""
        # 创建测试数据: 5组，每组4个样本
        np.random.seed(42)
        data = np.random.normal(100, 2, (5, 4))

        limits = calculate_x_bar_r_limits(data)

        assert limits.ucl > limits.cl > limits.lcl
        assert limits.ucl_secondary is not None
        assert limits.lcl_secondary is not None

    def test_x_mr_limits(self):
        """测试X-MR图限值计算"""
        np.random.seed(42)
        data = np.random.normal(100, 2, 20)

        limits = calculate_x_mr_limits(data)

        assert limits.ucl > limits.cl > limits.lcl
        assert limits.ucl_secondary > limits.lcl_secondary

    def test_c_limits(self):
        """测试C图限值计算"""
        np.random.seed(42)
        data = np.random.poisson(10, 30)  # 泊松分布缺陷数

        limits = calculate_c_limits(data)

        assert limits.ucl > limits.cl >= 0
        assert limits.lcl >= 0

    def test_p_limits(self):
        """测试P图限值计算"""
        np.random.seed(42)
        # 不合格数 (每组100个样本)
        defectives = np.random.binomial(100, 0.05, 30)
        sample_sizes = np.full(30, 100)

        limits = calculate_p_limits(defectives, sample_sizes)

        assert limits.ucl > limits.cl >= 0
        assert limits.lcl >= 0


class TestSPCRules:
    """测试SPC规则"""

    def test_rule_1_violation(self):
        """测试Rule 1: 点落在控制限外"""
        limits = ControlLimits(ucl=100, cl=50, lcl=0)
        data = [50, 60, 70, 80, 90, 110, 100]  # 110超出控制限

        violations = check_spc_rules(data, limits, [SPCRule.RULE_1])

        assert len(violations) == 1
        assert violations[0].rule == SPCRule.RULE_1
        assert violations[0].data_index == 5

    def test_rule_2_violation(self):
        """测试Rule 2: 连续9点在中心线同一侧"""
        limits = ControlLimits(ucl=100, cl=50, lcl=0)
        data = [60] * 9 + [50, 40, 60]  # 前9点在中心线上方

        violations = check_spc_rules(data, limits, [SPCRule.RULE_2])

        assert len(violations) == 1
        assert violations[0].rule == SPCRule.RULE_2

    def test_rule_3_violation(self):
        """测试Rule 3: 连续6点递增或递减"""
        limits = ControlLimits(ucl=100, cl=50, lcl=0)
        data = [10, 20, 30, 40, 50, 60, 70]  # 递增

        violations = check_spc_rules(data, limits, [SPCRule.RULE_3])

        assert len(violations) >= 1
        assert violations[0].rule == SPCRule.RULE_3

    def test_multiple_rules(self):
        """测试多个规则"""
        limits = ControlLimits(ucl=100, cl=50, lcl=0)
        data = [60, 70, 80, 90, 95, 105, 100]  # Rule 1违规

        violations = check_spc_rules(data, limits)

        assert len(violations) >= 1


class TestControlChart:
    """测试控制图"""

    def test_chart_creation(self):
        """测试控制图创建"""
        chart = ControlChart(
            chart_id="test_chart",
            chart_type=ChartType.X_MR,
            name="Test Chart",
        )

        assert chart.chart_id == "test_chart"
        assert chart.chart_type == ChartType.X_MR
        assert len(chart.data) == 0

    def test_add_point(self):
        """测试添加数据点"""
        chart = ControlChart(
            chart_id="test_chart",
            chart_type=ChartType.X_MR,
        )

        point = chart.add_point(100.0, datetime.now())

        assert len(chart.data) == 1
        assert chart.data[0] == 100.0
        assert point.index == 0

    def test_add_multiple_points(self):
        """测试添加多个数据点"""
        chart = ControlChart(
            chart_id="test_chart",
            chart_type=ChartType.X_MR,
            auto_update_limits=False,
        )

        for i in range(25):
            chart.add_point(100.0 + np.random.randn())

        assert len(chart.data) == 25

    def test_chart_statistics(self):
        """测试统计信息"""
        chart = ControlChart(
            chart_id="test_chart",
            chart_type=ChartType.X_MR,
            auto_update_limits=False,
        )

        for _ in range(10):
            chart.add_point(100.0)

        stats = chart.statistics
        assert stats is not None
        assert stats.mean == 100.0
        assert stats.min == 100.0
        assert stats.max == 100.0
        assert stats.sample_count == 10


class TestSPCEngine:
    """测试SPC引擎"""

    def test_engine_creation(self):
        """测试引擎创建"""
        engine = SPCEngine()

        assert len(engine.charts) == 0
        assert len(engine.rules) > 0

    def test_create_chart(self):
        """测试创建控制图"""
        engine = SPCEngine()

        chart = engine.create_chart(
            chart_id="temp_chart",
            chart_type=ChartType.X_MR,
            name="Temperature Chart",
        )

        assert chart is not None
        assert chart.chart_id == "temp_chart"
        assert len(engine.charts) == 1

    def test_create_duplicate_chart(self):
        """测试创建重复ID的控制图"""
        engine = SPCEngine()

        engine.create_chart("temp_chart", ChartType.X_MR)

        try:
            engine.create_chart("temp_chart", ChartType.X_MR)
            assert False, "Should raise ValueError"
        except ValueError as e:
            assert "already exists" in str(e)

    def test_add_data_point(self):
        """测试添加数据点"""
        engine = SPCEngine()

        engine.create_chart("temp_chart", ChartType.X_MR)

        violations = engine.add_data_point("temp_chart", 100.0, datetime.now())

        assert len(engine.charts["temp_chart"].data) == 1
        assert isinstance(violations, list)

    def test_add_data_point_to_nonexistent_chart(self):
        """测试向不存在的控制图添加数据"""
        engine = SPCEngine()

        try:
            engine.add_data_point("nonexistent", 100.0)
            assert False, "Should raise ValueError"
        except ValueError as e:
            assert "not found" in str(e)

    def test_add_batch(self):
        """测试批量添加数据"""
        engine = SPCEngine()
        engine.create_chart("temp_chart", ChartType.X_MR)

        data = [100.0 + np.random.randn() for _ in range(10)]
        violations = engine.add_batch("temp_chart", data)

        assert len(engine.charts["temp_chart"].data) == 10
        assert isinstance(violations, list)

    def test_get_chart_statistics(self):
        """测试获取统计信息"""
        engine = SPCEngine()
        engine.create_chart("temp_chart", ChartType.X_MR, auto_update_limits=False)

        for _ in range(10):
            engine.add_data_point("temp_chart", 100.0)

        stats = engine.get_chart_statistics("temp_chart")

        assert stats is not None
        assert stats.mean == 100.0

    def test_delete_chart(self):
        """测试删除控制图"""
        engine = SPCEngine()
        engine.create_chart("temp_chart", ChartType.X_MR)

        result = engine.delete_chart("temp_chart")

        assert result is True
        assert len(engine.charts) == 0

    def test_reset_chart(self):
        """测试重置控制图"""
        engine = SPCEngine()
        engine.create_chart("temp_chart", ChartType.X_MR)

        for _ in range(10):
            engine.add_data_point("temp_chart", 100.0)

        engine.reset_chart("temp_chart")

        assert len(engine.charts["temp_chart"].data) == 0

    def test_engine_summary(self):
        """测试引擎摘要"""
        engine = SPCEngine()
        engine.create_chart("chart1", ChartType.X_MR)
        engine.create_chart("chart2", ChartType.X_BAR_R)

        summary = engine.get_summary()

        assert summary["total_charts"] == 2
        assert len(summary["charts"]) == 2


class TestProcessCapability:
    """测试过程能力分析"""

    def test_capability_within_spec(self):
        """测试在规格内的过程能力"""
        np.random.seed(42)
        data = np.random.normal(100, 2, 100)

        capability = calculate_capability(
            data,
            usl=110,
            lsl=90,
        )

        assert capability.cp > 0
        assert capability.cpk > 0
        assert capability.sigma_within > 0
        assert capability.sigma_total > 0

    def test_capability_one_sided_spec(self):
        """测试单边规格限"""
        np.random.seed(42)
        data = np.random.normal(100, 2, 100)

        # 只有上限
        cap_upper = calculate_capability(data, usl=110)

        assert cap_upper.cp == 0
        assert cap_upper.cpu > 0

        # 只有下限
        cap_lower = calculate_capability(data, lsl=90)

        assert cap_lower.cp == 0
        assert cap_lower.cpl > 0

    def test_capability_interpretation(self):
        """测试能力等级解释"""
        np.random.seed(42)
        data = np.random.normal(100, 1, 100)

        capability = calculate_capability(
            data,
            usl=106,
            lsl=94,
        )

        # 6sigma范围约为99.73%的数据
        assert capability.cp > 0
        assert capability.cpk > 0

    def test_capability_excellent_process(self):
        """测试优秀过程"""
        np.random.seed(42)
        # 标准差很小的过程
        data = np.random.normal(100, 0.5, 100)

        capability = calculate_capability(
            data,
            usl=106,
            lsl=94,
        )

        # 应该能力很好
        assert capability.cp > 2
        assert capability.cpk > 2

    def test_capability_dict_export(self):
        """测试导出为字典"""
        np.random.seed(42)
        data = np.random.normal(100, 2, 100)

        capability = calculate_capability(
            data,
            usl=110,
            lsl=90,
        )

        result = capability.to_dict()

        assert "cp" in result
        assert "cpk" in result
        assert "mean" in result
        assert "is_capable" in result


class TestSPCViolation:
    """测试SPC违规"""

    def test_violation_creation(self):
        """测试违规创建"""
        violation = SPCViolation(
            rule=SPCRule.RULE_1,
            data_index=5,
            value=110.0,
            expected_range=(0, 100),
        )

        assert violation.rule == SPCRule.RULE_1
        assert violation.data_index == 5
        assert violation.value == 110.0
        assert violation.severity.value == "critical"

    def test_violation_to_dict(self):
        """测试违规转换为字典"""
        violation = SPCViolation(
            rule=SPCRule.RULE_2,
            data_index=0,
            value=60.0,
            expected_range=(0, 100),
        )

        result = violation.to_dict()

        assert result["rule"] == "rule_2"
        assert result["data_index"] == 0
        assert result["value"] == 60.0


def run_all_tests():
    """运行所有测试"""
    import traceback

    test_classes = [
        TestControlLimits,
        TestChartTypes,
        TestControlLimitsCalculation,
        TestSPCRules,
        TestControlChart,
        TestSPCEngine,
        TestProcessCapability,
        TestSPCViolation,
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
    success = run_all_tests()
    sys.exit(0 if success else 1)
