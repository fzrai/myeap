"""腔体控制模块

提供腔体状态管理和控制功能。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from dataclasses import dataclass, field


class ChamberState(Enum):
    """腔体状态"""

    IDLE = "IDLE"
    LOADING = "LOADING"
    PREPARING = "PREPARING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    UNLOADING = "UNLOADING"
    MAINTENANCE = "MAINTENANCE"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


class ChamberType(Enum):
    """腔体类型"""

    PROCESS = "process"
    BUFFER = "buffer"
    LOADLOCK = "loadlock"
    TRANSFER = "transfer"
    STORAGE = "storage"


@dataclass
class ChamberParameters:
    """腔体工艺参数"""

    temperature: Optional[float] = None
    target_temperature: Optional[float] = None
    pressure: Optional[float] = None
    target_pressure: Optional[float] = None
    humidity: Optional[float] = None
    target_humidity: Optional[float] = None
    gas_flows: Dict[str, float] = field(default_factory=dict)
    target_gas_flows: Dict[str, float] = field(default_factory=dict)
    rf_power: Optional[float] = None
    target_rf_power: Optional[float] = None
    dc_power: Optional[float] = None
    target_dc_power: Optional[float] = None
    rotation_speed: Optional[float] = None
    target_rotation_speed: Optional[float] = None


@dataclass
class ChamberControl:
    """腔体控制类

    提供腔体的状态监控和基本控制功能。
    """

    chamber_id: str
    equipment_id: str
    chamber_type: ChamberType = ChamberType.PROCESS

    # 状态
    state: ChamberState = ChamberState.UNKNOWN
    sub_state: Optional[str] = None

    # 工艺信息
    current_recipe: Optional[str] = None
    current_recipe_id: Optional[str] = None
    recipe_step: Optional[int] = None
    recipe_steps_total: Optional[int] = None

    # 参数
    parameters: ChamberParameters = field(default_factory=ChamberParameters)

    # 载具信息
    wafer_count: int = 0
    max_wafer_count: int = 25
    wafer_ids: List[str] = field(default_factory=list)

    # 时间戳
    state_changed_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None

    # 告警
    alarms: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_idle(self) -> bool:
        """腔体是否空闲"""
        return self.state == ChamberState.IDLE

    @property
    def is_available(self) -> bool:
        """腔体是否可用"""
        return self.state in (ChamberState.IDLE, ChamberState.PAUSED)

    @property
    def is_running(self) -> bool:
        """腔体是否正在运行"""
        return self.state == ChamberState.RUNNING

    @property
    def is_ready(self) -> bool:
        """腔体是否就绪"""
        return (
            self.state == ChamberState.IDLE
            and self.current_recipe is None
            and self.wafer_count == 0
        )

    @property
    def temperature_stable(self) -> bool:
        """温度是否稳定"""
        if self.parameters.target_temperature is None:
            return True
        if self.parameters.temperature is None:
            return False
        return abs(self.parameters.temperature - self.parameters.target_temperature) < 1.0

    @property
    def pressure_stable(self) -> bool:
        """压力是否稳定"""
        if self.parameters.target_pressure is None:
            return True
        if self.parameters.pressure is None:
            return False
        return abs(self.parameters.pressure - self.parameters.target_pressure) < 0.1

    def set_state(self, new_state: ChamberState, sub_state: Optional[str] = None) -> None:
        """设置腔体状态"""
        if self.state != new_state:
            self.state = new_state
            self.state_changed_at = datetime.utcnow()
        self.sub_state = sub_state
        self.last_updated = datetime.utcnow()

    def set_recipe(self, recipe_name: str, recipe_id: Optional[str] = None) -> None:
        """设置当前配方"""
        self.current_recipe = recipe_name
        self.current_recipe_id = recipe_id
        self.recipe_step = 0
        self.last_updated = datetime.utcnow()

    def update_parameters(self, params: ChamberParameters) -> None:
        """更新工艺参数"""
        self.parameters = params
        self.last_updated = datetime.utcnow()

    def load_wafer(self, wafer_id: str) -> bool:
        """加载晶圆"""
        if self.wafer_count >= self.max_wafer_count:
            return False
        if wafer_id in self.wafer_ids:
            return False
        self.wafer_ids.append(wafer_id)
        self.wafer_count = len(self.wafer_ids)
        self.last_updated = datetime.utcnow()
        return True

    def unload_wafer(self, wafer_id: str) -> bool:
        """卸载晶圆"""
        if wafer_id not in self.wafer_ids:
            return False
        self.wafer_ids.remove(wafer_id)
        self.wafer_count = len(self.wafer_ids)
        self.last_updated = datetime.utcnow()
        return True

    def unload_all(self) -> List[str]:
        """卸载所有晶圆"""
        unloaded = self.wafer_ids.copy()
        self.wafer_ids.clear()
        self.wafer_count = 0
        self.last_updated = datetime.utcnow()
        return unloaded

    def add_alarm(self, alarm_id: str, severity: str, message: str) -> None:
        """添加告警"""
        self.alarms[alarm_id] = {
            "severity": severity,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.last_updated = datetime.utcnow()

    def clear_alarm(self, alarm_id: str) -> bool:
        """清除告警"""
        if alarm_id in self.alarms:
            del self.alarms[alarm_id]
            self.last_updated = datetime.utcnow()
            return True
        return False

    def clear_all_alarms(self) -> None:
        """清除所有告警"""
        self.alarms.clear()
        self.last_updated = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "chamber_id": self.chamber_id,
            "equipment_id": self.equipment_id,
            "chamber_type": self.chamber_type.value,
            "state": self.state.value,
            "sub_state": self.sub_state,
            "current_recipe": self.current_recipe,
            "current_recipe_id": self.current_recipe_id,
            "recipe_step": self.recipe_step,
            "recipe_steps_total": self.recipe_steps_total,
            "parameters": {
                "temperature": self.parameters.temperature,
                "target_temperature": self.parameters.target_temperature,
                "pressure": self.parameters.pressure,
                "target_pressure": self.parameters.target_pressure,
                "humidity": self.parameters.humidity,
                "target_humidity": self.parameters.target_humidity,
                "gas_flows": self.parameters.gas_flows,
                "target_gas_flows": self.parameters.target_gas_flows,
                "rf_power": self.parameters.rf_power,
                "target_rf_power": self.parameters.target_rf_power,
                "dc_power": self.parameters.dc_power,
                "target_dc_power": self.parameters.target_dc_power,
                "rotation_speed": self.parameters.rotation_speed,
                "target_rotation_speed": self.parameters.target_rotation_speed,
            },
            "wafer_count": self.wafer_count,
            "max_wafer_count": self.max_wafer_count,
            "wafer_ids": self.wafer_ids,
            "state_changed_at": self.state_changed_at.isoformat() if self.state_changed_at else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "alarms": self.alarms,
        }


class ChamberManager:
    """腔体管理器

    管理设备的所有腔体。
    """

    def __init__(self, equipment_id: str):
        self.equipment_id = equipment_id
        self._chambers: Dict[str, ChamberControl] = {}

    def add_chamber(self, chamber: ChamberControl) -> None:
        """添加腔体"""
        self._chambers[chamber.chamber_id] = chamber

    def remove_chamber(self, chamber_id: str) -> bool:
        """移除腔体"""
        if chamber_id in self._chambers:
            del self._chambers[chamber_id]
            return True
        return False

    def get_chamber(self, chamber_id: str) -> Optional[ChamberControl]:
        """获取腔体"""
        return self._chambers.get(chamber_id)

    def get_all_chambers(self) -> List[ChamberControl]:
        """获取所有腔体"""
        return list(self._chambers.values())

    def get_by_type(self, chamber_type: ChamberType) -> List[ChamberControl]:
        """按类型获取腔体"""
        return [c for c in self._chambers.values() if c.chamber_type == chamber_type]

    def get_available(self) -> List[ChamberControl]:
        """获取可用腔体"""
        return [c for c in self._chambers.values() if c.is_available]

    def get_idle(self) -> List[ChamberControl]:
        """获取空闲腔体"""
        return [c for c in self._chambers.values() if c.is_idle]
