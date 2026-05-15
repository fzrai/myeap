"""故障分类器测试"""

import unittest
import numpy as np
from myeap.fdc.classifier import (
    Condition,
    FeatureCondition,
    CompositeCondition,
    ClassificationRule,
    FaultClassifier,
)
from myeap.fdc.features import FeatureVector
from myeap.fdc.models import FaultType


class TestFeatureCondition(unittest.TestCase):
    """测试特征条件"""

    def test_greater_than(self):
        """测试大于条件"""
        condition = FeatureCondition("std", ">", 5.0)
        features = FeatureVector(std=10.0)

        self.assertTrue(condition.evaluate(features))

    def test_less_than(self):
        """测试小于条件"""
        condition = FeatureCondition("stability_score", "<", 0.5)
        features = FeatureVector(stability_score=0.3)

        self.assertTrue(condition.evaluate(features))

    def test_greater_than_or_equal(self):
        """测试大于等于条件"""
        condition = FeatureCondition("r_squared", ">=", 0.8)
        features = FeatureVector(r_squared=0.8)

        self.assertTrue(condition.evaluate(features))

    def test_less_than_or_equal(self):
        """测试小于等于条件"""
        condition = FeatureCondition("mean", "<=", 100.0)
        features = FeatureVector(mean=100.0)

        self.assertTrue(condition.evaluate(features))

    def test_equal(self):
        """测试等于条件"""
        condition = FeatureCondition("slope", "==", 0.0)
        features = FeatureVector(slope=0.0)

        self.assertTrue(condition.evaluate(features))

    def test_not_equal(self):
        """测试不等于条件"""
        condition = FeatureCondition("slope", "!=", 0.0)
        features = FeatureVector(slope=0.5)

        self.assertTrue(condition.evaluate(features))

    def test_missing_feature(self):
        """测试特征不存在"""
        condition = FeatureCondition("nonexistent", ">", 0.0)
        features = FeatureVector(mean=100.0)

        self.assertFalse(condition.evaluate(features))


class TestCompositeCondition(unittest.TestCase):
    """测试组合条件"""

    def test_and_logic_all_true(self):
        """测试AND逻辑-全部为真"""
        conditions = [
            FeatureCondition("std", ">", 1.0),
            FeatureCondition("stability_score", "<", 0.5),
        ]
        composite = CompositeCondition(conditions, logic="and")

        features = FeatureVector(std=5.0, stability_score=0.3)

        self.assertTrue(composite.evaluate(features))

    def test_and_logic_one_false(self):
        """测试AND逻辑-一个为假"""
        conditions = [
            FeatureCondition("std", ">", 1.0),
            FeatureCondition("stability_score", "<", 0.5),
        ]
        composite = CompositeCondition(conditions, logic="and")

        features = FeatureVector(std=5.0, stability_score=0.8)

        self.assertFalse(composite.evaluate(features))

    def test_or_logic_one_true(self):
        """测试OR逻辑-一个为真"""
        conditions = [
            FeatureCondition("std", ">", 10.0),
            FeatureCondition("stability_score", "<", 0.5),
        ]
        composite = CompositeCondition(conditions, logic="or")

        features = FeatureVector(std=5.0, stability_score=0.3)

        self.assertTrue(composite.evaluate(features))

    def test_or_logic_all_false(self):
        """测试OR逻辑-全部为假"""
        conditions = [
            FeatureCondition("std", ">", 10.0),
            FeatureCondition("stability_score", "<", 0.1),
        ]
        composite = CompositeCondition(conditions, logic="or")

        features = FeatureVector(std=5.0, stability_score=0.8)

        self.assertFalse(composite.evaluate(features))


class TestClassificationRule(unittest.TestCase):
    """测试分类规则"""

    def test_validate_matching(self):
        """测试匹配的规则验证"""
        rule = ClassificationRule(
            name="temp_drift_rule",
            fault_type=FaultType.TEMP_DRIFT,
            conditions=[
                FeatureCondition("slope", "!=", 0.0),
                FeatureCondition("r_squared", ">=", 0.7),
            ],
            confidence=0.85,
            recommendations=["检查传感器"],
        )

        features = FeatureVector(slope=0.5, r_squared=0.9)

        self.assertTrue(rule.validate(features))

    def test_validate_not_matching(self):
        """测试不匹配的规则验证"""
        rule = ClassificationRule(
            name="temp_drift_rule",
            fault_type=FaultType.TEMP_DRIFT,
            conditions=[
                FeatureCondition("slope", "!=", 0.0),
                FeatureCondition("r_squared", ">=", 0.7),
            ],
            confidence=0.85,
        )

        features = FeatureVector(slope=0.0, r_squared=0.9)  # slope为0

        self.assertFalse(rule.validate(features))


class TestFaultClassifier(unittest.TestCase):
    """测试故障分类器"""

    def setUp(self):
        """设置测试环境"""
        self.classifier = FaultClassifier()

    def test_default_rules_exist(self):
        """测试默认规则存在"""
        self.assertGreater(len(self.classifier._rules), 0)

    def test_classify_temp_drift(self):
        """测试温度漂移分类"""
        # 模拟温度漂移特征
        features = FeatureVector(
            mean=150.0,
            std=5.0,
            skewness=0.2,
            kurtosis=3.0,
            slope=0.8,  # 明显趋势
            intercept=100.0,
            r_squared=0.85,  # 高决定系数
            stability_score=0.3,  # 低稳定性
        )

        result = self.classifier.classify(features)

        self.assertNotEqual(result.fault_type, FaultType.UNKNOWN)
        self.assertGreater(result.confidence, 0.0)

    def test_classify_temp_spike(self):
        """测试温度尖峰分类"""
        features = FeatureVector(
            mean=100.0,
            std=10.0,
            skewness=1.5,
            kurtosis=10.0,  # 高峰度
            max_derivative=15.0,  # 大导数
            stability_score=0.2,
        )

        result = self.classifier.classify(features)

        self.assertNotEqual(result.fault_type, FaultType.UNKNOWN)

    def test_classify_unknown(self):
        """测试未知分类"""
        # 使用极端的正常特征值，不会匹配任何规则
        features = FeatureVector(
            mean=100.0,
            std=0.5,
            skewness=0.0,
            kurtosis=3.0,
            slope=0.0,
            r_squared=0.1,
            stability_score=0.99,
            max_derivative=0.1,
            zero_crossings=0,
            dominant_frequency=0.0,
            spectral_entropy=0.1,
        )

        result = self.classifier.classify(features)

        self.assertEqual(result.fault_type, FaultType.UNKNOWN)
        self.assertEqual(result.confidence, 0.0)

    def test_classify_with_known_fault_type(self):
        """测试使用已知故障类型验证"""
        # 创建一个符合TEMP_DRIFT的特征
        features = FeatureVector(
            mean=150.0,
            std=5.0,
            skewness=0.0,
            kurtosis=3.0,
            slope=0.5,  # 有斜率
            r_squared=0.8,  # 高决定系数
            stability_score=0.3,  # 低稳定性
            max_derivative=1.0,
        )

        # 验证一个匹配的特征
        result = self.classifier.classify(features, FaultType.TEMP_DRIFT)
        self.assertEqual(result.fault_type, FaultType.TEMP_DRIFT)

        # 验证一个不匹配的特征
        features2 = FeatureVector(
            mean=100.0,
            std=0.5,
            skewness=0.0,
            kurtosis=3.0,
            slope=0.0,  # 无斜率
            r_squared=0.1,
            stability_score=0.99,
            max_derivative=0.1,
        )
        result2 = self.classifier.classify(features2, FaultType.TEMP_DRIFT)
        self.assertEqual(result2.fault_type, FaultType.UNKNOWN)

    def test_add_rule(self):
        """测试添加规则"""
        initial_count = len(self.classifier._rules)

        new_rule = ClassificationRule(
            name="custom_rule",
            fault_type=FaultType.RF_POWER_ERROR,
            conditions=[FeatureCondition("std", ">", 2.0)],
            confidence=0.9,
        )

        self.classifier.add_rule(new_rule)

        self.assertEqual(len(self.classifier._rules), initial_count + 1)

    def test_remove_rule(self):
        """测试移除规则"""
        rule_name = self.classifier._rules[0].name
        initial_count = len(self.classifier._rules)

        result = self.classifier.remove_rule(rule_name)

        self.assertTrue(result)
        self.assertEqual(len(self.classifier._rules), initial_count - 1)

    def test_remove_rule_not_found(self):
        """测试移除不存在的规则"""
        result = self.classifier.remove_rule("nonexistent_rule")

        self.assertFalse(result)

    def test_get_recommendations(self):
        """测试获取建议"""
        recommendations = self.classifier.get_recommendations(FaultType.TEMP_DRIFT)

        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)

    def test_get_recommendations_unknown_type(self):
        """测试未知类型的建议"""
        recommendations = self.classifier.get_recommendations(FaultType.UNKNOWN)

        self.assertEqual(len(recommendations), 0)


class TestFaultClassifierPriorities(unittest.TestCase):
    """测试分类器规则优先级"""

    def test_rules_sorted_by_priority(self):
        """测试规则按优先级排序"""
        classifier = FaultClassifier()

        priorities = [rule.priority for rule in classifier._rules]

        # 验证已排序
        for i in range(len(priorities) - 1):
            self.assertLessEqual(priorities[i], priorities[i + 1])


if __name__ == "__main__":
    unittest.main()
