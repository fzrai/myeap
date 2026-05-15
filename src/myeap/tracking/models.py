"""追踪模型定义

定义载具、晶圆、工艺结果等追踪相关的数据模型。
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CarrierType(str, Enum):
    """载具类型"""

    FOUP = "foup"  # Front Opening Unified Pod
    FOSB = "fosb"  # Front Opening Shipping Box
    MAGAZINE = "magazine"  # 晶圆盒

    @classmethod
    def from_string(cls, value: str) -> "CarrierType":
        """从字符串转换为枚举值"""
        value_lower = value.lower()
        for member in cls:
            if member.value == value_lower:
                return member
        return cls.FOUP  # 默认值


class CarrierStatus(str, Enum):
    """载具状态"""

    IDLE = "idle"
    LOADED = "loaded"
    IN_TRANSIT = "in_transit"
    AT_EQUIPMENT = "at_equipment"
    WAITING = "waiting"

    @classmethod
    def from_string(cls, value: str) -> "CarrierStatus":
        """从字符串转换为枚举值"""
        value_lower = value.lower()
        for member in cls:
            if member.value == value_lower:
                return member
        return cls.IDLE  # 默认值


class WaferStatus(str, Enum):
    """晶圆状态"""

    IN_CARRIER = "in_carrier"
    IN_PROCESS = "in_process"
    COMPLETED = "completed"
    REJECTED = "rejected"

    @classmethod
    def from_string(cls, value: str) -> "WaferStatus":
        """从字符串转换为枚举值"""
        value_lower = value.lower()
        for member in cls:
            if member.value == value_lower:
                return member
        return cls.IN_CARRIER  # 默认值


class Carrier(BaseModel):
    """载具模型

    表示一个载具实体，包含载具的所有属性和状态信息。

    Attributes:
        carrier_id: 载具唯一标识
        carrier_type: 载具类型 (FOUP, FOSB, MAGAZINE)
        capacity: 载具容量 (晶圆数量)
        current_location: 当前位置 (equipment_id或location_id)
        current_position: 在设备中的位置
        wafer_ids: 装载的晶圆ID列表
        status: 载具状态
        created_at: 创建时间
        loaded_at: 装载时间
        unloaded_at: 卸载时间
    """

    carrier_id: str = Field(..., description="载具唯一标识")
    carrier_type: CarrierType = Field(..., description="载具类型")
    capacity: int = Field(..., ge=1, description="载具容量")

    # 位置
    current_location: Optional[str] = Field(
        default=None, description="当前位置 (equipment_id或location_id)"
    )
    current_position: Optional[int] = Field(
        default=None, description="在设备中的位置"
    )

    # 晶圆
    wafer_ids: List[str] = Field(default_factory=list, description="装载的晶圆ID列表")

    # 状态
    status: CarrierStatus = Field(
        default=CarrierStatus.IDLE, description="载具状态"
    )

    # 时间
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="创建时间"
    )
    loaded_at: Optional[datetime] = Field(default=None, description="装载时间")
    unloaded_at: Optional[datetime] = Field(default=None, description="卸载时间")

    @property
    def is_empty(self) -> bool:
        """载具是否为空"""
        return len(self.wafer_ids) == 0

    @property
    def is_full(self) -> bool:
        """载具是否已满"""
        return len(self.wafer_ids) >= self.capacity

    @property
    def available_slots(self) -> int:
        """可用槽位数"""
        return self.capacity - len(self.wafer_ids)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "carrier_id": self.carrier_id,
            "carrier_type": self.carrier_type.value,
            "capacity": self.capacity,
            "current_location": self.current_location,
            "current_position": self.current_position,
            "wafer_ids": self.wafer_ids,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "loaded_at": self.loaded_at.isoformat() if self.loaded_at else None,
            "unloaded_at": self.unloaded_at.isoformat() if self.unloaded_at else None,
        }


class WaferEvent(BaseModel):
    """晶圆事件模型

    记录晶圆的处理历史事件。

    Attributes:
        event_id: 事件唯一标识
        wafer_id: 晶圆ID
        lot_id: 批次ID
        event_type: 事件类型 (LOADED, UNLOADED, PROCESS_START, PROCESS_END等)
        equipment_id: 设备ID
        chamber_id: 腔体ID
        carrier_id: 载具ID
        position: 在载具中的位置
        recipe_id: 配方ID
        recipe_name: 配方名称
        timestamp: 事件时间
        duration_seconds: 持续时间 (秒)
        result: 事件结果
        measurements: 质量数据
    """

    event_id: str = Field(..., description="事件唯一标识")
    wafer_id: str = Field(..., description="晶圆ID")
    lot_id: str = Field(..., description="批次ID")

    # 事件类型
    event_type: str = Field(..., description="事件类型")

    # 位置信息
    equipment_id: Optional[str] = Field(default=None, description="设备ID")
    chamber_id: Optional[str] = Field(default=None, description="腔体ID")
    carrier_id: Optional[str] = Field(default=None, description="载具ID")
    position: Optional[int] = Field(default=None, description="在载具中的位置")

    # 工艺信息
    recipe_id: Optional[str] = Field(default=None, description="配方ID")
    recipe_name: Optional[str] = Field(default=None, description="配方名称")

    # 时间和结果
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="事件时间"
    )
    duration_seconds: Optional[float] = Field(
        default=None, description="持续时间 (秒)"
    )
    result: Optional[Dict[str, Any]] = Field(default=None, description="事件结果")

    # 质量数据
    measurements: Optional[Dict[str, float]] = Field(
        default=None, description="质量数据"
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "wafer_id": self.wafer_id,
            "lot_id": self.lot_id,
            "event_type": self.event_type,
            "equipment_id": self.equipment_id,
            "chamber_id": self.chamber_id,
            "carrier_id": self.carrier_id,
            "position": self.position,
            "recipe_id": self.recipe_id,
            "recipe_name": self.recipe_name,
            "timestamp": self.timestamp.isoformat(),
            "duration_seconds": self.duration_seconds,
            "result": self.result,
            "measurements": self.measurements,
        }


class Wafer(BaseModel):
    """晶圆模型

    表示一个晶圆实体，包含晶圆的所有属性和处理历史。

    Attributes:
        wafer_id: 晶圆唯一标识
        lot_id: 批次ID
        current_location: 当前位置 (equipment_id或location_id)
        current_carrier_id: 所在载具ID
        position: 在载具中的位置
        status: 晶圆状态
        history: 处理历史事件列表
    """

    wafer_id: str = Field(..., description="晶圆唯一标识")
    lot_id: str = Field(..., description="批次ID")

    # 位置
    current_location: Optional[str] = Field(
        default=None, description="当前位置"
    )
    current_carrier_id: Optional[str] = Field(
        default=None, description="所在载具ID"
    )
    position: Optional[int] = Field(
        default=None, description="在载具中的位置"
    )

    # 状态
    status: WaferStatus = Field(
        default=WaferStatus.IN_CARRIER, description="晶圆状态"
    )

    # 历史
    history: List[WaferEvent] = Field(
        default_factory=list, description="处理历史事件列表"
    )

    @property
    def is_in_carrier(self) -> bool:
        """是否在载具中"""
        return self.status == WaferStatus.IN_CARRIER

    @property
    def is_in_process(self) -> bool:
        """是否在处理中"""
        return self.status == WaferStatus.IN_PROCESS

    @property
    def is_completed(self) -> bool:
        """是否已完成"""
        return self.status == WaferStatus.COMPLETED

    @property
    def is_rejected(self) -> bool:
        """是否被拒绝"""
        return self.status == WaferStatus.REJECTED

    def add_event(self, event: WaferEvent) -> None:
        """添加历史事件"""
        self.history.append(event)

    def get_event_count(self) -> int:
        """获取事件数量"""
        return len(self.history)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "wafer_id": self.wafer_id,
            "lot_id": self.lot_id,
            "current_location": self.current_location,
            "current_carrier_id": self.current_carrier_id,
            "position": self.position,
            "status": self.status.value,
            "history": [event.to_dict() for event in self.history],
        }


class ProcessResult(BaseModel):
    """工艺结果模型

    表示一次工艺处理的结果。

    Attributes:
        wafer_id: 晶圆ID
        recipe_id: 配方ID
        equipment_id: 设备ID
        start_time: 开始时间
        end_time: 结束时间
        duration_seconds: 持续时间 (秒)
        status: 处理状态 (COMPLETED, ABORTED, FAILED)
        exit_code: 退出码
        measurements: 质量数据
        defects: 缺陷数量
        yield_data: 良率数据
    """

    wafer_id: str = Field(..., description="晶圆ID")
    recipe_id: str = Field(..., description="配方ID")
    equipment_id: str = Field(..., description="设备ID")

    start_time: datetime = Field(..., description="开始时间")
    end_time: datetime = Field(..., description="结束时间")
    duration_seconds: float = Field(..., description="持续时间 (秒)")

    # 结果
    status: str = Field(
        ..., description="处理状态 (COMPLETED, ABORTED, FAILED)"
    )
    exit_code: Optional[int] = Field(default=None, description="退出码")

    # 质量数据
    measurements: Dict[str, float] = Field(
        default_factory=dict, description="质量数据"
    )
    defects: Optional[int] = Field(default=None, description="缺陷数量")
    yield_data: Optional[Dict[str, Any]] = Field(
        default=None, description="良率数据"
    )

    @property
    def is_successful(self) -> bool:
        """处理是否成功"""
        return self.status == "COMPLETED"

    @property
    def is_failed(self) -> bool:
        """处理是否失败"""
        return self.status in ("FAILED", "ABORTED")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "wafer_id": self.wafer_id,
            "recipe_id": self.recipe_id,
            "equipment_id": self.equipment_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "exit_code": self.exit_code,
            "measurements": self.measurements,
            "defects": self.defects,
            "yield_data": self.yield_data,
        }


# Event type constants
class EventType:
    """事件类型常量"""

    # 载具事件
    CARRIER_REGISTERED = "CARRIER_REGISTERED"
    CARRIER_LOADED = "CARRIER_LOADED"
    CARRIER_UNLOADED = "CARRIER_UNLOADED"
    CARRIER_MOVED = "CARRIER_MOVED"
    CARRIER_ARRIVED = "CARRIER_ARRIVED"
    CARRIER_DEPARTED = "CARRIER_DEPARTED"

    # 晶圆事件
    WAFER_LOADED = "WAFER_LOADED"
    WAFER_UNLOADED = "WAFER_UNLOADED"
    PROCESS_START = "PROCESS_START"
    PROCESS_END = "PROCESS_END"
    PROCESS_ABORTED = "PROCESS_ABORTED"
    CHAMBER_START = "CHAMBER_START"
    CHAMBER_END = "CHAMBER_END"

    # 质量事件
    MEASUREMENT_TAKEN = "MEASUREMENT_TAKEN"
    DEFECT_DETECTED = "DEFECT_DETECTED"

    @classmethod
    def all_types(cls) -> List[str]:
        """获取所有事件类型"""
        return [
            getattr(cls, attr)
            for attr in dir(cls)
            if not attr.startswith("_") and attr.isupper()
        ]
