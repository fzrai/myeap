"""设备抽象模块

定义设备核心抽象，包括设备状态、类型、腔体信息等。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from dataclasses import dataclass, field


class EquipmentStatus(Enum):
    """设备状态枚举"""

    UNKNOWN = "UNKNOWN"
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    MAINTENANCE = "MAINTENANCE"
    ERROR = "ERROR"
    OFFLINE = "OFFLINE"

    @property
    def is_available(self) -> bool:
        """判断状态是否表示设备可用"""
        return self in (EquipmentStatus.IDLE, EquipmentStatus.PAUSED)

    @property
    def is_active(self) -> bool:
        """判断状态是否表示设备正在运行"""
        return self == EquipmentStatus.RUNNING

    @property
    def needs_attention(self) -> bool:
        """判断状态是否需要关注"""
        return self in (EquipmentStatus.ERROR, EquipmentStatus.MAINTENANCE)


class EquipmentType(Enum):
    """设备类型枚举"""

    CLEANER = "cleaner"
    CVD = "cvd"
    PVD = "pvd"
    ETCHER = "etcher"
    LITHOGRAPHY = "lithography"
    DIFFUSION = "diffusion"
    CMP = "cmp"
    PROBE = "probe"
    PACKAGE = "package"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, value: str) -> "EquipmentType":
        """从字符串转换为枚举值"""
        value_lower = value.lower()
        for member in cls:
            if member.value == value_lower:
                return member
        return cls.UNKNOWN


@dataclass
class ChamberInfo:
    """腔体信息

    Attributes:
        chamber_id: 腔体ID
        chamber_type: 腔体类型 (process, buffer, loadlock)
        status: 当前状态
        current_recipe: 当前运行的配方
        temperature: 温度 (摄氏度)
        pressure: 压力 (torr)
        humidity: 湿度 (可选)
        gas_flows: 气体流量 (可选)
    """

    chamber_id: str
    chamber_type: str  # process, buffer, loadlock
    status: str
    current_recipe: Optional[str] = None
    temperature: Optional[float] = None
    pressure: Optional[float] = None
    humidity: Optional[float] = None
    gas_flows: Optional[Dict[str, float]] = None
    last_updated: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "chamber_id": self.chamber_id,
            "chamber_type": self.chamber_type,
            "status": self.status,
            "current_recipe": self.current_recipe,
            "temperature": self.temperature,
            "pressure": self.pressure,
            "humidity": self.humidity,
            "gas_flows": self.gas_flows,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }


@dataclass
class Equipment:
    """设备抽象

    表示一个设备实体，包含设备的所有属性和状态信息。

    Attributes:
        equipment_id: 设备唯一标识
        equipment_type: 设备类型
        name: 设备名称
        host: 设备IP地址
        port: 设备端口
        device_id: SECS设备ID
        status: 当前状态
        sub_status: 子状态
        chambers: 腔体字典
        is_connected: 是否已连接
        last_connected: 最后连接时间
        last_message: 最后消息时间
        capabilities: 设备能力
        supported_recipes: 支持的配方列表
        config: 配置信息
    """

    equipment_id: str
    equipment_type: EquipmentType
    name: str
    host: str
    port: int
    device_id: int

    # 状态
    status: EquipmentStatus = EquipmentStatus.UNKNOWN
    sub_status: Optional[str] = None
    chambers: Dict[str, ChamberInfo] = field(default_factory=dict)

    # 连接信息
    is_connected: bool = False
    last_connected: Optional[datetime] = None
    last_message: Optional[datetime] = None

    # 能力
    capabilities: Dict[str, Any] = field(default_factory=dict)
    supported_recipes: List[str] = field(default_factory=list)

    # 配置
    config: Dict[str, Any] = field(default_factory=dict)

    # 元数据
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    software_version: Optional[str] = None

    @property
    def is_available(self) -> bool:
        """设备是否可用"""
        return self.is_connected and self.status.is_available

    @property
    def chamber_count(self) -> int:
        """腔体数量"""
        return len(self.chambers)

    @property
    def process_chamber_count(self) -> int:
        """工艺腔体数量"""
        return sum(1 for c in self.chambers.values() if c.chamber_type == "process")

    @property
    def is_online(self) -> bool:
        """设备是否在线"""
        return self.is_connected and self.status != EquipmentStatus.OFFLINE

    def get_chamber(self, chamber_id: str) -> Optional[ChamberInfo]:
        """获取指定腔体"""
        return self.chambers.get(chamber_id)

    def get_process_chambers(self) -> List[ChamberInfo]:
        """获取所有工艺腔体"""
        return [c for c in self.chambers.values() if c.chamber_type == "process"]

    def get_available_chambers(self) -> List[ChamberInfo]:
        """获取所有可用腔体"""
        return [c for c in self.chambers.values() if c.status == "IDLE"]

    def update_chamber(self, chamber_info: ChamberInfo) -> None:
        """更新腔体信息"""
        chamber_info.last_updated = datetime.utcnow()
        self.chambers[chamber_info.chamber_id] = chamber_info

    def set_connected(self, connected: bool) -> None:
        """设置连接状态"""
        self.is_connected = connected
        if connected:
            self.last_connected = datetime.utcnow()
            if self.status == EquipmentStatus.UNKNOWN:
                self.status = EquipmentStatus.IDLE
        else:
            self.status = EquipmentStatus.OFFLINE

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "equipment_id": self.equipment_id,
            "equipment_type": self.equipment_type.value,
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "device_id": self.device_id,
            "status": self.status.value,
            "sub_status": self.sub_status,
            "chambers": {k: v.to_dict() for k, v in self.chambers.items()},
            "is_connected": self.is_connected,
            "last_connected": self.last_connected.isoformat() if self.last_connected else None,
            "last_message": self.last_message.isoformat() if self.last_message else None,
            "capabilities": self.capabilities,
            "supported_recipes": self.supported_recipes,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "serial_number": self.serial_number,
            "software_version": self.software_version,
        }

    def __repr__(self) -> str:
        return (
            f"Equipment(id={self.equipment_id}, type={self.equipment_type.value}, "
            f"status={self.status.value}, connected={self.is_connected})"
        )
