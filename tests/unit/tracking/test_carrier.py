"""载具管理器测试"""

import pytest
from datetime import datetime

from myeap.tracking.carrier import CarrierManager
from myeap.tracking.models import (
    CarrierType,
    CarrierStatus,
)


class TestCarrierManager:
    """载具管理器测试"""

    @pytest.fixture
    def manager(self):
        """创建载具管理器实例"""
        return CarrierManager(db_manager=None)

    @pytest.mark.asyncio
    async def test_register_carrier(self, manager):
        """测试注册载具"""
        carrier = await manager.register_carrier(
            carrier_id="CAR-001",
            carrier_type=CarrierType.FOUP,
            capacity=25,
        )
        assert carrier.carrier_id == "CAR-001"
        assert carrier.carrier_type == CarrierType.FOUP
        assert carrier.capacity == 25
        assert carrier.status == CarrierStatus.IDLE

    @pytest.mark.asyncio
    async def test_register_duplicate_carrier(self, manager):
        """测试注册重复载具"""
        await manager.register_carrier(
            carrier_id="CAR-001",
            carrier_type=CarrierType.FOUP,
            capacity=25,
        )
        with pytest.raises(ValueError, match="already exists"):
            await manager.register_carrier(
                carrier_id="CAR-001",
                carrier_type=CarrierType.FOUP,
                capacity=25,
            )

    @pytest.mark.asyncio
    async def test_unregister_carrier(self, manager):
        """测试注销载具"""
        await manager.register_carrier(
            carrier_id="CAR-001",
            carrier_type=CarrierType.FOUP,
            capacity=25,
        )
        result = await manager.unregister_carrier("CAR-001")
        assert result is True

        # 再次注销应该返回False
        result = await manager.unregister_carrier("CAR-001")
        assert result is False

    @pytest.mark.asyncio
    async def test_load_carrier(self, manager):
        """测试装载晶圆到载具"""
        await manager.register_carrier(
            carrier_id="CAR-001",
            carrier_type=CarrierType.FOUP,
            capacity=25,
        )
        result = await manager.load_carrier(
            carrier_id="CAR-001",
            wafer_ids=["W-001", "W-002", "W-003"],
            location="STOCK-01",
        )
        assert result is True

        carrier = await manager.get_carrier("CAR-001")
        assert carrier.wafer_ids == ["W-001", "W-002", "W-003"]
        assert carrier.status == CarrierStatus.LOADED
        assert carrier.loaded_at is not None

    @pytest.mark.asyncio
    async def test_load_carrier_exceed_capacity(self, manager):
        """测试超过容量的装载"""
        await manager.register_carrier(
            carrier_id="CAR-001",
            carrier_type=CarrierType.FOUP,
            capacity=2,
        )
        result = await manager.load_carrier(
            carrier_id="CAR-001",
            wafer_ids=["W-001", "W-002", "W-003"],
            location="STOCK-01",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_unload_carrier(self, manager):
        """测试从载具卸载晶圆"""
        await manager.register_carrier(
            carrier_id="CAR-001",
            carrier_type=CarrierType.FOUP,
            capacity=25,
        )
        await manager.load_carrier(
            carrier_id="CAR-001",
            wafer_ids=["W-001", "W-002"],
            location="STOCK-01",
        )
        wafer_ids = await manager.unload_carrier("CAR-001")
        assert wafer_ids == ["W-001", "W-002"]

        carrier = await manager.get_carrier("CAR-001")
        assert len(carrier.wafer_ids) == 0
        assert carrier.status == CarrierStatus.IDLE
        assert carrier.unloaded_at is not None

    @pytest.mark.asyncio
    async def test_move_carrier(self, manager):
        """测试移动载具"""
        await manager.register_carrier(
            carrier_id="CAR-001",
            carrier_type=CarrierType.FOUP,
            capacity=25,
        )
        await manager.load_carrier(
            carrier_id="CAR-001",
            wafer_ids=["W-001"],
            location="STOCK-01",
        )
        result = await manager.move_carrier(
            carrier_id="CAR-001",
            destination="EQ-001",
        )
        assert result is True

        carrier = await manager.get_carrier("CAR-001")
        assert carrier.current_location == "EQ-001"
        assert carrier.status == CarrierStatus.IN_TRANSIT

        # 检查位置索引
        carrier_at_location = await manager.get_carrier_at_location("EQ-001")
        assert carrier_at_location is not None
        assert carrier_at_location.carrier_id == "CAR-001"

    @pytest.mark.asyncio
    async def test_arrive_at_equipment(self, manager):
        """测试载具到达设备"""
        await manager.register_carrier(
            carrier_id="CAR-001",
            carrier_type=CarrierType.FOUP,
            capacity=25,
        )
        await manager.load_carrier(
            carrier_id="CAR-001",
            wafer_ids=["W-001"],
            location="EQ-001",
        )
        await manager.move_carrier(
            carrier_id="CAR-001",
            destination="EQ-001",
        )
        result = await manager.arrive_at_equipment(
            carrier_id="CAR-001",
            equipment_id="EQ-001",
            position=0,
        )
        assert result is True

        carrier = await manager.get_carrier("CAR-001")
        assert carrier.status == CarrierStatus.AT_EQUIPMENT
        assert carrier.current_position == 0

    @pytest.mark.asyncio
    async def test_depart_from_equipment(self, manager):
        """测试载具离开设备"""
        await manager.register_carrier(
            carrier_id="CAR-001",
            carrier_type=CarrierType.FOUP,
            capacity=25,
        )
        await manager.load_carrier(
            carrier_id="CAR-001",
            wafer_ids=["W-001"],
            location="EQ-001",
        )
        await manager.move_carrier(
            carrier_id="CAR-001",
            destination="EQ-001",
        )
        await manager.arrive_at_equipment(
            carrier_id="CAR-001",
            equipment_id="EQ-001",
            position=0,
        )
        result = await manager.depart_from_equipment("CAR-001")
        assert result is True

        carrier = await manager.get_carrier("CAR-001")
        assert carrier.status == CarrierStatus.IN_TRANSIT
        assert carrier.current_position is None

    @pytest.mark.asyncio
    async def test_get_carriers_at_equipment(self, manager):
        """测试获取指定设备的载具"""
        await manager.register_carrier(
            carrier_id="CAR-001",
            carrier_type=CarrierType.FOUP,
            capacity=25,
        )
        await manager.register_carrier(
            carrier_id="CAR-002",
            carrier_type=CarrierType.FOUP,
            capacity=25,
        )
        await manager.register_carrier(
            carrier_id="CAR-003",
            carrier_type=CarrierType.FOUP,
            capacity=25,
        )

        await manager.load_carrier(
            carrier_id="CAR-001",
            wafer_ids=["W-001"],
            location="EQ-001",
        )
        await manager.move_carrier("CAR-001", "EQ-001")
        await manager.arrive_at_equipment("CAR-001", "EQ-001", 0)

        await manager.load_carrier(
            carrier_id="CAR-002",
            wafer_ids=["W-002"],
            location="EQ-001",
        )
        await manager.move_carrier("CAR-002", "EQ-001")
        await manager.arrive_at_equipment("CAR-002", "EQ-001", 1)

        await manager.load_carrier(
            carrier_id="CAR-003",
            wafer_ids=["W-003"],
            location="EQ-002",
        )
        await manager.move_carrier("CAR-003", "EQ-002")
        await manager.arrive_at_equipment("CAR-003", "EQ-002", 0)

        carriers_at_eq1 = await manager.get_carriers_at_equipment("EQ-001")
        assert len(carriers_at_eq1) == 2
        carrier_ids = [c.carrier_id for c in carriers_at_eq1]
        assert "CAR-001" in carrier_ids
        assert "CAR-002" in carrier_ids

        carriers_at_eq2 = await manager.get_carriers_at_equipment("EQ-002")
        assert len(carriers_at_eq2) == 1
        assert carriers_at_eq2[0].carrier_id == "CAR-003"

    @pytest.mark.asyncio
    async def test_get_carriers_by_status(self, manager):
        """测试按状态获取载具"""
        await manager.register_carrier(
            carrier_id="CAR-001",
            carrier_type=CarrierType.FOUP,
            capacity=25,
        )
        await manager.register_carrier(
            carrier_id="CAR-002",
            carrier_type=CarrierType.FOUP,
            capacity=25,
        )
        await manager.register_carrier(
            carrier_id="CAR-003",
            carrier_type=CarrierType.FOUP,
            capacity=25,
        )

        await manager.load_carrier(
            carrier_id="CAR-001",
            wafer_ids=["W-001"],
            location="EQ-001",
        )
        await manager.move_carrier("CAR-001", "EQ-001")
        await manager.arrive_at_equipment("CAR-001", "EQ-001", 0)

        await manager.load_carrier(
            carrier_id="CAR-002",
            wafer_ids=["W-002"],
            location="EQ-001",
        )
        await manager.move_carrier("CAR-002", "EQ-002")
        await manager.arrive_at_equipment("CAR-002", "EQ-002", 0)

        idle_carriers = await manager.get_carriers_by_status(CarrierStatus.IDLE)
        assert len(idle_carriers) == 1
        assert idle_carriers[0].carrier_id == "CAR-003"

        at_eq_carriers = await manager.get_carriers_by_status(CarrierStatus.AT_EQUIPMENT)
        assert len(at_eq_carriers) == 2

    @pytest.mark.asyncio
    async def test_get_carrier_count(self, manager):
        """测试获取载具数量统计"""
        await manager.register_carrier(
            carrier_id="CAR-001",
            carrier_type=CarrierType.FOUP,
            capacity=25,
        )
        await manager.register_carrier(
            carrier_id="CAR-002",
            carrier_type=CarrierType.FOUP,
            capacity=25,
        )

        counts = await manager.get_carrier_count()
        assert counts[CarrierStatus.IDLE] == 2
        assert counts[CarrierStatus.LOADED] == 0

    @pytest.mark.asyncio
    async def test_get_carrier_stats(self, manager):
        """测试获取载具统计信息"""
        await manager.register_carrier(
            carrier_id="CAR-001",
            carrier_type=CarrierType.FOUP,
            capacity=25,
        )
        await manager.register_carrier(
            carrier_id="CAR-002",
            carrier_type=CarrierType.FOUP,
            capacity=25,
        )

        stats = manager.get_carrier_stats()
        assert stats["total"] == 2
        assert "idle" in stats["by_status"]
