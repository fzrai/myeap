"""限值监控器测试"""

import asyncio
import pytest
from datetime import datetime

from myeap.data.models import DataPoint, DataBatch
from myeap.data.limit_monitor import (
    LimitMonitor,
    LimitType,
    Limit,
    LimitViolation,
)


class TestLimitType:
    """限值类型测试"""

    def test_control_limits(self):
        """测试控制限"""
        assert LimitType.UCL.is_control_limit
        assert LimitType.LCL.is_control_limit
        assert not LimitType.UCL.is_spec_limit
        assert not LimitType.LCL.is_spec_limit

    def test_spec_limits(self):
        """测试规格限"""
        assert LimitType.USL.is_spec_limit
        assert LimitType.LSL.is_spec_limit
        assert not LimitType.USL.is_control_limit
        assert not LimitType.LSL.is_control_limit


class TestLimit:
    """限值测试"""

    def test_creation(self):
        """测试创建限值"""
        limit = Limit("Temperature", LimitType.UCL, 100.0)
        assert limit.parameter_name == "Temperature"
        assert limit.limit_type == LimitType.UCL
        assert limit.value == 100.0
        assert limit.severity == "warning"

    def test_with_severity(self):
        """测试带严重程度"""
        limit = Limit("Temperature", LimitType.UCL, 100.0, severity="critical")
        assert limit.severity == "critical"

    def test_repr(self):
        """测试字符串表示"""
        limit = Limit("Temperature", LimitType.UCL, 100.0)
        assert "Temperature" in repr(limit)
        assert "ucl" in repr(limit)

    def test_to_dict(self):
        """测试转换为字典"""
        limit = Limit("Temperature", LimitType.UCL, 100.0)
        data = limit.to_dict()
        assert data["parameter_name"] == "Temperature"
        assert data["limit_type"] == "ucl"
        assert data["value"] == 100.0


class TestLimitViolation:
    """限值违规测试"""

    def test_creation(self):
        """测试创建违规"""
        limit = Limit("Temperature", LimitType.UCL, 100.0)
        violation = LimitViolation(
            equipment_id="eq-001",
            parameter_name="Temperature",
            value=105.0,
            limit=limit,
            deviation=5.0,
        )
        assert violation.equipment_id == "eq-001"
        assert violation.parameter_name == "Temperature"
        assert violation.value == 105.0
        assert violation.limit == limit
        assert violation.deviation == 5.0
        assert violation.timestamp is not None

    def test_repr(self):
        """测试字符串表示"""
        limit = Limit("Temperature", LimitType.UCL, 100.0)
        violation = LimitViolation(
            "eq-001", "Temperature", 105.0, limit, 5.0
        )
        assert "eq-001" in repr(violation)
        assert "Temperature" in repr(violation)

    def test_to_dict(self):
        """测试转换为字典"""
        limit = Limit("Temperature", LimitType.UCL, 100.0)
        violation = LimitViolation(
            "eq-001", "Temperature", 105.0, limit, 5.0
        )
        data = violation.to_dict()
        assert data["equipment_id"] == "eq-001"
        assert data["value"] == 105.0
        assert data["deviation"] == 5.0
        assert "timestamp" in data


class TestLimitMonitor:
    """限值监控器测试"""

    @pytest.fixture
    def monitor(self):
        """创建监控器"""
        return LimitMonitor()

    def test_creation(self, monitor):
        """测试创建监控器"""
        assert monitor.violation_count == 0
        assert monitor.get_limits("eq-001") == []

    def test_add_limit(self, monitor):
        """测试添加限值"""
        limit = Limit("Temperature", LimitType.UCL, 100.0)
        monitor.add_limit("eq-001", limit)

        limits = monitor.get_limits("eq-001")
        assert len(limits) == 1
        assert limits[0] == limit

    def test_add_multiple_limits(self, monitor):
        """测试添加多个限值"""
        monitor.add_limit("eq-001", Limit("Temp", LimitType.UCL, 100.0))
        monitor.add_limit("eq-001", Limit("Temp", LimitType.LCL, 50.0))
        monitor.add_limit("eq-001", Limit("Pressure", LimitType.USL, 200.0))

        limits = monitor.get_limits("eq-001")
        assert len(limits) == 3

    def test_remove_limit(self, monitor):
        """测试移除限值"""
        monitor.add_limit("eq-001", Limit("Temp", LimitType.UCL, 100.0))
        monitor.add_limit("eq-001", Limit("Temp", LimitType.LCL, 50.0))

        result = monitor.remove_limit("eq-001", "Temp", LimitType.UCL)
        assert result is True

        limits = monitor.get_limits("eq-001")
        assert len(limits) == 1
        assert limits[0].limit_type == LimitType.LCL

    def test_remove_nonexistent(self, monitor):
        """测试移除不存在的限值"""
        result = monitor.remove_limit("eq-001", "Temp")
        assert result is False

    def test_clear_limits(self, monitor):
        """测试清除限值"""
        monitor.add_limit("eq-001", Limit("Temp", LimitType.UCL, 100.0))
        monitor.add_limit("eq-002", Limit("Temp", LimitType.UCL, 100.0))

        monitor.clear_limits("eq-001")
        assert monitor.get_limits("eq-001") == []
        assert len(monitor.get_limits("eq-002")) == 1

        monitor.clear_limits()
        assert len(monitor.get_limits("eq-001")) == 0
        assert len(monitor.get_limits("eq-002")) == 0

    @pytest.mark.asyncio
    async def test_check_no_violation(self, monitor):
        """测试检查无违规"""
        monitor.add_limit("eq-001", Limit("Temp", LimitType.UCL, 100.0))
        point = DataPoint("eq-001", "Temp", 50.0)
        violation = await monitor.check(point)
        assert violation is None

    @pytest.mark.asyncio
    async def test_check_ucl_violation(self, monitor):
        """测试检查UCL违规"""
        monitor.add_limit("eq-001", Limit("Temp", LimitType.UCL, 100.0))
        point = DataPoint("eq-001", "Temp", 105.0)
        violation = await monitor.check(point)

        assert violation is not None
        assert violation.equipment_id == "eq-001"
        assert violation.parameter_name == "Temp"
        assert violation.value == 105.0
        assert violation.limit.value == 100.0
        assert violation.deviation == 5.0

    @pytest.mark.asyncio
    async def test_check_lcl_violation(self, monitor):
        """测试检查LCL违规"""
        monitor.add_limit("eq-001", Limit("Temp", LimitType.LCL, 50.0))
        point = DataPoint("eq-001", "Temp", 45.0)
        violation = await monitor.check(point)

        assert violation is not None
        assert violation.limit.limit_type == LimitType.LCL
        assert violation.deviation == -5.0

    @pytest.mark.asyncio
    async def test_check_usl_violation(self, monitor):
        """测试检查USL违规"""
        monitor.add_limit("eq-001", Limit("Temp", LimitType.USL, 100.0))
        point = DataPoint("eq-001", "Temp", 110.0)
        violation = await monitor.check(point)
        assert violation is not None

    @pytest.mark.asyncio
    async def test_check_lsl_violation(self, monitor):
        """测试检查LSL违规"""
        monitor.add_limit("eq-001", Limit("Temp", LimitType.LSL, 50.0))
        point = DataPoint("eq-001", "Temp", 40.0)
        violation = await monitor.check(point)
        assert violation is not None

    @pytest.mark.asyncio
    async def test_check_boundary(self, monitor):
        """测试边界值"""
        monitor.add_limit("eq-001", Limit("Temp", LimitType.UCL, 100.0))
        # 边界值不应违规
        point = DataPoint("eq-001", "Temp", 100.0)
        violation = await monitor.check(point)
        assert violation is None

    @pytest.mark.asyncio
    async def test_check_unknown_equipment(self, monitor):
        """测试未知设备"""
        monitor.add_limit("eq-001", Limit("Temp", LimitType.UCL, 100.0))
        point = DataPoint("eq-002", "Temp", 200.0)
        violation = await monitor.check(point)
        assert violation is None

    @pytest.mark.asyncio
    async def test_check_unknown_parameter(self, monitor):
        """测试未知参数"""
        monitor.add_limit("eq-001", Limit("Temp", LimitType.UCL, 100.0))
        point = DataPoint("eq-001", "Pressure", 200.0)
        violation = await monitor.check(point)
        assert violation is None

    @pytest.mark.asyncio
    async def test_check_batch(self, monitor):
        """测试批次检查"""
        monitor.add_limit("eq-001", Limit("Temp", LimitType.UCL, 100.0))
        monitor.add_limit("eq-001", Limit("Pressure", LimitType.USL, 200.0))

        batch = DataBatch(
            equipment_id="eq-001",
            points=[
                DataPoint("eq-001", "Temp", 50.0),  # 正常
                DataPoint("eq-001", "Temp", 105.0),  # 违规
                DataPoint("eq-001", "Pressure", 250.0),  # 违规
                DataPoint("eq-001", "Temp", 75.0),  # 正常
            ],
        )

        violations = await monitor.check_batch(batch)
        assert len(violations) == 2

    @pytest.mark.asyncio
    async def test_violation_callback(self, monitor):
        """测试违规回调"""
        violations_received = []

        def on_violation(v):
            violations_received.append(v)

        monitor.set_on_violation(on_violation)
        monitor.add_limit("eq-001", Limit("Temp", LimitType.UCL, 100.0))

        # 触发违规
        point = DataPoint("eq-001", "Temp", 105.0)
        await monitor.check(point)

        # 验证回调被调用
        assert len(violations_received) == 1

    def test_async_violation_callback(self, monitor):
        """测试异步违规回调"""
        async def on_violation(v):
            pass

        monitor.set_on_violation_async(on_violation)
        assert monitor._on_violation_async is not None

    def test_violation_count(self, monitor):
        """测试违规计数"""
        assert monitor.violation_count == 0
        monitor._violation_count = 5
        assert monitor.violation_count == 5
        monitor.reset_violation_count()
        assert monitor.violation_count == 0


class TestLimitMonitorIntegration:
    """限值监控器集成测试"""

    @pytest.mark.asyncio
    async def test_multiple_equipment(self):
        """测试多设备监控"""
        monitor = LimitMonitor()

        # 设备1的限值
        monitor.add_limit("eq-001", Limit("Temp", LimitType.UCL, 100.0))
        monitor.add_limit("eq-001", Limit("Temp", LimitType.LCL, 50.0))

        # 设备2的限值
        monitor.add_limit("eq-002", Limit("Temp", LimitType.UCL, 120.0))

        # 测试设备1违规
        v1 = await monitor.check(DataPoint("eq-001", "Temp", 110.0))
        assert v1 is not None

        # 测试设备2不违规
        v2 = await monitor.check(DataPoint("eq-002", "Temp", 110.0))
        assert v2 is None

    @pytest.mark.asyncio
    async def test_multiple_parameters(self):
        """测试多参数监控"""
        monitor = LimitMonitor()

        monitor.add_limit("eq-001", Limit("Temp", LimitType.UCL, 100.0))
        monitor.add_limit("eq-001", Limit("Pressure", LimitType.USL, 200.0))
        monitor.add_limit("eq-001", Limit("Flow", LimitType.LCL, 10.0))

        # 温度违规
        v1 = await monitor.check(DataPoint("eq-001", "Temp", 110.0))
        assert v1 is not None

        # 压力违规
        v2 = await monitor.check(DataPoint("eq-001", "Pressure", 250.0))
        assert v2 is not None

        # 流量正常
        v3 = await monitor.check(DataPoint("eq-001", "Flow", 50.0))
        assert v3 is None
