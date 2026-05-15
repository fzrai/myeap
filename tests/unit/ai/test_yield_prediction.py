"""良率预测模块测试

测试YieldPredictor和FeatureImportance。
"""

import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from myeap.ai.models import ProcessParameter, PredictionConfidence
from myeap.ai.yield_prediction import (
    BatchYieldRecord,
    FeatureImportance,
    YieldPredictor,
    get_default_process_parameters,
)


class TestYieldPredictorInit:
    """测试YieldPredictor初始化"""

    def test_creation(self):
        """测试创建"""
        yp = YieldPredictor()
        assert yp.min_samples == 10
        assert yp.confidence_width == 0.05

    def test_creation_custom(self):
        """测试自定义参数创建"""
        yp = YieldPredictor(min_samples=20, confidence_width=0.03)
        assert yp.min_samples == 20


class TestProcessParameterManagement:
    """测试工艺参数管理"""

    def test_add_parameter(self):
        """测试添加参数"""
        yp = YieldPredictor()
        param = yp.add_process_parameter(
            "temperature", 150.0, target=150, tolerance_upper=5, tolerance_lower=5
        )
        assert param.name == "temperature"
        assert param.target == 150

    def test_add_multiple_parameters(self):
        """测试添加多个参数"""
        yp = YieldPredictor()
        yp.add_process_parameter("temperature", 150.0, target=150)
        yp.add_process_parameter("pressure", 100.0, target=100)
        yp.add_process_parameter("rf_power", 500.0, target=500)

        assert len(yp._parameters) == 3
        assert len(yp._param_order) == 3

    def test_remove_parameter(self):
        """测试移除参数"""
        yp = YieldPredictor()
        yp.add_process_parameter("temperature", 150.0)
        assert yp.remove_process_parameter("temperature") is True
        assert yp.remove_process_parameter("nonexistent") is False
        assert len(yp._parameters) == 0


class TestYieldRecords:
    """测试良率记录管理"""

    def test_add_yield_record(self):
        """测试添加良率记录"""
        yp = YieldPredictor()
        record = yp.add_yield_record(
            "batch-001", 0.95, {"temperature": 150, "pressure": 100}
        )
        assert record.batch_id == "batch-001"
        assert record.yield_rate == 0.95

    def test_add_yield_record_clips_value(self):
        """测试良率值限幅"""
        yp = YieldPredictor()
        record1 = yp.add_yield_record("batch-001", 1.5, {"temp": 150})
        record2 = yp.add_yield_record("batch-002", -0.5, {"temp": 150})

        assert 0.0 <= record1.yield_rate <= 1.0
        assert 0.0 <= record2.yield_rate <= 1.0

    def test_batch_records(self):
        """测试批量添加记录"""
        yp = YieldPredictor()
        records = [
            BatchYieldRecord("b1", 0.95, {"temp": 150}),
            BatchYieldRecord("b2", 0.92, {"temp": 155}),
            BatchYieldRecord("b3", 0.88, {"temp": 160}),
        ]
        yp.add_batch_records(records)
        assert len(yp._yield_records) == 3


class TestTraining:
    """测试模型训练"""

    def test_train_insufficient_data(self):
        """测试训练数据不足"""
        yp = YieldPredictor(min_samples=10)
        yp.add_yield_record("b1", 0.95, {"temp": 150})

        result = yp.train()
        assert not result.is_successful

    def test_train_with_sufficient_data(self):
        """测试充足数据训练"""
        yp = YieldPredictor(min_samples=5)
        np.random.seed(42)

        # 创建具有线性关系的训练数据
        for i in range(20):
            temp = 145 + i * 0.5
            yield_rate = 0.98 - 0.01 * abs(temp - 150)
            yp.add_yield_record(f"batch-{i}", max(0.8, yield_rate), {"temp": temp})

        result = yp.train()
        assert result.is_successful
        assert result.metrics["r_squared"] > 0

    def test_train_no_parameters(self):
        """测试训练时无参数定义但数据足够"""
        yp = YieldPredictor(min_samples=3)
        # 直接添加有参数的记录
        for i in range(5):
            yp.add_yield_record(f"batch-{i}", 0.95, {"temp": 150, "pressure": 100})

        result = yp.train()
        assert result.is_successful


class TestPredictYield:
    """测试良率预测"""

    def test_predict_without_training(self):
        """测试未训练的预测"""
        yp = YieldPredictor()
        yp.add_process_parameter("temperature", 150.0, target=150, tolerance_upper=5, tolerance_lower=5)

        result = yp.predict_yield("batch-001", {"temperature": 152.0})

        assert result.batch_id == "batch-001"
        assert 0.0 < result.predicted_yield <= 1.0

    def test_predict_with_training(self):
        """测试训练后的预测"""
        yp = YieldPredictor(min_samples=5)
        np.random.seed(42)

        for i in range(20):
            temp = 148 + i * 0.4
            yp.add_yield_record(f"b{i}", 0.95 - 0.005 * abs(temp - 150), {"temp": temp})

        yp.train()
        result = yp.predict_yield("batch-020", {"temp": 150.0})

        assert result.batch_id == "batch-020"
        assert result.predicted_yield >= 0.8

    def test_predict_confidence_interval(self):
        """测试置信区间"""
        yp = YieldPredictor(min_samples=5)
        np.random.seed(42)

        for i in range(15):
            temp = 148 + i * 0.4
            yp.add_yield_record(f"b{i}", 0.95 - 0.005 * abs(temp - 150), {"temp": temp})

        yp.train()
        result = yp.predict_yield("batch-100", {"temp": 150.0})

        ci_lower, ci_upper = result.confidence_interval
        assert 0.0 <= ci_lower <= ci_upper <= 1.0

    def test_predict_batch(self):
        """测试批量预测"""
        yp = YieldPredictor(min_samples=5)
        np.random.seed(42)

        for i in range(10):
            yp.add_yield_record(f"b{i}", 0.95, {"temp": 150 + i * 0.2})

        yp.train()

        batches = [
            ("batch-a", {"temp": 150.0}),
            ("batch-b", {"temp": 152.0}),
            ("batch-c", {"temp": 148.0}),
        ]
        results = yp.predict_yield_batch(batches)

        assert len(results) == 3
        for r in results:
            assert 0.0 < r.predicted_yield <= 1.0


class TestFeatureImportance:
    """测试特征重要性"""

    def test_feature_importance_creation(self):
        """测试创建FeatureImportance"""
        fi = FeatureImportance(
            parameter_name="temperature",
            importance_score=0.8,
            correlation=0.7,
            optimal_range=(148.0, 152.0),
        )
        assert fi.parameter_name == "temperature"
        assert fi.importance_score == 0.8

    def test_get_feature_importance(self):
        """测试获取特征重要性"""
        yp = YieldPredictor(min_samples=5)
        np.random.seed(42)

        for i in range(20):
            temp = 148 + i * 0.4
            yp.add_yield_record(f"b{i}", 0.95 - 0.005 * abs(temp - 150), {"temp": temp, "pressure": 100 + i * 0.1})

        yp.train()

        imp = yp.get_feature_importance("temp")
        assert imp is not None
        assert imp.parameter_name == "temp"

    def test_get_all_importance(self):
        """测试获取所有特征重要性"""
        yp = YieldPredictor(min_samples=5)
        np.random.seed(42)

        for i in range(15):
            yp.add_yield_record(f"b{i}", 0.95, {"temp": 150, "pressure": 100})

        yp.train()
        all_imp = yp.get_all_feature_importance()

        assert len(all_imp) > 0

    def test_get_nonexistent_importance(self):
        """测试获取不存在的特征重要性"""
        yp = YieldPredictor()
        assert yp.get_feature_importance("nonexistent") is None


class TestSensitivityAnalysis:
    """测试灵敏度分析"""

    def test_sensitivity_analysis(self):
        """测试参数灵敏度分析"""
        yp = YieldPredictor(min_samples=5)
        np.random.seed(42)

        for i in range(15):
            temp = 148 + i * 0.4
            yp.add_yield_record(f"b{i}", 0.95 - 0.005 * abs(temp - 150), {"temp": temp})

        yp.train()

        results = yp.get_sensitivity_analysis(
            "temp",
            {"temp": 150.0},
            variation_range=0.1,
            steps=5,
        )

        assert len(results) == 6  # steps + 1
        for val, pred_yield in results:
            assert 0.0 < pred_yield <= 1.0

    def test_sensitivity_unknown_parameter(self):
        """测试未知参数的灵敏度"""
        yp = YieldPredictor()
        results = yp.get_sensitivity_analysis("unknown", {"temp": 150})
        assert len(results) == 0


class TestStatistics:
    """测试统计信息"""

    def test_get_statistics_empty(self):
        """测试空的统计信息"""
        yp = YieldPredictor()
        stats = yp.get_statistics()
        assert stats["record_count"] == 0
        assert stats["is_trained"] is False

    def test_get_statistics_with_data(self):
        """测试有数据的统计信息"""
        yp = YieldPredictor(min_samples=3)
        for i in range(5):
            yp.add_yield_record(f"b{i}", 0.95, {"temp": 150})
        yp.train()

        stats = yp.get_statistics()
        assert stats["record_count"] == 5
        assert stats["is_trained"] is True


class TestDefaultParameters:
    """测试默认参数"""

    def test_get_default_parameters(self):
        """测试获取默认参数"""
        params = get_default_process_parameters()
        assert len(params) > 0
        assert isinstance(params[0], ProcessParameter)

    def test_default_params_have_targets(self):
        """测试默认参数有目标值"""
        params = get_default_process_parameters()
        for p in params:
            assert p.name
            assert p.target is not None


class TestBatchYieldRecord:
    """测试批次良率记录"""

    def test_to_feature_array(self):
        """测试转换为特征数组"""
        record = BatchYieldRecord(
            batch_id="b1",
            yield_rate=0.95,
            process_params={"temp": 150.0, "pressure": 100.0},
        )

        arr = record.to_feature_array(["temp", "pressure"])
        assert len(arr) == 2
        assert arr[0] == 150.0
        assert arr[1] == 100.0

    def test_missing_params_default_zero(self):
        """测试缺失参数默认为0"""
        record = BatchYieldRecord(
            batch_id="b1",
            yield_rate=0.95,
            process_params={"temp": 150.0},
        )

        arr = record.to_feature_array(["temp", "pressure"])
        assert arr[1] == 0.0


class TestReset:
    """测试重置"""

    def test_reset(self):
        """测试重置"""
        yp = YieldPredictor(min_samples=3)
        for i in range(5):
            yp.add_yield_record(f"b{i}", 0.95, {"temp": 150})
        yp.train()

        assert len(yp._yield_records) == 5
        assert yp._coefficients is not None

        yp.reset()

        assert len(yp._yield_records) == 0
        assert yp._coefficients is None
        assert len(yp._param_order) == 0


def run_all_tests():
    """运行所有测试"""
    test_classes = [
        TestYieldPredictorInit,
        TestProcessParameterManagement,
        TestYieldRecords,
        TestTraining,
        TestPredictYield,
        TestFeatureImportance,
        TestSensitivityAnalysis,
        TestStatistics,
        TestDefaultParameters,
        TestBatchYieldRecord,
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
