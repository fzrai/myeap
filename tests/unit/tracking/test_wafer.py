"""晶圆追踪器测试"""

import pytest
from datetime import datetime, timedelta, timezone

from myeap.tracking.wafer import WaferTracker
from myeap.tracking.models import (
    WaferStatus,
    WaferEvent,
    EventType,
)


class TestWaferTracker:
    """晶圆追踪器测试"""

    @pytest.fixture
    def tracker(self):
        """创建晶圆追踪器实例"""
        return WaferTracker(db_manager=None)

    @pytest.mark.asyncio
    async def test_track_wafer(self, tracker):
        """测试追踪晶圆"""
        wafer = await tracker.track_wafer(
            wafer_id="W-001",
            lot_id="LOT-001",
        )
        assert wafer.wafer_id == "W-001"
        assert wafer.lot_id == "LOT-001"
        assert wafer.status == WaferStatus.IN_CARRIER

    @pytest.mark.asyncio
    async def test_track_wafer_with_location(self, tracker):
        """测试追踪带位置的晶圆"""
        wafer = await tracker.track_wafer(
            wafer_id="W-001",
            lot_id="LOT-001",
            carrier_id="CAR-001",
            position=0,
        )
        assert wafer.current_carrier_id == "CAR-001"
        assert wafer.position == 0

    @pytest.mark.asyncio
    async def test_get_wafer(self, tracker):
        """测试获取晶圆"""
        await tracker.track_wafer(
            wafer_id="W-001",
            lot_id="LOT-001",
        )
        wafer = await tracker.get_wafer("W-001")
        assert wafer is not None
        assert wafer.wafer_id == "W-001"

        # 获取不存在的晶圆
        wafer = await tracker.get_wafer("W-999")
        assert wafer is None

    @pytest.mark.asyncio
    async def test_update_wafer_location(self, tracker):
        """测试更新晶圆位置"""
        await tracker.track_wafer(
            wafer_id="W-001",
            lot_id="LOT-001",
        )
        result = await tracker.update_wafer_location(
            wafer_id="W-001",
            location="EQ-001",
            carrier_id="CAR-001",
            position=0,
        )
        assert result is True

        wafer = await tracker.get_wafer("W-001")
        assert wafer.current_location == "EQ-001"
        assert wafer.current_carrier_id == "CAR-001"

    @pytest.mark.asyncio
    async def test_record_process_event(self, tracker):
        """测试记录工艺事件"""
        await tracker.track_wafer(
            wafer_id="W-001",
            lot_id="LOT-001",
        )
        event = WaferEvent(
            event_id="EVT-001",
            wafer_id="W-001",
            lot_id="LOT-001",
            event_type=EventType.PROCESS_START,
            equipment_id="EQ-001",
            recipe_name="Clean Recipe",
        )
        await tracker.record_process_event("W-001", event)

        wafer = await tracker.get_wafer("W-001")
        assert len(wafer.history) == 1
        assert wafer.status == WaferStatus.IN_PROCESS

    @pytest.mark.asyncio
    async def test_record_wafer_loaded(self, tracker):
        """测试记录晶圆装载事件"""
        event = await tracker.record_wafer_loaded(
            wafer_id="W-001",
            lot_id="LOT-001",
            carrier_id="CAR-001",
            position=0,
            equipment_id="EQ-001",
        )
        assert event.event_type == EventType.WAFER_LOADED
        assert event.carrier_id == "CAR-001"
        assert event.position == 0

        wafer = await tracker.get_wafer("W-001")
        assert wafer.status == WaferStatus.IN_CARRIER
        assert wafer.current_carrier_id == "CAR-001"

    @pytest.mark.asyncio
    async def test_record_process_start(self, tracker):
        """测试记录工艺开始事件"""
        await tracker.track_wafer(
            wafer_id="W-001",
            lot_id="LOT-001",
        )
        event = await tracker.record_process_start(
            wafer_id="W-001",
            lot_id="LOT-001",
            equipment_id="EQ-001",
            chamber_id="CH-01",
            recipe_id="RCP-001",
            recipe_name="Clean Recipe",
        )
        assert event.event_type == EventType.PROCESS_START
        assert event.equipment_id == "EQ-001"
        assert event.recipe_name == "Clean Recipe"

        wafer = await tracker.get_wafer("W-001")
        assert wafer.status == WaferStatus.IN_PROCESS

    @pytest.mark.asyncio
    async def test_record_process_end(self, tracker):
        """测试记录工艺结束事件"""
        await tracker.track_wafer(
            wafer_id="W-001",
            lot_id="LOT-001",
        )
        await tracker.record_process_start(
            wafer_id="W-001",
            lot_id="LOT-001",
            equipment_id="EQ-001",
        )
        event = await tracker.record_process_end(
            wafer_id="W-001",
            lot_id="LOT-001",
            equipment_id="EQ-001",
            duration_seconds=300.0,
            result={"status": "COMPLETED"},
        )
        assert event.event_type == EventType.PROCESS_END
        assert event.duration_seconds == 300.0

        wafer = await tracker.get_wafer("W-001")
        assert wafer.status == WaferStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_record_process_end_with_failure(self, tracker):
        """测试记录工艺失败事件"""
        await tracker.track_wafer(
            wafer_id="W-001",
            lot_id="LOT-001",
        )
        await tracker.record_process_start(
            wafer_id="W-001",
            lot_id="LOT-001",
            equipment_id="EQ-001",
        )
        event = await tracker.record_process_end(
            wafer_id="W-001",
            lot_id="LOT-001",
            equipment_id="EQ-001",
            duration_seconds=100.0,
            result={"status": "FAILED"},
        )

        wafer = await tracker.get_wafer("W-001")
        assert wafer.status == WaferStatus.REJECTED

    @pytest.mark.asyncio
    async def test_get_wafer_history(self, tracker):
        """测试获取晶圆历史"""
        await tracker.track_wafer(
            wafer_id="W-001",
            lot_id="LOT-001",
        )
        await tracker.record_process_start(
            wafer_id="W-001",
            lot_id="LOT-001",
            equipment_id="EQ-001",
            recipe_name="Recipe 1",
        )
        await tracker.record_process_end(
            wafer_id="W-001",
            lot_id="LOT-001",
            equipment_id="EQ-001",
            duration_seconds=300.0,
        )

        history = await tracker.get_wafer_history("W-001")
        assert len(history) == 2
        assert history[0].event_type == EventType.PROCESS_START
        assert history[1].event_type == EventType.PROCESS_END

    @pytest.mark.asyncio
    async def test_trace_lot(self, tracker):
        """测试追溯批次"""
        await tracker.track_wafer(
            wafer_id="W-001",
            lot_id="LOT-001",
        )
        await tracker.track_wafer(
            wafer_id="W-002",
            lot_id="LOT-001",
        )
        await tracker.record_process_start(
            wafer_id="W-001",
            lot_id="LOT-001",
            equipment_id="EQ-001",
        )
        await tracker.record_process_start(
            wafer_id="W-002",
            lot_id="LOT-001",
            equipment_id="EQ-001",
        )

        events = await tracker.trace_lot("LOT-001")
        assert len(events) == 2
        wafer_ids = {e.wafer_id for e in events}
        assert "W-001" in wafer_ids
        assert "W-002" in wafer_ids

    @pytest.mark.asyncio
    async def test_find_affected_wafers(self, tracker):
        """测试查找受影响晶圆"""
        await tracker.track_wafer(
            wafer_id="W-001",
            lot_id="LOT-001",
        )
        await tracker.track_wafer(
            wafer_id="W-002",
            lot_id="LOT-001",
        )
        await tracker.track_wafer(
            wafer_id="W-003",
            lot_id="LOT-002",
        )

        # 记录一些事件
        now = datetime.now(timezone.utc)
        await tracker.record_process_start(
            wafer_id="W-001",
            lot_id="LOT-001",
            equipment_id="EQ-001",
        )
        await tracker.record_process_start(
            wafer_id="W-002",
            lot_id="LOT-001",
            equipment_id="EQ-001",
        )
        await tracker.record_process_start(
            wafer_id="W-003",
            lot_id="LOT-002",
            equipment_id="EQ-002",
        )

        affected = await tracker.find_affected_wafers(
            equipment_id="EQ-001",
            time_range=(now - timedelta(hours=1), now + timedelta(hours=1)),
        )
        assert len(affected) == 2
        assert "W-001" in affected
        assert "W-002" in affected
        assert "W-003" not in affected

    @pytest.mark.asyncio
    async def test_get_wafers_by_status(self, tracker):
        """测试按状态获取晶圆"""
        await tracker.track_wafer(
            wafer_id="W-001",
            lot_id="LOT-001",
        )
        await tracker.track_wafer(
            wafer_id="W-002",
            lot_id="LOT-001",
        )
        await tracker.track_wafer(
            wafer_id="W-003",
            lot_id="LOT-002",
        )

        await tracker.record_process_start(
            wafer_id="W-001",
            lot_id="LOT-001",
            equipment_id="EQ-001",
        )

        in_carrier = await tracker.get_wafers_by_status(WaferStatus.IN_CARRIER)
        assert len(in_carrier) == 2

        in_process = await tracker.get_wafers_by_status(WaferStatus.IN_PROCESS)
        assert len(in_process) == 1
        assert in_process[0].wafer_id == "W-001"

    @pytest.mark.asyncio
    async def test_get_wafer_count(self, tracker):
        """测试获取晶圆数量统计"""
        await tracker.track_wafer(
            wafer_id="W-001",
            lot_id="LOT-001",
        )
        await tracker.track_wafer(
            wafer_id="W-002",
            lot_id="LOT-001",
        )

        counts = await tracker.get_wafer_count()
        assert counts[WaferStatus.IN_CARRIER] == 2
        assert counts[WaferStatus.IN_PROCESS] == 0

    @pytest.mark.asyncio
    async def test_get_tracker_stats(self, tracker):
        """测试获取追踪器统计信息"""
        await tracker.track_wafer(
            wafer_id="W-001",
            lot_id="LOT-001",
        )
        await tracker.track_wafer(
            wafer_id="W-002",
            lot_id="LOT-001",
        )
        await tracker.record_process_start(
            wafer_id="W-001",
            lot_id="LOT-001",
            equipment_id="EQ-001",
        )

        stats = tracker.get_tracker_stats()
        assert stats["total"] == 2
        assert stats["tracked_lots"] == 1
        assert stats["equipment_count"] == 1

    @pytest.mark.asyncio
    async def test_complete_process_flow(self, tracker):
        """测试完整工艺流程"""
        # 1. 追踪晶圆
        wafer = await tracker.track_wafer(
            wafer_id="W-001",
            lot_id="LOT-001",
            carrier_id="CAR-001",
            position=0,
        )
        assert wafer.status == WaferStatus.IN_CARRIER

        # 2. 开始清洗工艺
        event1 = await tracker.record_process_start(
            wafer_id="W-001",
            lot_id="LOT-001",
            equipment_id="EQ-CLEANER",
            chamber_id="CH-01",
            recipe_name="Clean Recipe",
        )
        assert event1.event_type == EventType.PROCESS_START

        wafer = await tracker.get_wafer("W-001")
        assert wafer.status == WaferStatus.IN_PROCESS

        # 3. 结束清洗工艺
        event2 = await tracker.record_process_end(
            wafer_id="W-001",
            lot_id="LOT-001",
            equipment_id="EQ-CLEANER",
            duration_seconds=600.0,
            result={"status": "COMPLETED"},
            measurements={"cleanliness": 0.99},
        )
        assert event2.event_type == EventType.PROCESS_END

        wafer = await tracker.get_wafer("W-001")
        assert wafer.status == WaferStatus.COMPLETED

        # 4. 检查历史
        history = await tracker.get_wafer_history("W-001")
        assert len(history) == 2
        assert history[0].event_type == EventType.PROCESS_START
        assert history[1].event_type == EventType.PROCESS_END
        assert history[1].measurements == {"cleanliness": 0.99}
