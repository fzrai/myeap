"""预测性维护模块测试

测试PredictiveMaintenance和MaintenanceSchedule。
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from myeap.ai.predictive_maintenance import (
    MaintenanceSchedule,
    PredictiveMaintenance,
    get_default_maintenance_recommendations,
)


class TestPredictiveMaintenanceInit:
    """测试PredictiveMaintenance初始化"""

    def test_creation(self):
        """测试引擎创建"""
        pm = PredictiveMaintenance()
        assert pm.rul_threshold == 168.0
        assert pm.degradation_rate_threshold == 0.01

    def test_creation_with_custom_threshold(self):
        """测试自定义RUL阈值"""
        pm = PredictiveMaintenance(rul_threshold=240.0)
        assert pm.rul_threshold == 240.0


class TestTrainBaseline:
    """测试基线训练"""

    def test_train_baseline_1d(self):
        """测试一维数据基线训练"""
        pm = PredictiveMaintenance()
        np.random.seed(42)
        data = np.random.normal(100, 5, 100)

        info = pm.train_baseline("eq-001", data)

        assert info["sample_count"] == 100
        assert "mean" in info
        assert "std" in info

    def test_train_baseline_2d(self):
        """测试多维数据基线训练"""
        pm = PredictiveMaintenance()
        np.random.seed(42)
        data = np.random.normal(100, 5, (100, 3))

        info = pm.train_baseline(
            "eq-001",
            data,
            parameter_names=["temperature", "pressure", "flow"],
        )

        assert info["sample_count"] == 100
        assert info["parameter_names"] == ["temperature", "pressure", "flow"]

    def test_train_baseline_empty_data(self):
        """测试空数据基线训练"""
        pm = PredictiveMaintenance()
        try:
            pm.train_baseline("eq-001", np.array([]))
            assert False, "Should raise ValueError"
        except ValueError:
            pass


class TestPredictFailure:
    """测试故障预测"""

    def test_predict_no_baseline(self):
        """测试无基线时的预测"""
        pm = PredictiveMaintenance()
        result = pm.predict_failure("eq-001", np.array([100.0]))

        assert result.equipment_id == "eq-001"
        assert result.failure_probability == 0.0
        assert result.remaining_useful_life_hours == float("inf")
        assert result.predicted_failure_time is None

    def test_predict_normal_data(self):
        """测试正常数据的预测"""
        pm = PredictiveMaintenance()
        np.random.seed(42)
        normal_data = np.random.normal(100, 5, 100)
        pm.train_baseline("eq-001", normal_data)

        result = pm.predict_failure("eq-001", np.array([102.0]))

        assert result.equipment_id == "eq-001"
        assert result.failure_probability < 0.5

    def test_predict_anomalous_data(self):
        """测试异常数据的预测"""
        pm = PredictiveMaintenance()
        np.random.seed(42)
        normal_data = np.random.normal(100, 3, 100)
        pm.train_baseline("eq-001", normal_data)

        # 明显偏离基线的数据
        result = pm.predict_failure("eq-001", np.array([130.0]))

        assert result.failure_probability > 0.0
        assert len(result.risk_factors) > 0

    def test_predict_multi_dimension(self):
        """测试多维数据预测"""
        pm = PredictiveMaintenance()
        np.random.seed(42)
        normal_data = np.random.normal(100, 5, (100, 3))
        pm.train_baseline(
            "eq-001",
            normal_data,
            parameter_names=["temperature", "pressure", "flow"],
        )

        result = pm.predict_failure("eq-001", np.array([120, 105, 98]))

        assert result.equipment_id == "eq-001"
        assert isinstance(result.risk_factors, list)

    def test_predict_multiple_equipment(self):
        """测试多设备预测"""
        pm = PredictiveMaintenance()
        np.random.seed(42)

        pm.train_baseline("eq-001", np.random.normal(100, 5, 100))
        pm.train_baseline("eq-002", np.random.normal(200, 10, 100))

        result1 = pm.predict_failure("eq-001", np.array([108.0]))
        result2 = pm.predict_failure("eq-002", np.array([220.0]))

        assert result1.equipment_id == "eq-001"
        assert result2.equipment_id == "eq-002"

    def test_predict_returns_recommendations(self):
        """测试预测返回建议措施"""
        pm = PredictiveMaintenance()
        np.random.seed(42)
        normal_data = np.random.normal(100, 3, 100)
        pm.train_baseline("eq-001", normal_data)

        # 制造严重异常
        result = pm.predict_failure("eq-001", np.array([160.0]))

        assert len(result.recommended_actions) > 0


class TestUpdateBaseline:
    """测试在线更新基线"""

    def test_update_baseline(self):
        """测试在线更新"""
        pm = PredictiveMaintenance()
        np.random.seed(42)
        pm.train_baseline("eq-001", np.random.normal(100, 5, 100))

        # 在线更新
        pm.update_baseline("eq-001", np.random.normal(102, 5, 50), learning_rate=0.1)

        # 应该不抛异常
        baseline = pm._baselines["eq-001"]
        assert baseline["sample_count"] == 100  # 保持样本数不变

    def test_update_baseline_no_existing(self):
        """测试更新不存在的基线"""
        pm = PredictiveMaintenance()
        try:
            pm.update_baseline("eq-001", np.array([100.0]))
            assert False, "Should raise ValueError"
        except ValueError:
            pass


class TestMaintenanceSchedule:
    """测试维护计划"""

    def test_get_maintenance_schedule(self):
        """测试获取维护计划"""
        pm = PredictiveMaintenance()
        np.random.seed(42)
        pm.train_baseline("eq-001", np.random.normal(100, 3, 100))

        prediction = pm.predict_failure("eq-001", np.array([130.0]))
        schedule = pm.get_maintenance_schedule("eq-001", prediction)

        assert schedule.equipment_id == "eq-001"
        assert schedule.scheduled_date is not None
        assert isinstance(schedule.maintenance_type, str)

    def test_schedule_high_priority(self):
        """测试高优先级计划"""
        pm = PredictiveMaintenance()
        np.random.seed(42)
        pm.train_baseline("eq-001", np.random.normal(100, 3, 100))

        prediction = pm.predict_failure("eq-001", np.array([150.0]))
        schedule = pm.get_maintenance_schedule("eq-001", prediction)

        # 高故障概率应该有较高优先级
        assert schedule.priority <= 3


class TestBatchPredict:
    """测试批量预测"""

    def test_batch_predict(self):
        """测试批量预测"""
        pm = PredictiveMaintenance()
        np.random.seed(42)

        pm.train_baseline("eq-001", np.random.normal(100, 5, 100))
        pm.train_baseline("eq-002", np.random.normal(200, 10, 100))

        equipment_data = {
            "eq-001": np.array([102.0]),
            "eq-002": np.array([205.0]),
        }

        results = pm.batch_predict(equipment_data)

        assert len(results) == 2
        assert results[0].equipment_id == "eq-001"
        assert results[1].equipment_id == "eq-002"


class TestEquipmentStatus:
    """测试设备状态"""

    def test_get_equipment_status_no_baseline(self):
        """测试无基线设备状态"""
        pm = PredictiveMaintenance()
        status = pm.get_equipment_status("eq-unknown")

        assert status["equipment_id"] == "eq-unknown"
        assert status["has_baseline"] is False

    def test_get_equipment_status_with_data(self):
        """测试有数据的设备状态"""
        pm = PredictiveMaintenance()
        np.random.seed(42)
        pm.train_baseline("eq-001", np.random.normal(100, 5, 100))

        # 添加一些数据点
        for _ in range(5):
            pm.predict_failure("eq-001", np.array([100.0 + np.random.randn() * 5]))

        status = pm.get_equipment_status("eq-001")

        assert status["has_baseline"] is True
        assert status["baseline_samples"] == 100


class TestDefaultRecommendations:
    """测试默认建议"""

    def test_get_default_recommendations(self):
        """测试默认建议生成"""
        recs = get_default_maintenance_recommendations(
            "eq-001",
            ["temperature_high", "vibration_high"],
        )
        assert len(recs) > 0
        assert recs[0].equipment_id == "eq-001"

    def test_empty_risk_factors(self):
        """测试空风险因素"""
        recs = get_default_maintenance_recommendations("eq-001", [])
        assert len(recs) == 0


class TestReset:
    """测试重置"""

    def test_reset(self):
        """测试重置引擎"""
        pm = PredictiveMaintenance()
        np.random.seed(42)
        pm.train_baseline("eq-001", np.random.normal(100, 5, 100))

        assert len(pm._baselines) == 1

        pm.reset()

        assert len(pm._baselines) == 0
        assert len(pm._trend_data) == 0


def run_all_tests():
    """运行所有测试"""
    test_classes = [
        TestPredictiveMaintenanceInit,
        TestTrainBaseline,
        TestPredictFailure,
        TestUpdateBaseline,
        TestMaintenanceSchedule,
        TestBatchPredict,
        TestEquipmentStatus,
        TestDefaultRecommendations,
        TestReset,
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
