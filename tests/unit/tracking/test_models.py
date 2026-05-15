"""追踪模型测试"""

import pytest
from datetime import datetime

from myeap.tracking.models import (
    CarrierType,
    CarrierStatus,
    WaferStatus,
    Carrier,
    Wafer,
    WaferEvent,
    ProcessResult,
    EventType,
)


class TestCarrierType:
    """载具类型测试"""

    def test_all_types_have_values(self):
        """测试所有类型都有值"""
        assert CarrierType.FOUP.value == "foup"
        assert CarrierType.FOSB.value == "fosb"
        assert CarrierType.MAGAZINE.value == "magazine"

    def test_from_string(self):
        """测试从字符串转换"""
        assert CarrierType.from_string("foup") == CarrierType.FOUP
        assert CarrierType.from_string("FOUP") == CarrierType.FOUP
        assert CarrierType.from_string("fosb") == CarrierType.FOSB
        assert CarrierType.from_string("magazine") == CarrierType.MAGAZINE
        assert CarrierType.from_string("unknown") == CarrierType.FOUP  # 默认值


class TestCarrierStatus:
    """载具状态测试"""

    def test_all_statuses_have_values(self):
        """测试所有状态都有值"""
        assert CarrierStatus.IDLE.value == "idle"
        assert CarrierStatus.LOADED.value == "loaded"
        assert CarrierStatus.IN_TRANSIT.value == "in_transit"
        assert CarrierStatus.AT_EQUIPMENT.value == "at_equipment"
        assert CarrierStatus.WAITING.value == "waiting"

    def test_from_string(self):
        """测试从字符串转换"""
        assert CarrierStatus.from_string("idle") == CarrierStatus.IDLE
        assert CarrierStatus.from_string("IDLE") == CarrierStatus.IDLE
        assert CarrierStatus.from_string("loaded") == CarrierStatus.LOADED
        assert CarrierStatus.from_string("unknown") == CarrierStatus.IDLE  # 默认值


class TestWaferStatus:
    """晶圆状态测试"""

    def test_all_statuses_have_values(self):
        """测试所有状态都有值"""
        assert WaferStatus.IN_CARRIER.value == "in_carrier"
        assert WaferStatus.IN_PROCESS.value == "in_process"
        assert WaferStatus.COMPLETED.value == "completed"
        assert WaferStatus.REJECTED.value == "rejected"

    def test_from_string(self):
        """测试从字符串转换"""
        assert WaferStatus.from_string("in_carrier") == WaferStatus.IN_CARRIER
        assert WaferStatus.from_string("IN_CARRIER") == WaferStatus.IN_CARRIER
        assert WaferStatus.from_string("completed") == WaferStatus.COMPLETED
        assert WaferStatus.from_string("unknown") == WaferStatus.IN_CARRIER  # 默认值


class TestCarrier:
    """载具模型测试"""

    def test_creation(self):
        """测试创建载具"""
        carrier = Carrier(
            carrier_id="CAR-001",
            carrier_type=CarrierType.FOUP,
            capacity=25,
        )
        assert carrier.carrier_id == "CAR-001"
        assert carrier.carrier_type == CarrierType.FOUP
        assert carrier.capacity == 25
        assert carrier.status == CarrierStatus.IDLE
        assert len(carrier.wafer_ids) == 0
        assert carrier.created_at is not None

    def test_is_empty(self):
        """测试空载具判断"""
        carrier = Carrier(
            carrier_id="CAR-001",
            carrier_type=CarrierType.FOUP,
            capacity=25,
        )
        assert carrier.is_empty
        carrier.wafer_ids = ["W-001"]
        assert not carrier.is_empty

    def test_is_full(self):
        """测试载具已满判断"""
        carrier = Carrier(
            carrier_id="CAR-001",
            carrier_type=CarrierType.FOUP,
            capacity=2,
        )
        assert not carrier.is_full
        carrier.wafer_ids = ["W-001"]
        assert not carrier.is_full
        carrier.wafer_ids = ["W-001", "W-002"]
        assert carrier.is_full

    def test_available_slots(self):
        """测试可用槽位计算"""
        carrier = Carrier(
            carrier_id="CAR-001",
            carrier_type=CarrierType.FOUP,
            capacity=25,
        )
        assert carrier.available_slots == 25
        carrier.wafer_ids = ["W-001", "W-002"]
        assert carrier.available_slots == 23

    def test_to_dict(self):
        """测试转换为字典"""
        carrier = Carrier(
            carrier_id="CAR-001",
            carrier_type=CarrierType.FOUP,
            capacity=25,
        )
        data = carrier.to_dict()
        assert data["carrier_id"] == "CAR-001"
        assert data["carrier_type"] == "foup"
        assert data["capacity"] == 25
        assert data["status"] == "idle"


class TestWaferEvent:
    """晶圆事件模型测试"""

    def test_creation(self):
        """测试创建晶圆事件"""
        event = WaferEvent(
            event_id="EVT-001",
            wafer_id="W-001",
            lot_id="LOT-001",
            event_type="LOADED",
        )
        assert event.event_id == "EVT-001"
        assert event.wafer_id == "W-001"
        assert event.lot_id == "LOT-001"
        assert event.event_type == "LOADED"
        assert event.timestamp is not None

    def test_with_equipment_info(self):
        """测试带设备信息的事件"""
        event = WaferEvent(
            event_id="EVT-001",
            wafer_id="W-001",
            lot_id="LOT-001",
            event_type="PROCESS_START",
            equipment_id="EQ-001",
            chamber_id="CH-01",
            recipe_id="RCP-001",
            recipe_name="Clean Recipe",
        )
        assert event.equipment_id == "EQ-001"
        assert event.chamber_id == "CH-01"
        assert event.recipe_id == "RCP-001"
        assert event.recipe_name == "Clean Recipe"

    def test_with_measurements(self):
        """测试带测量数据的事件"""
        event = WaferEvent(
            event_id="EVT-001",
            wafer_id="W-001",
            lot_id="LOT-001",
            event_type="PROCESS_END",
            duration_seconds=120.5,
            measurements={"temperature": 150.0, "pressure": 10.0},
        )
        assert event.duration_seconds == 120.5
        assert event.measurements == {"temperature": 150.0, "pressure": 10.0}

    def test_to_dict(self):
        """测试转换为字典"""
        event = WaferEvent(
            event_id="EVT-001",
            wafer_id="W-001",
            lot_id="LOT-001",
            event_type="LOADED",
            equipment_id="EQ-001",
        )
        data = event.to_dict()
        assert data["event_id"] == "EVT-001"
        assert data["wafer_id"] == "W-001"
        assert data["event_type"] == "LOADED"
        assert data["equipment_id"] == "EQ-001"


class TestWafer:
    """晶圆模型测试"""

    def test_creation(self):
        """测试创建晶圆"""
        wafer = Wafer(
            wafer_id="W-001",
            lot_id="LOT-001",
        )
        assert wafer.wafer_id == "W-001"
        assert wafer.lot_id == "LOT-001"
        assert wafer.status == WaferStatus.IN_CARRIER
        assert len(wafer.history) == 0

    def test_add_event(self):
        """测试添加事件"""
        wafer = Wafer(
            wafer_id="W-001",
            lot_id="LOT-001",
        )
        event = WaferEvent(
            event_id="EVT-001",
            wafer_id="W-001",
            lot_id="LOT-001",
            event_type="LOADED",
        )
        wafer.add_event(event)
        assert wafer.get_event_count() == 1
        assert wafer.history[0] == event

    def test_status_checks(self):
        """测试状态检查"""
        wafer = Wafer(
            wafer_id="W-001",
            lot_id="LOT-001",
        )
        assert wafer.is_in_carrier
        assert not wafer.is_in_process
        assert not wafer.is_completed

        wafer.status = WaferStatus.IN_PROCESS
        assert not wafer.is_in_carrier
        assert wafer.is_in_process

        wafer.status = WaferStatus.COMPLETED
        assert wafer.is_completed

        wafer.status = WaferStatus.REJECTED
        assert wafer.is_rejected


class TestProcessResult:
    """工艺结果模型测试"""

    def test_creation(self):
        """测试创建工艺结果"""
        result = ProcessResult(
            wafer_id="W-001",
            recipe_id="RCP-001",
            equipment_id="EQ-001",
            start_time=datetime(2024, 1, 1, 10, 0, 0),
            end_time=datetime(2024, 1, 1, 10, 5, 0),
            duration_seconds=300.0,
            status="COMPLETED",
        )
        assert result.wafer_id == "W-001"
        assert result.status == "COMPLETED"
        assert result.duration_seconds == 300.0

    def test_is_successful(self):
        """测试成功判断"""
        result = ProcessResult(
            wafer_id="W-001",
            recipe_id="RCP-001",
            equipment_id="EQ-001",
            start_time=datetime(2024, 1, 1, 10, 0, 0),
            end_time=datetime(2024, 1, 1, 10, 5, 0),
            duration_seconds=300.0,
            status="COMPLETED",
        )
        assert result.is_successful
        assert not result.is_failed

        result.status = "FAILED"
        assert not result.is_successful
        assert result.is_failed

    def test_with_measurements(self):
        """测试带测量数据的结果"""
        result = ProcessResult(
            wafer_id="W-001",
            recipe_id="RCP-001",
            equipment_id="EQ-001",
            start_time=datetime(2024, 1, 1, 10, 0, 0),
            end_time=datetime(2024, 1, 1, 10, 5, 0),
            duration_seconds=300.0,
            status="COMPLETED",
            measurements={"thickness": 100.5, "uniformity": 0.95},
            defects=0,
        )
        assert result.measurements == {"thickness": 100.5, "uniformity": 0.95}
        assert result.defects == 0


class TestEventType:
    """事件类型常量测试"""

    def test_all_types(self):
        """测试所有事件类型"""
        types = EventType.all_types()
        assert "CARRIER_REGISTERED" in types
        assert "CARRIER_LOADED" in types
        assert "CARRIER_MOVED" in types
        assert "WAFER_LOADED" in types
        assert "PROCESS_START" in types
        assert "PROCESS_END" in types
