"""FDC模型测试"""

import unittest
from datetime import datetime, timezone
from myeap.fdc.models import (
    Fault,
    FaultType,
    FaultSeverity,
    FaultStatus,
    FaultCategory,
    DetectionResult,
    FaultClassification,
    FDCEvent,
    FDCEventType,
)


class TestFaultType(unittest.TestCase):
    """测试故障类型枚举"""

    def test_fault_types_exist(self):
        """测试所有故障类型都存在"""
        self.assertIsNotNone(FaultType.TEMP_DRIFT)
        self.assertIsNotNone(FaultType.TEMP_SPIKE)
        self.assertIsNotNone(FaultType.PRESSURE_DRIFT)
        self.assertIsNotNone(FaultType.GAS_LEAK)
        self.assertIsNotNone(FaultType.PLASMA_EXTINCTION)

    def test_fault_type_values(self):
        """测试故障类型值"""
        self.assertEqual(FaultType.TEMP_DRIFT.value, "temp_drift")
        self.assertEqual(FaultType.PRESSURE_DRIFT.value, "pressure_drift")
        self.assertEqual(FaultType.GAS_LEAK.value, "gas_leak")


class TestFaultSeverity(unittest.TestCase):
    """测试故障严重程度"""

    def test_severity_priority(self):
        """测试严重程度优先级"""
        self.assertEqual(FaultSeverity.FATAL.priority, 1)
        self.assertEqual(FaultSeverity.CRITICAL.priority, 2)
        self.assertEqual(FaultSeverity.WARNING.priority, 3)
        self.assertEqual(FaultSeverity.INFO.priority, 4)

    def test_severity_order(self):
        """测试严重程度排序"""
        severities = [
            FaultSeverity.INFO,
            FaultSeverity.WARNING,
            FaultSeverity.CRITICAL,
            FaultSeverity.FATAL,
        ]
        sorted_severities = sorted(severities, key=lambda s: s.priority)
        self.assertEqual(
            sorted_severities,
            [
                FaultSeverity.FATAL,
                FaultSeverity.CRITICAL,
                FaultSeverity.WARNING,
                FaultSeverity.INFO,
            ],
        )


class TestFaultCategory(unittest.TestCase):
    """测试故障类别"""

    def test_category_from_fault_type(self):
        """测试从故障类型获取类别"""
        self.assertEqual(
            FaultCategory.from_fault_type(FaultType.TEMP_DRIFT),
            FaultCategory.TEMPERATURE,
        )
        self.assertEqual(
            FaultCategory.from_fault_type(FaultType.PRESSURE_DRIFT),
            FaultCategory.PRESSURE,
        )
        self.assertEqual(
            FaultCategory.from_fault_type(FaultType.GAS_FLOW_ERROR),
            FaultCategory.GAS,
        )
        self.assertEqual(
            FaultCategory.from_fault_type(FaultType.PLASMA_UNSTABLE),
            FaultCategory.PLASMA,
        )
        self.assertEqual(
            FaultCategory.from_fault_type(FaultType.ENDPOINT_EARLY),
            FaultCategory.PROCESS,
        )


class TestFault(unittest.TestCase):
    """测试故障模型"""

    def test_create_fault(self):
        """测试创建故障"""
        fault = Fault(
            fault_id="test-001",
            fault_type=FaultType.TEMP_DRIFT,
            severity=FaultSeverity.WARNING,
            equipment_id="eq-001",
            chamber_id="ch-1",
            start_time=datetime.now(timezone.utc),
            confidence=0.85,
            recommendations=["检查温度传感器", "检查加热器"],
        )

        self.assertEqual(fault.fault_id, "test-001")
        self.assertEqual(fault.fault_type, FaultType.TEMP_DRIFT)
        self.assertEqual(fault.severity, FaultSeverity.WARNING)
        self.assertTrue(fault.is_active)

    def test_fault_duration(self):
        """测试故障持续时间"""
        start = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 10, 30, 0, tzinfo=timezone.utc)

        fault = Fault(
            fault_id="test-002",
            fault_type=FaultType.TEMP_SPIKE,
            severity=FaultSeverity.CRITICAL,
            equipment_id="eq-001",
            start_time=start,
            end_time=end,
        )

        self.assertEqual(fault.duration, 1800.0)

    def test_resolve_fault(self):
        """测试解决故障"""
        fault = Fault(
            fault_id="test-003",
            fault_type=FaultType.PRESSURE_DROP,
            severity=FaultSeverity.WARNING,
            equipment_id="eq-001",
            start_time=datetime.now(timezone.utc),
        )

        self.assertTrue(fault.is_active)
        fault.resolve()
        self.assertFalse(fault.is_active)
        self.assertEqual(fault.status, FaultStatus.RESOLVED)

    def test_dismiss_fault(self):
        """测试忽略故障"""
        fault = Fault(
            fault_id="test-004",
            fault_type=FaultType.TEMP_OSCILLATION,
            severity=FaultSeverity.INFO,
            equipment_id="eq-001",
            start_time=datetime.now(timezone.utc),
        )

        fault.dismiss("误报")
        self.assertEqual(fault.status, FaultStatus.DISMISSED)
        self.assertEqual(fault.metadata.get("dismiss_reason"), "误报")

    def test_fault_to_dict(self):
        """测试故障转字典"""
        fault = Fault(
            fault_id="test-005",
            fault_type=FaultType.RF_POWER_ERROR,
            severity=FaultSeverity.CRITICAL,
            equipment_id="eq-001",
            start_time=datetime(2024, 1, 1, 12, 0, 0),
        )

        d = fault.to_dict()
        self.assertEqual(d["fault_id"], "test-005")
        self.assertEqual(d["fault_type"], "rf_power_error")
        self.assertEqual(d["severity"], "critical")
        self.assertEqual(d["category"], "equipment")


class TestDetectionResult(unittest.TestCase):
    """测试检测结果"""

    def test_create_detection_result(self):
        """测试创建检测结果"""
        result = DetectionResult(
            is_anomaly=True,
            score=0.85,
            z_scores=[1.2, 2.5, 3.8],
            anomaly_indices=[2],
        )

        self.assertTrue(result.is_anomaly)
        self.assertEqual(result.score, 0.85)
        self.assertEqual(len(result.z_scores), 3)
        self.assertEqual(result.anomaly_indices, [2])


class TestFaultClassification(unittest.TestCase):
    """测试故障分类"""

    def test_create_classification(self):
        """测试创建分类结果"""
        classification = FaultClassification(
            fault_type=FaultType.GAS_LEAK,
            confidence=0.92,
            matched_rule="gas_leak_rule",
        )

        self.assertEqual(classification.fault_type, FaultType.GAS_LEAK)
        self.assertEqual(classification.confidence, 0.92)
        self.assertEqual(classification.matched_rule, "gas_leak_rule")


class TestFDCEvent(unittest.TestCase):
    """测试FDC事件"""

    def test_create_event(self):
        """测试创建事件"""
        event = FDCEvent(
            event_type=FDCEventType.FAULT_DETECTED,
            equipment_id="eq-001",
            chamber_id="ch-1",
            data={"temperature": 150.0},
        )

        self.assertEqual(event.event_type, "fault_detected")
        self.assertEqual(event.equipment_id, "eq-001")


if __name__ == "__main__":
    unittest.main()
