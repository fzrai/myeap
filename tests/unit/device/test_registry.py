"""设备注册表测试"""

import pytest
import asyncio

from myeap.device.equipment import (
    Equipment,
    EquipmentStatus,
    EquipmentType,
)
from myeap.device.registry import EquipmentRegistry


class TestEquipmentRegistry:
    """设备注册表测试"""

    @pytest.fixture
    def registry(self):
        """创建注册表实例"""
        return EquipmentRegistry()

    @pytest.fixture
    def sample_equipment(self):
        """创建示例设备"""
        return Equipment(
            equipment_id="eq-001",
            equipment_type=EquipmentType.CLEANER,
            name="Cleaner-01",
            host="192.168.1.100",
            port=5000,
            device_id=1,
        )

    @pytest.mark.asyncio
    async def test_register(self, registry, sample_equipment):
        """测试注册设备"""
        await registry.register(sample_equipment, None)
        assert registry.get_total_count() == 1

        retrieved = await registry.get("eq-001")
        assert retrieved is not None
        assert retrieved.equipment_id == "eq-001"

    @pytest.mark.asyncio
    async def test_register_duplicate(self, registry, sample_equipment):
        """测试重复注册"""
        await registry.register(sample_equipment, None)
        await registry.register(sample_equipment, None)  # 重复注册
        assert registry.get_total_count() == 1

    @pytest.mark.asyncio
    async def test_unregister(self, registry, sample_equipment):
        """测试注销设备"""
        await registry.register(sample_equipment, None)
        await registry.unregister("eq-001")
        assert registry.get_total_count() == 0

    @pytest.mark.asyncio
    async def test_get_or_raise(self, registry, sample_equipment):
        """测试获取设备或抛出异常"""
        await registry.register(sample_equipment, None)

        eq = await registry.get_or_raise("eq-001")
        assert eq.equipment_id == "eq-001"

        with pytest.raises(ValueError):
            await registry.get_or_raise("nonexistent")

    @pytest.mark.asyncio
    async def test_get_by_type(self, registry):
        """测试按类型获取设备"""
        eq1 = Equipment(
            equipment_id="eq-001",
            equipment_type=EquipmentType.CLEANER,
            name="Cleaner",
            host="127.0.0.1",
            port=5000,
            device_id=1,
        )
        eq2 = Equipment(
            equipment_id="eq-002",
            equipment_type=EquipmentType.CVD,
            name="CVD",
            host="127.0.0.2",
            port=5000,
            device_id=2,
        )
        eq3 = Equipment(
            equipment_id="eq-003",
            equipment_type=EquipmentType.CLEANER,
            name="Cleaner2",
            host="127.0.0.3",
            port=5000,
            device_id=3,
        )

        await registry.register(eq1, None)
        await registry.register(eq2, None)
        await registry.register(eq3, None)

        cleaner_eq = await registry.get_by_type(EquipmentType.CLEANER)
        assert len(cleaner_eq) == 2

        cvd_eq = await registry.get_by_type(EquipmentType.CVD)
        assert len(cvd_eq) == 1

    @pytest.mark.asyncio
    async def test_get_available(self, registry):
        """测试获取可用设备"""
        eq1 = Equipment(
            equipment_id="eq-001",
            equipment_type=EquipmentType.CLEANER,
            name="Available",
            host="127.0.0.1",
            port=5000,
            device_id=1,
        )
        eq1.status = EquipmentStatus.IDLE
        eq1.set_connected(True)

        eq2 = Equipment(
            equipment_id="eq-002",
            equipment_type=EquipmentType.CLEANER,
            name="Running",
            host="127.0.0.2",
            port=5000,
            device_id=2,
        )
        eq2.status = EquipmentStatus.RUNNING
        eq2.set_connected(True)

        eq3 = Equipment(
            equipment_id="eq-003",
            equipment_type=EquipmentType.CLEANER,
            name="Disconnected",
            host="127.0.0.3",
            port=5000,
            device_id=3,
        )
        eq3.status = EquipmentStatus.IDLE

        await registry.register(eq1, None)
        await registry.register(eq2, None)
        await registry.register(eq3, None)

        available = await registry.get_available(EquipmentType.CLEANER)
        assert len(available) == 1
        assert available[0].equipment_id == "eq-001"

    @pytest.mark.asyncio
    async def test_connected_count(self, registry):
        """测试连接计数"""
        eq1 = Equipment(
            equipment_id="eq-001",
            equipment_type=EquipmentType.CLEANER,
            name="Connected",
            host="127.0.0.1",
            port=5000,
            device_id=1,
        )
        eq1.set_connected(True)

        eq2 = Equipment(
            equipment_id="eq-002",
            equipment_type=EquipmentType.CLEANER,
            name="Disconnected",
            host="127.0.0.2",
            port=5000,
            device_id=2,
        )

        await registry.register(eq1, None)
        await registry.register(eq2, None)

        assert registry.get_connected_count() == 1
        assert registry.get_total_count() == 2

    @pytest.mark.asyncio
    async def test_group_management(self, registry):
        """测试分组管理"""
        eq1 = Equipment(
            equipment_id="eq-001",
            equipment_type=EquipmentType.CLEANER,
            name="Cleaner 1",
            host="127.0.0.1",
            port=5000,
            device_id=1,
        )
        eq2 = Equipment(
            equipment_id="eq-002",
            equipment_type=EquipmentType.CVD,
            name="CVD 1",
            host="127.0.0.2",
            port=5000,
            device_id=2,
        )

        await registry.register(eq1, None)
        await registry.register(eq2, None)

        # 添加到分组
        await registry.add_to_group("eq-001", "cleaners")
        await registry.add_to_group("eq-002", "deposition")

        groups = await registry.get_group("cleaners")
        assert len(groups) == 1
        assert groups[0].equipment_id == "eq-001"

        # 从分组移除
        await registry.remove_from_group("eq-001", "cleaners")
        groups = await registry.get_group("cleaners")
        assert len(groups) == 0

    @pytest.mark.asyncio
    async def test_update_status(self, registry):
        """测试更新状态"""
        eq = Equipment(
            equipment_id="eq-001",
            equipment_type=EquipmentType.CLEANER,
            name="Test",
            host="127.0.0.1",
            port=5000,
            device_id=1,
        )

        await registry.register(eq, None)

        await registry.update_status("eq-001", EquipmentStatus.RUNNING)
        retrieved = await registry.get("eq-001")
        assert retrieved.status == EquipmentStatus.RUNNING

    @pytest.mark.asyncio
    async def test_update_connection(self, registry):
        """测试更新连接状态"""
        eq = Equipment(
            equipment_id="eq-001",
            equipment_type=EquipmentType.CLEANER,
            name="Test",
            host="127.0.0.1",
            port=5000,
            device_id=1,
        )

        await registry.register(eq, None)
        await registry.update_connection("eq-001", True)

        retrieved = await registry.get("eq-001")
        assert retrieved.is_connected
        assert retrieved.status == EquipmentStatus.IDLE

    def test_get_stats(self, registry):
        """测试获取统计信息"""
        stats = registry.get_stats()
        assert stats["total"] == 0
        assert stats["connected"] == 0

    def test_count_by_type(self, registry):
        """测试按类型计数"""
        assert registry.get_count_by_type(EquipmentType.CLEANER) == 0

    def test_count_by_status(self, registry):
        """测试按状态计数"""
        assert registry.get_count_by_status(EquipmentStatus.IDLE) == 0
