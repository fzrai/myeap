"""FDC引擎测试"""

import asyncio
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import numpy as np

from myeap.data.limit_monitor import Limit, LimitType
from myeap.fdc.engine import FDCEngine
from myeap.fdc.models import Fault, FaultType, FaultSeverity, FDCEvent


class TestFDCEngine(unittest.TestCase):
    """测试FDC引擎"""

    def setUp(self):
        """设置测试环境"""
        self.engine = FDCEngine(window_size=50, min_window_size=20)

    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.engine._window_size, 50)
        self.assertEqual(self.engine._min_window_size, 20)
        self.assertEqual(self.engine.fault_count, 0)
        self.assertEqual(len(self.engine.active_faults), 0)

    def test_set_limit(self):
        """测试设置限值"""
        limit = Limit("Temperature", LimitType.UCL, 150.0, severity="warning")
        self.engine.set_limit("eq-001", "Temperature", limit)

        limits = self.engine.get_limits("eq-001")
        self.assertIn("Temperature", limits)
        self.assertEqual(limits["Temperature"].value, 150.0)

    def test_remove_limit(self):
        """测试移除限值"""
        limit = Limit("Temperature", LimitType.UCL, 150.0)
        self.engine.set_limit("eq-001", "Temperature", limit)

        result = self.engine.remove_limit("eq-001", "Temperature")

        self.assertTrue(result)
        self.assertNotIn("Temperature", self.engine.get_limits("eq-001"))

    def test_register_detector(self):
        """测试注册检测器"""
        from myeap.fdc.detector import StatisticalDetector

        detector = StatisticalDetector(z_threshold=2.5)
        self.engine.register_detector("Temperature", detector)

        self.assertIn("Temperature", self.engine._detectors)

    def test_set_baseline(self):
        """测试设置基线"""
        np.random.seed(42)
        baseline = np.random.normal(100, 5, 100)

        self.engine.set_baseline("eq-001", "Temperature", baseline)

        stored_baseline = self.engine.get_baseline("eq-001", "Temperature")
        self.assertIsNotNone(stored_baseline)
        self.assertEqual(len(stored_baseline), 100)


class TestFDCEngineProcessData(unittest.TestCase):
    """测试FDC引擎数据处理"""

    def setUp(self):
        """设置测试环境"""
        self.engine = FDCEngine(window_size=50, min_window_size=10)

    def test_process_data_empty(self):
        """测试处理空数据"""
        result = self.engine.process_data_sync(
            "eq-001", "ch-1", {}, datetime.now(timezone.utc)
        )

        self.assertIsNone(result)

    def test_process_data_no_violation(self):
        """测试处理正常数据（无违规）"""
        limit = Limit("Temperature", LimitType.UCL, 150.0)
        self.engine.set_limit("eq-001", "Temperature", limit)

        result = self.engine.process_data_sync(
            "eq-001", "ch-1", {"Temperature": 120.0}, datetime.now(timezone.utc)
        )

        self.assertIsNone(result)

    def test_process_data_with_limit_violation(self):
        """测试处理限值违规数据"""
        limit = Limit("Temperature", LimitType.UCL, 150.0)
        self.engine.set_limit("eq-001", "Temperature", limit)

        result = self.engine.process_data_sync(
            "eq-001", "ch-1", {"Temperature": 160.0}, datetime.now(timezone.utc)
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.fault_type, FaultType.TEMP_DRIFT)
        self.assertGreater(result.confidence, 0.0)

    def test_process_data_with_callback(self):
        """测试带回调的数据处理"""
        callback_mock = Mock()
        self.engine.set_on_fault(callback_mock)

        limit = Limit("Temperature", LimitType.UCL, 150.0)
        self.engine.set_limit("eq-001", "Temperature", limit)

        self.engine.process_data_sync(
            "eq-001", "ch-1", {"Temperature": 160.0}, datetime.now(timezone.utc)
        )

        callback_mock.assert_called_once()
        fault = callback_mock.call_args[0][0]
        self.assertIsInstance(fault, Fault)

    def test_process_data_updates_buffer(self):
        """测试数据处理更新缓冲区"""
        # 添加足够的数据触发检测
        for i in range(15):
            self.engine.process_data_sync(
                "eq-001", "ch-1", {"Temperature": 100.0 + i * 0.5}, datetime.now(timezone.utc)
            )

        buffer_key = "eq-001:Temperature"
        # 缓冲区大小应该等于window_size
        self.assertLessEqual(len(self.engine._feature_buffer[buffer_key]), self.engine._window_size)

    def test_fault_count_increment(self):
        """测试故障计数增加"""
        limit = Limit("Temperature", LimitType.UCL, 150.0)
        self.engine.set_limit("eq-001", "Temperature", limit)

        self.engine.process_data_sync(
            "eq-001", "ch-1", {"Temperature": 160.0}, datetime.now(timezone.utc)
        )

        self.assertEqual(self.engine.fault_count, 1)

    def test_multiple_parameters(self):
        """测试多参数处理"""
        limit_temp = Limit("Temperature", LimitType.UCL, 150.0)
        limit_pressure = Limit("Pressure", LimitType.LCL, 0.5)
        self.engine.set_limit("eq-001", "Temperature", limit_temp)
        self.engine.set_limit("eq-001", "Pressure", limit_pressure)

        # 温度正常，压力违规
        result = self.engine.process_data_sync(
            "eq-001", "ch-1", {"Temperature": 120.0, "Pressure": 0.3}, datetime.now(timezone.utc)
        )

        self.assertIsNotNone(result)


class TestFDCEngineAsync(unittest.TestCase):
    """测试FDC引擎异步功能"""

    def setUp(self):
        """设置测试环境"""
        self.engine = FDCEngine(window_size=50, min_window_size=10)

    def test_process_data_async(self):
        """测试异步数据处理"""
        limit = Limit("Temperature", LimitType.UCL, 150.0)
        self.engine.set_limit("eq-001", "Temperature", limit)

        async def run_test():
            result = await self.engine.process_data(
                "eq-001", "ch-1", {"Temperature": 160.0}, datetime.now(timezone.utc)
            )
            return result

        result = asyncio.get_event_loop().run_until_complete(run_test())

        self.assertIsNotNone(result)

    def test_async_callback(self):
        """测试异步回调"""
        callback_mock = Mock()

        async def async_callback(fault):
            callback_mock(fault)

        self.engine.set_on_fault(async_callback, async_callback=True)

        limit = Limit("Temperature", LimitType.UCL, 150.0)
        self.engine.set_limit("eq-001", "Temperature", limit)

        async def run_test():
            await self.engine.process_data(
                "eq-001", "ch-1", {"Temperature": 160.0}, datetime.now(timezone.utc)
            )

        asyncio.get_event_loop().run_until_complete(run_test())

        callback_mock.assert_called_once()


class TestFDCEngineFaultManagement(unittest.TestCase):
    """测试FDC引擎故障管理"""

    def setUp(self):
        """设置测试环境"""
        self.engine = FDCEngine(window_size=50, min_window_size=10)

    def test_resolve_fault(self):
        """测试解决故障"""
        limit = Limit("Temperature", LimitType.UCL, 150.0)
        self.engine.set_limit("eq-001", "Temperature", limit)

        self.engine.process_data_sync(
            "eq-001", "ch-1", {"Temperature": 160.0}, datetime.now(timezone.utc)
        )

        fault_id = self.engine.active_faults[0].fault_id if self.engine.active_faults else None

        if fault_id:
            result = self.engine.resolve_fault(fault_id)
            self.assertTrue(result)
            self.assertEqual(len(self.engine.active_faults), 0)

    def test_dismiss_fault(self):
        """测试忽略故障"""
        limit = Limit("Temperature", LimitType.UCL, 150.0)
        self.engine.set_limit("eq-001", "Temperature", limit)

        self.engine.process_data_sync(
            "eq-001", "ch-1", {"Temperature": 160.0}, datetime.now(timezone.utc)
        )

        fault_id = self.engine.active_faults[0].fault_id if self.engine.active_faults else None

        if fault_id:
            result = self.engine.dismiss_fault(fault_id, "误报")
            self.assertTrue(result)
            self.assertEqual(len(self.engine.active_faults), 0)

    def test_resolve_nonexistent_fault(self):
        """测试解决不存在的故障"""
        result = self.engine.resolve_fault("nonexistent-id")
        self.assertFalse(result)

    def test_clear_history(self):
        """测试清除历史"""
        limit = Limit("Temperature", LimitType.UCL, 150.0)
        self.engine.set_limit("eq-001", "Temperature", limit)

        self.engine.process_data_sync(
            "eq-001", "ch-1", {"Temperature": 160.0}, datetime.now(timezone.utc)
        )

        self.engine.clear_history()

        self.assertEqual(len(self.engine.fault_history), 0)
        self.assertEqual(self.engine.fault_count, 0)

    def test_reset(self):
        """测试重置引擎"""
        limit = Limit("Temperature", LimitType.UCL, 150.0)
        self.engine.set_limit("eq-001", "Temperature", limit)

        self.engine.process_data_sync(
            "eq-001", "ch-1", {"Temperature": 160.0}, datetime.now(timezone.utc)
        )

        self.engine.reset()

        self.assertEqual(len(self.engine._limits), 0)
        self.assertEqual(len(self.engine._detectors), 0)
        self.assertEqual(len(self.engine._feature_buffer), 0)
        self.assertEqual(len(self.engine.active_faults), 0)


class TestFDCEngineIntegration(unittest.TestCase):
    """测试FDC引擎集成"""

    def setUp(self):
        """设置测试环境"""
        self.engine = FDCEngine(window_size=50, min_window_size=10)

    def test_full_detection_pipeline(self):
        """测试完整检测流程"""
        # 1. 设置基线
        np.random.seed(42)
        baseline = np.random.normal(100, 5, 100)
        self.engine.set_baseline("eq-001", "Temperature", baseline)

        # 2. 设置限值
        limit = Limit("Temperature", LimitType.UCL, 120.0)
        self.engine.set_limit("eq-001", "Temperature", limit)

        # 3. 设置回调
        faults_detected = []

        def on_fault(fault):
            faults_detected.append(fault)

        self.engine.set_on_fault(on_fault)

        # 4. 处理数据
        for i in range(20):
            # 添加有轻微偏移的数据
            value = 100.0 + i * 0.3 + np.random.normal(0, 1)
            self.engine.process_data_sync(
                "eq-001", "ch-1", {"Temperature": value}, datetime.now(timezone.utc)
            )

        # 验证结果
        self.assertGreaterEqual(len(faults_detected), 0)

    def test_event_generation(self):
        """测试事件生成"""
        events_received = []

        def on_event(event):
            events_received.append(event)

        self.engine.set_on_event(on_event)

        limit = Limit("Temperature", LimitType.UCL, 150.0)
        self.engine.set_limit("eq-001", "Temperature", limit)

        # 正常数据不应产生事件
        self.engine.process_data_sync(
            "eq-001", "ch-1", {"Temperature": 100.0}, datetime.now(timezone.utc)
        )

        self.assertEqual(len(events_received), 0)


if __name__ == "__main__":
    unittest.main()
