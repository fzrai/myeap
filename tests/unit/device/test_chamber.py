"""腔体控制测试"""

import pytest
from datetime import datetime

from myeap.device.chamber import (
    ChamberControl,
    ChamberManager,
    ChamberParameters,
    ChamberState,
    ChamberType,
)


class TestChamberState:
    """腔体状态测试"""

    def test_state_properties(self):
        """测试状态属性"""
        assert ChamberState.IDLE.value == "IDLE"
        assert ChamberState.RUNNING.value == "RUNNING"


class TestChamberControl:
    """腔体控制测试"""

    def test_creation(self):
        """测试创建腔体"""
        chamber = ChamberControl(
            chamber_id="ch-01",
            equipment_id="eq-001",
        )
        assert chamber.chamber_id == "ch-01"
        assert chamber.equipment_id == "eq-001"
        assert chamber.state == ChamberState.UNKNOWN
        assert chamber.wafer_count == 0

    def test_state_transitions(self):
        """测试状态转换"""
        chamber = ChamberControl(
            chamber_id="ch-01",
            equipment_id="eq-001",
        )

        chamber.set_state(ChamberState.IDLE)
        assert chamber.state == ChamberState.IDLE
        assert chamber.state_changed_at is not None

        chamber.set_state(ChamberState.RUNNING, "Deposition")
        assert chamber.state == ChamberState.RUNNING
        assert chamber.sub_state == "Deposition"

    def test_wafer_loading(self):
        """测试晶圆加载"""
        chamber = ChamberControl(
            chamber_id="ch-01",
            equipment_id="eq-001",
            max_wafer_count=3,
        )

        assert chamber.load_wafer("W001")
        assert chamber.wafer_count == 1
        assert "W001" in chamber.wafer_ids

        assert chamber.load_wafer("W002")
        assert chamber.wafer_count == 2

        # 测试重复加载
        assert not chamber.load_wafer("W001")
        assert chamber.wafer_count == 2

        # 测试超过最大数量
        assert chamber.load_wafer("W003")
        assert not chamber.load_wafer("W004")
        assert chamber.wafer_count == 3

    def test_wafer_unloading(self):
        """测试晶圆卸载"""
        chamber = ChamberControl(
            chamber_id="ch-01",
            equipment_id="eq-001",
        )
        chamber.load_wafer("W001")
        chamber.load_wafer("W002")

        assert chamber.unload_wafer("W001")
        assert chamber.wafer_count == 1
        assert "W001" not in chamber.wafer_ids

        # 测试卸载不存在的晶圆
        assert not chamber.unload_wafer("W999")

    def test_unload_all(self):
        """测试卸载所有晶圆"""
        chamber = ChamberControl(
            chamber_id="ch-01",
            equipment_id="eq-001",
        )
        chamber.load_wafer("W001")
        chamber.load_wafer("W002")
        chamber.load_wafer("W003")

        unloaded = chamber.unload_all()
        assert len(unloaded) == 3
        assert chamber.wafer_count == 0

    def test_alarm_management(self):
        """测试告警管理"""
        chamber = ChamberControl(
            chamber_id="ch-01",
            equipment_id="eq-001",
        )

        chamber.add_alarm("ALM001", "ERROR", "Temperature too high")
        assert "ALM001" in chamber.alarms
        assert chamber.alarms["ALM001"]["severity"] == "ERROR"

        assert chamber.clear_alarm("ALM001")
        assert "ALM001" not in chamber.alarms

        assert not chamber.clear_alarm("ALM999")

    def test_recipe_setting(self):
        """测试配方设置"""
        chamber = ChamberControl(
            chamber_id="ch-01",
            equipment_id="eq-001",
        )

        chamber.set_recipe("clean_recipe", "rcp-001")
        assert chamber.current_recipe == "clean_recipe"
        assert chamber.current_recipe_id == "rcp-001"
        assert chamber.recipe_step == 0

    def test_parameters_stability(self):
        """测试参数稳定性检查"""
        chamber = ChamberControl(
            chamber_id="ch-01",
            equipment_id="eq-001",
        )

        params = ChamberParameters(
            temperature=150.0,
            target_temperature=150.5,
            pressure=10.0,
            target_pressure=10.05,
        )
        chamber.update_parameters(params)

        assert chamber.temperature_stable
        assert chamber.pressure_stable

        # 测试不稳定
        params.temperature = 155.0
        chamber.update_parameters(params)
        assert not chamber.temperature_stable


class TestChamberManager:
    """腔体管理器测试"""

    def test_creation(self):
        """测试创建管理器"""
        manager = ChamberManager("eq-001")
        assert manager.equipment_id == "eq-001"
        assert len(manager.get_all_chambers()) == 0

    def test_chamber_operations(self):
        """测试腔体操作"""
        manager = ChamberManager("eq-001")

        chamber = ChamberControl(
            chamber_id="ch-01",
            equipment_id="eq-001",
            chamber_type=ChamberType.PROCESS,
        )
        chamber.set_state(ChamberState.IDLE)
        manager.add_chamber(chamber)

        assert manager.get_chamber("ch-01") is not None
        assert len(manager.get_all_chambers()) == 1

        # 测试按类型获取
        assert len(manager.get_by_type(ChamberType.PROCESS)) == 1
        assert len(manager.get_by_type(ChamberType.BUFFER)) == 0

        # 测试获取空闲腔体
        assert len(manager.get_idle()) == 1

        # 测试移除
        assert manager.remove_chamber("ch-01")
        assert manager.get_chamber("ch-01") is None
