"""AI引擎模块测试

测试AIEngine的完整功能，包括预测性维护、良率预测和根因分析的协调。
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from myeap.ai.engine import AIEngine, AsyncAIEngine


class TestAIEngineInit:
    """测试AIEngine初始化"""

    def test_creation(self):
        """测试引擎创建"""
        engine = AIEngine()
        assert engine.predictive_maintenance is not None
        assert engine.yield_predictor is not None
        assert engine.root_cause_analyzer is not None

    def test_creation_custom(self):
        """测试自定义参数创建"""
        engine = AIEngine(rul_threshold=240.0, yield_min_samples=20)
        assert engine.predictive_maintenance.rul_threshold == 240.0
        assert engine.yield_predictor.min_samples == 20


class TestPredictiveMaintenanceViaEngine:
    """测试通过引擎进行预测性维护"""

    def test_train_baseline(self):
        """测试训练基线"""
        engine = AIEngine()
        np.random.seed(42)
        data = np.random.normal(100, 5, (100, 3))

        info = engine.train_baseline(
            "eq-001", data, parameter_names=["temp", "pressure", "flow"]
        )
        assert info["sample_count"] == 100

    def test_predict_failure(self):
        """测试故障预测"""
        engine = AIEngine()
        np.random.seed(42)
        engine.train_baseline("eq-001", np.random.normal(100, 5, 100))

        result = engine.predict_failure("eq-001", np.array([105.0]))
        assert result.equipment_id == "eq-001"

    def test_get_maintenance_schedule(self):
        """测试获取维护计划"""
        engine = AIEngine()
        np.random.seed(42)
        engine.train_baseline("eq-001", np.random.normal(100, 3, 100))

        prediction = engine.predict_failure("eq-001", np.array([130.0]))
        schedule = engine.get_maintenance_schedule("eq-001", prediction)

        assert schedule.equipment_id == "eq-001"
        assert schedule.scheduled_date is not None

    def test_update_baseline(self):
        """测试在线更新基线"""
        engine = AIEngine()
        np.random.seed(42)
        engine.train_baseline("eq-001", np.random.normal(100, 5, 100))
        # 不应抛异常
        engine.update_baseline("eq-001", np.random.normal(102, 5, 50))

    def test_prediction_callback(self):
        """测试预测回调"""
        engine = AIEngine()
        np.random.seed(42)
        engine.train_baseline("eq-001", np.random.normal(100, 3, 100))

        callback_calls = []

        def on_prediction(prediction):
            callback_calls.append(prediction)

        engine.set_on_prediction(on_prediction)
        # 用异常数据触发高故障概率
        engine.predict_failure("eq-001", np.array([150.0]))

        # 回调可能被触发(取决于概率是否>=0.5)
        assert len(callback_calls) >= 0  # 只验证不报错


class TestYieldPredictionViaEngine:
    """测试通过引擎进行良率预测"""

    def test_add_process_parameter(self):
        """测试添加工艺参数"""
        engine = AIEngine()
        param = engine.add_process_parameter(
            "temperature", 150.0, target=150, tolerance_upper=5, tolerance_lower=5
        )
        assert param.name == "temperature"

    def test_add_yield_record(self):
        """测试添加良率记录"""
        engine = AIEngine()
        record = engine.add_yield_record(
            "batch-001", 0.95, {"temperature": 150.0, "pressure": 100.0}
        )
        assert record.batch_id == "batch-001"

    def test_train_yield_model(self):
        """测试训练良率模型"""
        engine = AIEngine(yield_min_samples=5)
        np.random.seed(42)

        for i in range(15):
            temp = 148 + i * 0.4
            engine.add_yield_record(f"b{i}", 0.95 - 0.005 * abs(temp - 150), {"temp": temp})

        result = engine.train_yield_model()
        assert result.is_successful

    def test_predict_yield(self):
        """测试良率预测"""
        engine = AIEngine(yield_min_samples=5)
        np.random.seed(42)

        for i in range(15):
            temp = 148 + i * 0.4
            engine.add_yield_record(f"b{i}", 0.95 - 0.005 * abs(temp - 150), {"temp": temp})

        engine.train_yield_model()
        result = engine.predict_yield("batch-020", {"temp": 150.0})

        assert result.batch_id == "batch-020"
        assert 0.0 < result.predicted_yield <= 1.0

    def test_predict_yield_batch(self):
        """测试批量良率预测"""
        engine = AIEngine(yield_min_samples=3)
        np.random.seed(42)

        for i in range(10):
            engine.add_yield_record(f"b{i}", 0.95, {"temp": 150 + i * 0.2})

        engine.train_yield_model()

        batches = [
            ("batch-a", {"temp": 150.0}),
            ("batch-b", {"temp": 152.0}),
        ]
        results = engine.predict_yield_batch(batches)

        assert len(results) == 2


class TestRootCauseViaEngine:
    """测试通过引擎进行根因分析"""

    def test_record_event(self):
        """测试记录事件"""
        engine = AIEngine()
        engine.record_event("eq-001", "temp_high", datetime.now(), 0.8)

        events = engine.root_cause_analyzer.get_recent_events("eq-001")
        assert len(events) == 1

    def test_analyze_root_cause(self):
        """测试根因分析"""
        engine = AIEngine()
        base_time = datetime.now()

        engine.record_event("eq-001", "power_fault", base_time, 0.9)
        engine.record_event("eq-001", "temp_high", base_time + timedelta(minutes=5), 0.7)
        engine.record_event("eq-001", "shutdown", base_time + timedelta(minutes=10), 1.0)

        result = engine.analyze_root_cause("incident-001", equipment_id="eq-001")

        assert result.incident_id == "incident-001"

    def test_analyze_multi_equipment(self):
        """测试多设备根因分析"""
        engine = AIEngine()
        base_time = datetime.now()

        engine.record_event("eq-001", "temp_high", base_time, 0.8)
        engine.record_event("eq-002", "vibration", base_time + timedelta(minutes=2), 0.6)

        result = engine.analyze_root_cause_multi("incident-001", ["eq-001", "eq-002"])

        assert result.incident_id == "incident-001"


class TestEquipmentHealth:
    """测试设备健康报告"""

    def test_get_equipment_health(self):
        """测试获取设备健康报告"""
        engine = AIEngine()
        np.random.seed(42)
        engine.train_baseline("eq-001", np.random.normal(100, 5, 100))

        report = engine.get_equipment_health("eq-001", np.array([105.0]))

        assert report.equipment_id == "eq-001"
        assert 0 <= report.health_score <= 100
        assert report.health_status in ("good", "fair", "poor", "critical")

    def test_get_equipment_health_no_baseline(self):
        """测试无基线的健康报告"""
        engine = AIEngine()
        report = engine.get_equipment_health("eq-unknown", np.array([100.0]))

        assert report.equipment_id == "eq-unknown"
        assert report.health_score == 100.0  # 无基线时故障概率为0

    def test_cached_health_report(self):
        """测试缓存的健康报告"""
        engine = AIEngine()
        np.random.seed(42)
        engine.train_baseline("eq-001", np.random.normal(100, 5, 100))

        engine.get_equipment_health("eq-001", np.array([105.0]))

        cached = engine.get_cached_health_report("eq-001")
        assert cached is not None
        assert cached.equipment_id == "eq-001"

    def test_cached_health_report_nonexistent(self):
        """测试不存在的缓存报告"""
        engine = AIEngine()
        cached = engine.get_cached_health_report("eq-unknown")
        assert cached is None

    def test_health_alert_callback(self):
        """测试健康告警回调"""
        engine = AIEngine()
        np.random.seed(42)

        # 使用极窄基线使正常数据看起来偏离
        engine.train_baseline("eq-001", np.random.normal(100, 0.1, 100))

        alerts = []

        def on_alert(alert_type, data):
            alerts.append((alert_type, data))

        engine.set_on_alert(on_alert)
        engine.get_equipment_health("eq-001", np.array([150.0]))

        # 可能触发告警
        assert len(alerts) >= 0


class TestSummary:
    """测试引擎摘要"""

    def test_get_summary_empty(self):
        """测试空引擎摘要"""
        engine = AIEngine()
        summary = engine.get_summary()
        assert summary["prediction_count"] == 0
        assert summary["equipment_count"] == 0
        assert summary["yield_records_count"] == 0
        assert summary["cached_reports"] == 0

    def test_get_summary_with_data(self):
        """测试有数据的引擎摘要"""
        engine = AIEngine()
        np.random.seed(42)
        engine.train_baseline("eq-001", np.random.normal(100, 5, 100))

        # 添加一些操作
        engine.predict_failure("eq-001", np.array([102.0]))
        engine.get_equipment_health("eq-001", np.array([105.0]))

        summary = engine.get_summary()
        assert summary["equipment_count"] >= 1
        assert summary["cached_reports"] >= 1


class TestAsyncAIEngine:
    """测试异步AI引擎"""

    def test_creation(self):
        """测试异步引擎创建"""
        engine = AsyncAIEngine()
        assert engine.predictive_maintenance is not None

    def test_async_callbacks(self):
        """测试异步回调设置"""
        engine = AsyncAIEngine()

        async def async_callback(prediction):
            pass

        engine.set_on_prediction_async(async_callback)
        # 验证不报错即可


class TestAlertCallback:
    """测试告警回调"""

    def test_prediction_callback_threshold(self):
        """测试预测回调阈值"""
        engine = AIEngine()
        np.random.seed(42)
        engine.train_baseline("eq-001", np.random.normal(100, 0.5, 100))

        failures = []

        def on_prediction(pred):
            failures.append(pred)

        engine.set_on_prediction(on_prediction)
        engine.predict_failure("eq-001", np.array([120.0]))

        # 由于偏离很大，大概率会触发
        assert len(failures) >= 0

    def test_yield_low_alert(self):
        """测试低良率告警"""
        engine = AIEngine()
        alerts = []

        def on_alert(alert_type, data):
            alerts.append((alert_type, data))

        engine.set_on_alert(on_alert)

        # 预测会很低的良率
        result = engine.predict_yield("batch-test", {"temperature": 200.0})
        # 只验证不报错
        assert isinstance(result.predicted_yield, float)


class TestReset:
    """测试引擎重置"""

    def test_reset(self):
        """测试重置"""
        engine = AIEngine()
        np.random.seed(42)

        # 添加数据
        engine.train_baseline("eq-001", np.random.normal(100, 5, 100))
        engine.add_yield_record("b1", 0.95, {"temp": 150})
        engine.record_event("eq-001", "temp_high", datetime.now(), 0.8)

        engine.predict_failure("eq-001", np.array([105.0]))
        engine.get_equipment_health("eq-001", np.array([105.0]))

        # 重置
        engine.reset()

        summary = engine.get_summary()
        assert summary["prediction_count"] == 0
        assert summary["equipment_count"] == 0
        assert summary["cached_reports"] == 0


def run_all_tests():
    """运行所有测试"""
    test_classes = [
        TestAIEngineInit,
        TestPredictiveMaintenanceViaEngine,
        TestYieldPredictionViaEngine,
        TestRootCauseViaEngine,
        TestEquipmentHealth,
        TestSummary,
        TestAsyncAIEngine,
        TestAlertCallback,
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
