"""AI/ML数据模型测试

测试FailurePrediction、YieldPrediction、RootCauseResult等数据模型。
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from myeap.ai.models import (
    AnalysisStatus,
    AnomalyPattern,
    EquipmentHealthReport,
    FailurePrediction,
    MaintenanceRecommendation,
    PredictionConfidence,
    ProcessParameter,
    RootCauseResult,
    TrainingResult,
    YieldPrediction,
)


class TestFailurePrediction:
    """测试故障预测模型"""

    def test_creation(self):
        """测试创建FailurePrediction"""
        pred = FailurePrediction(
            equipment_id="eq-001",
            failure_probability=0.7,
            predicted_failure_time=datetime.now() + timedelta(hours=48),
            remaining_useful_life_hours=48.0,
            confidence_interval=(0.6, 0.8),
            risk_factors=["temperature_high"],
            recommended_actions=["检查冷却系统"],
        )
        assert pred.equipment_id == "eq-001"
        assert pred.failure_probability == 0.7
        assert pred.remaining_useful_life_hours == 48.0

    def test_risk_level_critical(self):
        """测试风险等级 - critical"""
        pred = FailurePrediction(
            equipment_id="eq-001",
            failure_probability=0.9,
            predicted_failure_time=None,
            remaining_useful_life_hours=10.0,
            confidence_interval=(0.8, 0.95),
        )
        assert pred.risk_level == "critical"

    def test_risk_level_high(self):
        """测试风险等级 - high"""
        pred = FailurePrediction(
            equipment_id="eq-001",
            failure_probability=0.7,
            predicted_failure_time=None,
            remaining_useful_life_hours=100.0,
            confidence_interval=(0.6, 0.8),
        )
        assert pred.risk_level == "high"

    def test_risk_level_medium(self):
        """测试风险等级 - medium"""
        pred = FailurePrediction(
            equipment_id="eq-001",
            failure_probability=0.4,
            predicted_failure_time=None,
            remaining_useful_life_hours=500.0,
            confidence_interval=(0.3, 0.5),
        )
        assert pred.risk_level == "medium"

    def test_risk_level_low(self):
        """测试风险等级 - low"""
        pred = FailurePrediction(
            equipment_id="eq-001",
            failure_probability=0.1,
            predicted_failure_time=None,
            remaining_useful_life_hours=float("inf"),
            confidence_interval=(0.0, 0.2),
        )
        assert pred.risk_level == "low"

    def test_time_to_failure(self):
        """测试失效时间计算"""
        future_time = datetime.now() + timedelta(hours=24)
        pred = FailurePrediction(
            equipment_id="eq-001",
            failure_probability=0.5,
            predicted_failure_time=future_time,
            remaining_useful_life_hours=24.0,
            confidence_interval=(0.4, 0.6),
        )
        assert pred.time_to_failure_hours <= 24.0
        assert pred.time_to_failure_hours > 0

    def test_no_predicted_failure_time(self):
        """测试无预测失效时间"""
        pred = FailurePrediction(
            equipment_id="eq-001",
            failure_probability=0.0,
            predicted_failure_time=None,
            remaining_useful_life_hours=float("inf"),
            confidence_interval=(0.0, 0.0),
        )
        assert pred.time_to_failure_hours == float("inf")

    def test_to_dict(self):
        """测试转换为字典"""
        pred = FailurePrediction(
            equipment_id="eq-001",
            failure_probability=0.6,
            predicted_failure_time=None,
            remaining_useful_life_hours=200.0,
            confidence_interval=(0.5, 0.7),
            risk_factors=["temperature_high"],
            recommended_actions=["检查冷却"],
        )
        d = pred.to_dict()
        assert d["equipment_id"] == "eq-001"
        assert d["risk_level"] == "high"
        assert "temperature_high" in d["risk_factors"]


class TestYieldPrediction:
    """测试良率预测模型"""

    def test_creation(self):
        """测试创建YieldPrediction"""
        pred = YieldPrediction(
            batch_id="batch-001",
            predicted_yield=0.95,
            confidence_interval=(0.92, 0.98),
            key_influence_factors=[("temperature", 0.3)],
        )
        assert pred.batch_id == "batch-001"
        assert pred.predicted_yield == 0.95

    def test_yield_rate_percent(self):
        """测试百分比良率"""
        pred = YieldPrediction(
            batch_id="batch-001",
            predicted_yield=0.95,
            confidence_interval=(0.92, 0.98),
        )
        assert abs(pred.yield_rate_percent - 95.0) < 0.01

    def test_is_acceptable_true(self):
        """测试良率可接受"""
        pred = YieldPrediction(
            batch_id="batch-001",
            predicted_yield=0.97,
            confidence_interval=(0.95, 0.99),
        )
        assert pred.is_acceptable is True

    def test_is_acceptable_false(self):
        """测试良率不可接受"""
        pred = YieldPrediction(
            batch_id="batch-001",
            predicted_yield=0.85,
            confidence_interval=(0.80, 0.90),
        )
        assert pred.is_acceptable is False

    def test_to_dict(self):
        """测试转换为字典"""
        pred = YieldPrediction(
            batch_id="batch-001",
            predicted_yield=0.96,
            confidence_interval=(0.94, 0.98),
            feature_contributions={"temp": 0.01},
        )
        d = pred.to_dict()
        assert d["batch_id"] == "batch-001"
        assert d["is_acceptable"] is True


class TestRootCauseResult:
    """测试根因分析结果模型"""

    def test_creation(self):
        """测试创建RootCauseResult"""
        result = RootCauseResult(
            incident_id="incident-001",
            root_causes=[("temp_drift", 0.8), ("pressure_drop", 0.5)],
            propagation_path=["power_supply", "temp_drift", "shutdown"],
        )
        assert result.incident_id == "incident-001"
        assert len(result.root_causes) == 2

    def test_primary_cause(self):
        """测试主要根因"""
        result = RootCauseResult(
            incident_id="incident-001",
            root_causes=[("temp_drift", 0.8), ("pressure_drop", 0.5)],
        )
        assert result.primary_cause == ("temp_drift", 0.8)

    def test_no_primary_cause(self):
        """测试无根因"""
        result = RootCauseResult(
            incident_id="incident-001",
            root_causes=[],
        )
        assert result.primary_cause is None
        assert result.has_root_cause is False

    def test_has_root_cause(self):
        """测试有根因"""
        result = RootCauseResult(
            incident_id="incident-001",
            root_causes=[("temp_drift", 0.8)],
        )
        assert result.has_root_cause is True

    def test_to_dict(self):
        """测试转换为字典"""
        result = RootCauseResult(
            incident_id="incident-001",
            root_causes=[("temp_drift", 0.8)],
            propagation_path=["A", "B", "C"],
        )
        d = result.to_dict()
        assert d["incident_id"] == "incident-001"
        assert d["primary_cause"]["cause"] == "temp_drift"


class TestProcessParameter:
    """测试工艺参数模型"""

    def test_creation(self):
        """测试创建ProcessParameter"""
        param = ProcessParameter(
            name="temperature",
            value=150.0,
            target=150.0,
            tolerance_upper=5.0,
            tolerance_lower=5.0,
        )
        assert param.name == "temperature"
        assert param.value == 150.0

    def test_deviation(self):
        """测试偏差计算"""
        param = ProcessParameter(
            name="temperature",
            value=155.0,
            target=150.0,
        )
        assert param.deviation == 5.0

    def test_no_deviation(self):
        """测试无目标值的偏差"""
        param = ProcessParameter(
            name="temperature",
            value=150.0,
        )
        assert param.deviation is None

    def test_is_within_tolerance_true(self):
        """测试在公差范围内"""
        param = ProcessParameter(
            name="temperature",
            value=152.0,
            target=150.0,
            tolerance_upper=5.0,
            tolerance_lower=5.0,
        )
        assert param.is_within_tolerance is True

    def test_is_within_tolerance_false(self):
        """测试超出公差范围"""
        param = ProcessParameter(
            name="temperature",
            value=160.0,
            target=150.0,
            tolerance_upper=5.0,
            tolerance_lower=5.0,
        )
        assert param.is_within_tolerance is False


class TestPredictionConfidence:
    """测试预测置信度枚举"""

    def test_from_score_high(self):
        """测试高置信度"""
        assert PredictionConfidence.from_score(0.9) == PredictionConfidence.HIGH

    def test_from_score_medium(self):
        """测试中置信度"""
        assert PredictionConfidence.from_score(0.6) == PredictionConfidence.MEDIUM

    def test_from_score_low(self):
        """测试低置信度"""
        assert PredictionConfidence.from_score(0.3) == PredictionConfidence.LOW

    def test_from_score_boundary(self):
        """测试边界值"""
        assert PredictionConfidence.from_score(0.8) == PredictionConfidence.HIGH
        assert PredictionConfidence.from_score(0.5) == PredictionConfidence.MEDIUM


class TestAnomalyPattern:
    """测试异常模式模型"""

    def test_creation(self):
        """测试创建AnomalyPattern"""
        pattern = AnomalyPattern(
            pattern_id="ap-001",
            equipment_id="eq-001",
            feature_signature={"temp": 0.8, "pressure": 0.3},
            occurrence_count=3,
        )
        assert pattern.pattern_id == "ap-001"
        assert pattern.occurrence_count == 3

    def test_increment_occurrence(self):
        """测试增加出现次数"""
        pattern = AnomalyPattern(
            pattern_id="ap-001",
            equipment_id="eq-001",
            occurrence_count=1,
        )
        pattern.increment_occurrence()
        assert pattern.occurrence_count == 2
        assert pattern.last_seen is not None


class TestTrainingResult:
    """测试训练结果模型"""

    def test_creation(self):
        """测试创建TrainingResult"""
        result = TrainingResult(
            model_name="test_model",
            status=AnalysisStatus.COMPLETED,
            training_time_seconds=10.5,
            metrics={"r_squared": 0.85},
            data_points_count=100,
        )
        assert result.model_name == "test_model"
        assert result.is_successful is True

    def test_failed_training(self):
        """测试训练失败"""
        result = TrainingResult(
            model_name="test_model",
            status=AnalysisStatus.FAILED,
        )
        assert result.is_successful is False

    def test_to_dict(self):
        """测试转换为字典"""
        result = TrainingResult(
            model_name="test_model",
            status=AnalysisStatus.COMPLETED,
            metrics={"accuracy": 0.9},
            data_points_count=50,
        )
        d = result.to_dict()
        assert d["model_name"] == "test_model"
        assert d["data_points_count"] == 50


class TestEquipmentHealthReport:
    """测试设备健康报告模型"""

    def test_creation(self):
        """测试创建EquipmentHealthReport"""
        report = EquipmentHealthReport(
            equipment_id="eq-001",
            health_score=85.0,
            active_alerts=0,
            trend="stable",
        )
        assert report.equipment_id == "eq-001"
        assert report.health_score == 85.0
        assert report.health_status == "good"

    def test_health_status_good(self):
        """测试健康状态 - good"""
        report = EquipmentHealthReport(
            equipment_id="eq-001",
            health_score=90.0,
        )
        assert report.health_status == "good"

    def test_health_status_fair(self):
        """测试健康状态 - fair"""
        report = EquipmentHealthReport(
            equipment_id="eq-001",
            health_score=70.0,
        )
        assert report.health_status == "fair"

    def test_health_status_poor(self):
        """测试健康状态 - poor"""
        report = EquipmentHealthReport(
            equipment_id="eq-001",
            health_score=45.0,
        )
        assert report.health_status == "poor"

    def test_health_status_critical(self):
        """测试健康状态 - critical"""
        report = EquipmentHealthReport(
            equipment_id="eq-001",
            health_score=15.0,
        )
        assert report.health_status == "critical"

    def test_to_dict(self):
        """测试转换为字典"""
        report = EquipmentHealthReport(
            equipment_id="eq-001",
            health_score=75.0,
        )
        d = report.to_dict()
        assert d["equipment_id"] == "eq-001"
        assert d["health_status"] == "fair"


class TestMaintenanceRecommendation:
    """测试维护建议模型"""

    def test_creation(self):
        """测试创建MaintenanceRecommendation"""
        rec = MaintenanceRecommendation(
            equipment_id="eq-001",
            priority=1,
            action="更换冷却泵",
            reason="温度异常偏高",
        )
        assert rec.is_urgent is True

    def test_not_urgent(self):
        """测试非紧急"""
        rec = MaintenanceRecommendation(
            equipment_id="eq-001",
            priority=3,
            action="常规维护",
            reason="定期检查",
        )
        assert rec.is_urgent is False


def run_all_tests():
    """运行所有测试"""
    test_classes = [
        TestFailurePrediction,
        TestYieldPrediction,
        TestRootCauseResult,
        TestProcessParameter,
        TestPredictionConfidence,
        TestAnomalyPattern,
        TestTrainingResult,
        TestEquipmentHealthReport,
        TestMaintenanceRecommendation,
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
