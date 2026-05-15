"""追溯服务测试"""

import pytest
from datetime import datetime, timedelta, timezone

from myeap.tracking.service import TraceabilityService
from myeap.tracking.wafer import WaferTracker
from myeap.tracking.carrier import CarrierManager
from myeap.tracking.models import (
    CarrierType,
    CarrierStatus,
    WaferStatus,
    WaferEvent,
    EventType,
)


class TestTraceabilityService:
    """追溯服务测试"""

    @pytest.fixture
    def service(self):
        """创建追溯服务实例"""
        tracker = WaferTracker(db_manager=None)
        carrier_manager = CarrierManager(db_manager=None)
        return TraceabilityService(tracker, carrier_manager), tracker, carrier_manager

    @pytest.mark.asyncio
    async def test_trace_forward(self, service):
        """测试正向追踪"""
        svc, tracker, _ = service

        # 准备测试数据
        await tracker.track_wafer(
            wafer_id="W-001",
            lot_id="LOT-001",
        )
        await tracker.record_process_start(
            wafer_id="W-001",
            lot_id="LOT-001",
            equipment_id="EQ-001",
            recipe_name="Recipe A",
        )
        await tracker.record_process_end(
            wafer_id="W-001",
            lot_id="LOT-001",
            equipment_id="EQ-001",
            duration_seconds=300.0,
        )
        await tracker.record_process_start(
            wafer_id="W-001",
            lot_id="LOT-001",
            equipment_id="EQ-002",
            recipe_name="Recipe B",
        )
        await tracker.record_process_end(
            wafer_id="W-001",
            lot_id="LOT-001",
            equipment_id="EQ-002",
            duration_seconds=600.0,
        )

        # 执行正向追踪
        trace = await svc.trace_forward("LOT-001")

        assert trace["lot_id"] == "LOT-001"
        assert trace["summary"]["total_wafers"] == 1
        assert trace["summary"]["total_events"] == 4
        assert trace["summary"]["equipment_count"] == 2
        assert trace["summary"]["recipe_count"] == 2
        assert "Recipe A" in trace["recipe_usage"]
        assert "Recipe B" in trace["recipe_usage"]
        assert "EQ-001" in trace["equipment_visits"]
        assert "EQ-002" in trace["equipment_visits"]

    @pytest.mark.asyncio
    async def test_trace_backward(self, service):
        """测试反向追溯"""
        svc, tracker, _ = service

        # 准备测试数据
        await tracker.track_wafer(
            wafer_id="W-001",
            lot_id="LOT-001",
        )
        await tracker.record_process_start(
            wafer_id="W-001",
            lot_id="LOT-001",
            equipment_id="EQ-001",
            recipe_name="Recipe A",
        )
        await tracker.record_process_end(
            wafer_id="W-001",
            lot_id="LOT-001",
            equipment_id="EQ-001",
            duration_seconds=300.0,
        )

        # 执行反向追溯
        trace = await svc.trace_backward("W-001")

        assert trace["wafer_id"] == "W-001"
        assert trace["lot_id"] == "LOT-001"
        assert trace["summary"]["total_events"] == 2
        assert trace["summary"]["equipment_count"] == 1
        assert len(trace["equipment_path"]) == 1
        assert trace["equipment_path"][0] == "EQ-001"

    @pytest.mark.asyncio
    async def test_trace_backward_not_found(self, service):
        """测试反向追溯不存在的晶圆"""
        svc, tracker, _ = service

        trace = await svc.trace_backward("W-999")
        assert "error" in trace
        assert trace["error"] == "Wafer not found"

    @pytest.mark.asyncio
    async def test_trace_by_carrier(self, service):
        """测试按载具追溯"""
        svc, tracker, carrier_mgr = service

        # 注册载具
        await carrier_mgr.register_carrier(
            carrier_id="CAR-001",
            carrier_type=CarrierType.FOUP,
            capacity=25,
        )
        await carrier_mgr.load_carrier(
            carrier_id="CAR-001",
            wafer_ids=["W-001", "W-002"],
            location="STOCK-01",
        )

        # 追踪晶圆
        await tracker.track_wafer(
            wafer_id="W-001",
            lot_id="LOT-001",
            carrier_id="CAR-001",
        )
        await tracker.track_wafer(
            wafer_id="W-002",
            lot_id="LOT-001",
            carrier_id="CAR-001",
        )
        await tracker.record_process_start(
            wafer_id="W-001",
            lot_id="LOT-001",
            equipment_id="EQ-001",
        )

        # 执行载具追溯
        trace = await svc.trace_by_carrier("CAR-001")

        assert trace["carrier_id"] == "CAR-001"
        assert trace["wafer_count"] == 2
        assert len(trace["wafers"]) == 2

    @pytest.mark.asyncio
    async def test_trace_by_carrier_not_found(self, service):
        """测试按载具追溯不存在的载具"""
        svc, tracker, _ = service

        trace = await svc.trace_by_carrier("CAR-999")
        assert "error" in trace
        assert trace["error"] == "Carrier not found"

    @pytest.mark.asyncio
    async def test_impact_analysis(self, service):
        """测试影响分析"""
        svc, tracker, _ = service

        # 准备测试数据
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
            recipe_name="Recipe A",
        )
        await tracker.record_process_start(
            wafer_id="W-002",
            lot_id="LOT-001",
            equipment_id="EQ-001",
            recipe_name="Recipe A",
        )
        await tracker.record_process_start(
            wafer_id="W-003",
            lot_id="LOT-002",
            equipment_id="EQ-002",
            recipe_name="Recipe B",
        )

        # 执行影响分析
        now = datetime.now(timezone.utc)
        analysis = await svc.impact_analysis(
            equipment_id="EQ-001",
            time_range=(now - timedelta(hours=1), now + timedelta(hours=1)),
        )

        assert analysis["equipment_id"] == "EQ-001"
        assert analysis["total_wafers"] == 2
        assert analysis["total_lots"] == 1
        assert "LOT-001" in analysis["affected_lots"]
        assert "Recipe A" in analysis["recipes_used"]
        assert "Recipe B" not in analysis["recipes_used"]

    @pytest.mark.asyncio
    async def test_trace_quality_issue(self, service):
        """测试质量追溯"""
        svc, tracker, _ = service

        # 准备测试数据
        await tracker.track_wafer(
            wafer_id="W-001",
            lot_id="LOT-001",
        )
        await tracker.record_process_start(
            wafer_id="W-001",
            lot_id="LOT-001",
            equipment_id="EQ-001",
        )
        await tracker.record_process_end(
            wafer_id="W-001",
            lot_id="LOT-001",
            equipment_id="EQ-001",
            duration_seconds=300.0,
            measurements={"thickness": 100.5},
        )

        # 执行质量追溯
        trace = await svc.trace_quality_issue("W-001")

        assert trace["wafer_id"] == "W-001"
        assert trace["lot_id"] == "LOT-001"
        assert len(trace["quality_events"]) == 1
        assert trace["quality_events"][0]["measurements"] == {"thickness": 100.5}
        assert "PROCESS_END" in trace["measurements"]

    @pytest.mark.asyncio
    async def test_get_traceability_report(self, service):
        """测试生成追溯报告"""
        svc, tracker, _ = service

        # 准备测试数据
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

        # 生成报告
        report = await svc.get_traceability_report(
            lot_ids=["LOT-001"],
            wafer_ids=["W-001"],
        )

        assert report["summary"]["total_lots"] == 1
        assert report["summary"]["total_wafers"] == 1
        assert len(report["lots"]) == 1
        assert len(report["wafers"]) == 1

    @pytest.mark.asyncio
    async def test_verify_traceability_chain(self, service):
        """测试验证追溯链完整性"""
        svc, tracker, _ = service

        # 准备测试数据 - 正常流程
        await tracker.track_wafer(
            wafer_id="W-001",
            lot_id="LOT-001",
        )
        await tracker.record_wafer_loaded(
            wafer_id="W-001",
            lot_id="LOT-001",
            carrier_id="CAR-001",
            position=0,
        )
        await tracker.record_process_start(
            wafer_id="W-001",
            lot_id="LOT-001",
            equipment_id="EQ-001",
        )
        await tracker.record_process_end(
            wafer_id="W-001",
            lot_id="LOT-001",
            equipment_id="EQ-001",
            duration_seconds=300.0,
        )

        # 验证追溯链
        result = await svc.verify_traceability_chain("W-001")

        assert result["valid"] is True
        assert result["wafer_id"] == "W-001"
        assert result["event_count"] == 3
        assert len(result["issues"]) == 0

    @pytest.mark.asyncio
    async def test_verify_traceability_chain_not_found(self, service):
        """测试验证不存在的晶圆"""
        svc, tracker, _ = service

        result = await svc.verify_traceability_chain("W-999")
        assert result["valid"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_complete_traceability_scenario(self, service):
        """测试完整追溯场景"""
        svc, tracker, carrier_mgr = service

        # 1. 注册载具
        await carrier_mgr.register_carrier(
            carrier_id="CAR-001",
            carrier_type=CarrierType.FOUP,
            capacity=25,
        )

        # 2. 装载晶圆
        await carrier_mgr.load_carrier(
            carrier_id="CAR-001",
            wafer_ids=["W-001", "W-002", "W-003"],
            location="STOCK-01",
        )

        # 3. 移动到设备
        await carrier_mgr.move_carrier("CAR-001", "EQ-CLEANER")
        await carrier_mgr.arrive_at_equipment("CAR-001", "EQ-CLEANER", 0)

        # 4. 追踪每个晶圆的工艺
        for wafer_id in ["W-001", "W-002", "W-003"]:
            await tracker.track_wafer(
                wafer_id=wafer_id,
                lot_id="LOT-001",
                carrier_id="CAR-001",
            )
            await tracker.record_process_start(
                wafer_id=wafer_id,
                lot_id="LOT-001",
                equipment_id="EQ-CLEANER",
                recipe_name="Clean Recipe",
            )
            await tracker.record_process_end(
                wafer_id=wafer_id,
                lot_id="LOT-001",
                equipment_id="EQ-CLEANER",
                duration_seconds=600.0,
                measurements={"cleanliness": 0.99},
            )

        # 5. 执行各种追溯
        # 正向追踪
        lot_trace = await svc.trace_forward("LOT-001")
        assert lot_trace["summary"]["total_wafers"] == 3
        assert lot_trace["summary"]["total_events"] == 6

        # 单晶圆追溯
        wafer_trace = await svc.trace_backward("W-001")
        assert wafer_trace["summary"]["total_events"] == 2

        # 影响分析
        now = datetime.now(timezone.utc)
        impact = await svc.impact_analysis(
            equipment_id="EQ-CLEANER",
            time_range=(now - timedelta(hours=1), now + timedelta(hours=1)),
        )
        assert impact["total_wafers"] == 3
        assert impact["total_lots"] == 1

        # 载具追溯
        carrier_trace = await svc.trace_by_carrier("CAR-001")
        assert carrier_trace["wafer_count"] == 3

        # 质量追溯
        quality = await svc.trace_quality_issue("W-001")
        assert len(quality["measurements"]) > 0

        # 生成完整报告
        report = await svc.get_traceability_report(lot_ids=["LOT-001"])
        assert report["summary"]["total_lots"] == 1
