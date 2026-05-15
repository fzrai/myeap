"""设备抽象测试"""

import pytest
from datetime import datetime

from myeap.device.equipment import (
    Equipment,
    EquipmentStatus,
    EquipmentType,
    ChamberInfo,
)


class TestEquipmentStatus:
    """设备状态测试"""

    def test_available_statuses(self):
        """测试可用状态"""
        assert EquipmentStatus.IDLE.is_available
        assert EquipmentStatus.PAUSED.is_available
        assert not EquipmentStatus.RUNNING.is_available
        assert not EquipmentStatus.ERROR.is_available

    def test_active_statuses(self):
        """测试活跃状态"""
        assert EquipmentStatus.RUNNING.is_active
        assert not EquipmentStatus.IDLE.is_active
        assert not EquipmentStatus.PAUSED.is_active

    def test_needs_attention_statuses(self):
        """测试需要关注的状态"""
        assert EquipmentStatus.ERROR.needs_attention
        assert EquipmentStatus.MAINTENANCE.needs_attention
        assert not EquipmentStatus.IDLE.needs_attention


class TestEquipmentType:
    """设备类型测试"""

    def test_from_string(self):
        """测试从字符串转换"""
        assert EquipmentType.from_string("cleaner") == EquipmentType.CLEANER
        assert EquipmentType.from_string("CVD") == EquipmentType.CVD
        assert EquipmentType.from_string("unknown_equipment") == EquipmentType.UNKNOWN

    def test_all_types_have_values(self):
        """测试所有类型都有值"""
        for eq_type in EquipmentType:
            assert eq_type.value is not None


class TestChamberInfo:
    """腔体信息测试"""

    def test_creation(self):
        """测试创建腔体信息"""
        chamber = ChamberInfo(
            chamber_id="ch-01",
            chamber_type="process",
            status="IDLE",
        )
        assert chamber.chamber_id == "ch-01"
        assert chamber.chamber_type == "process"
        assert chamber.status == "IDLE"
        assert chamber.current_recipe is None

    def test_to_dict(self):
        """测试转换为字典"""
        chamber = ChamberInfo(
            chamber_id="ch-01",
            chamber_type="process",
            status="RUNNING",
            current_recipe="clean_recipe",
            temperature=150.0,
            pressure=10.0,
        )
        data = chamber.to_dict()
        assert data["chamber_id"] == "ch-01"
        assert data["current_recipe"] == "clean_recipe"
        assert data["temperature"] == 150.0


class TestEquipment:
    """设备测试"""

    def test_creation(self):
        """测试创建设备"""
        equipment = Equipment(
            equipment_id="eq-001",
            equipment_type=EquipmentType.CLEANER,
            name="Cleaner-01",
            host="192.168.1.100",
            port=5000,
            device_id=1,
        )
        assert equipment.equipment_id == "eq-001"
        assert equipment.equipment_type == EquipmentType.CLEANER
        assert equipment.status == EquipmentStatus.UNKNOWN
        assert not equipment.is_connected

    def test_is_available(self):
        """测试设备可用性"""
        equipment = Equipment(
            equipment_id="eq-001",
            equipment_type=EquipmentType.CLEANER,
            name="Test",
            host="127.0.0.1",
            port=5000,
            device_id=1,
        )

        # 未连接时不可用
        assert not equipment.is_available

        # 连接但状态未知时不可用
        equipment.set_connected(True)
        assert not equipment.is_available

        # 连接且空闲时可用
        equipment.status = EquipmentStatus.IDLE
        assert equipment.is_available

    def test_set_connected(self):
        """测试设置连接状态"""
        equipment = Equipment(
            equipment_id="eq-001",
            equipment_type=EquipmentType.CLEANER,
            name="Test",
            host="127.0.0.1",
            port=5000,
            device_id=1,
        )

        equipment.set_connected(True)
        assert equipment.is_connected
        assert equipment.last_connected is not None
        assert equipment.status == EquipmentStatus.IDLE

        equipment.set_connected(False)
        assert not equipment.is_connected
        assert equipment.status == EquipmentStatus.OFFLINE

    def test_chamber_management(self):
        """测试腔体管理"""
        equipment = Equipment(
            equipment_id="eq-001",
            equipment_type=EquipmentType.CVD,
            name="CVD-01",
            host="127.0.0.1",
            port=5000,
            device_id=1,
        )

        chamber = ChamberInfo(
            chamber_id="ch-01",
            chamber_type="process",
            status="IDLE",
        )
        equipment.update_chamber(chamber)

        assert equipment.chamber_count == 1
        assert equipment.get_chamber("ch-01") is not None
        assert equipment.get_process_chambers()[0].chamber_id == "ch-01"

    def test_to_dict(self):
        """测试转换为字典"""
        equipment = Equipment(
            equipment_id="eq-001",
            equipment_type=EquipmentType.CLEANER,
            name="Cleaner-01",
            host="192.168.1.100",
            port=5000,
            device_id=1,
            manufacturer="Test Inc.",
            model="TC-100",
        )

        data = equipment.to_dict()
        assert data["equipment_id"] == "eq-001"
        assert data["equipment_type"] == "cleaner"
        assert data["manufacturer"] == "Test Inc."
        assert data["model"] == "TC-100"

    def test_repr(self):
        """测试字符串表示"""
        equipment = Equipment(
            equipment_id="eq-001",
            equipment_type=EquipmentType.CLEANER,
            name="Test",
            host="127.0.0.1",
            port=5000,
            device_id=1,
        )
        repr_str = repr(equipment)
        assert "eq-001" in repr_str
        assert "cleaner" in repr_str
