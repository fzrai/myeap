"""MES Message Models

定义与MES系统通信的消息模型，使用Pydantic进行数据验证。
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


def utcnow() -> datetime:
    """Get current UTC datetime (timezone-aware)"""
    return datetime.now(timezone.utc)


class MESMessageType(str, Enum):
    """MES消息类型枚举"""

    WORK_ORDER = "work_order"  # 工单消息
    EQUIPMENT_STATUS = "equipment_status"  # 设备状态
    ALARM = "alarm"  # 报警消息
    COMPLETION = "completion"  # 工单完成
    PROCESS_START = "process_start"  # 加工开始
    PROCESS_END = "process_end"  # 加工结束
    MATERIAL_MOVE = "material_move"  # 物料移动
    DATA_COLLECTION = "data_collection"  # 数据采集
    RECIPE = "recipe"  # 配方消息
    COMMAND = "command"  # 命令消息
    RESPONSE = "response"  # 响应消息
    EVENT = "event"  # 事件消息


class AlarmSeverity(str, Enum):
    """报警严重级别"""

    CRITICAL = "CRITICAL"  # 严重
    MAJOR = "MAJOR"  # 主要
    MINOR = "MINOR"  # 次要
    WARNING = "WARNING"  # 警告
    INFO = "INFO"  # 信息


class EquipmentStatus(str, Enum):
    """设备状态"""

    IDLE = "IDLE"  # 空闲
    RUNNING = "RUNNING"  # 运行中
    PAUSED = "PAUSED"  # 暂停
    DOWN = "DOWN"  # 故障
    MAINTENANCE = "MAINTENANCE"  # 维护中
    PROCESSING = "PROCESSING"  # 加工中
    READY = "READY"  # 就绪


def datetime_encoder(v: datetime) -> str:
    """Custom datetime encoder for JSON serialization"""
    return v.isoformat() if v else None


class MESMessage(BaseModel):
    """MES消息基类

    所有MES消息的基类，定义通用字段。
    """

    model_config = ConfigDict(
        ser_json_timedelta="iso8601",
    )

    type: MESMessageType  # 消息类型
    message_id: Optional[str] = None  # 消息ID
    timestamp: datetime = Field(default_factory=utcnow)  # 时间戳
    source: str = "myeap"  # 消息来源
    destination: Optional[str] = None  # 消息目标
    correlation_id: Optional[str] = None  # 关联ID
    metadata: Optional[Dict[str, Any]] = None  # 扩展元数据


class WorkOrderMessage(BaseModel):
    """MES工单消息

    MES系统发送给EAP的工单信息。
    """

    model_config = ConfigDict(
        ser_json_timedelta="iso8601",
    )

    type: str = "work_order"
    mes_id: str  # MES工单号
    lot_id: str  # 批次ID
    recipe_name: str  # 配方名称
    wafer_count: int  # 晶圆数量
    priority: int = Field(default=5, ge=1, le=9)  # 优先级 1-9
    equipment_id: Optional[str] = None  # 指定设备ID
    carrier_id: Optional[str] = None  # 载具ID
    slot_map: Optional[List[int]] = None  # 槽位映射
    start_time: Optional[datetime] = None  # 计划开始时间
    due_time: Optional[datetime] = None  # 截止时间
    metadata: Optional[Dict[str, Any]] = None  # 扩展元数据


class EquipmentStatusMessage(BaseModel):
    """设备状态消息

    设备状态变更通知。
    """

    model_config = ConfigDict(
        ser_json_timedelta="iso8601",
    )

    type: str = "equipment_status"
    equipment_id: str  # 设备ID
    status: EquipmentStatus  # 设备状态
    sub_status: Optional[str] = None  # 子状态
    timestamp: datetime = Field(default_factory=utcnow)  # 时间戳
    reason_code: Optional[str] = None  # 状态原因码
    reason_text: Optional[str] = None  # 状态原因文本
    process_job_id: Optional[str] = None  # 当前加工任务ID
    lot_id: Optional[str] = None  # 当前批次ID
    wafer_count: Optional[int] = None  # 当前晶圆数量
    metadata: Optional[Dict[str, Any]] = None  # 扩展元数据


class AlarmMessage(BaseModel):
    """报警消息

    设备报警通知。
    """

    model_config = ConfigDict(
        ser_json_timedelta="iso8601",
    )

    type: str = "alarm"
    equipment_id: str  # 设备ID
    alarm_id: str  # 报警ID
    alarm_code: str  # 报警代码
    alarm_text: str  # 报警文本
    severity: AlarmSeverity  # 严重级别
    timestamp: datetime = Field(default_factory=utcnow)  # 时间戳
    ack_required: bool = True  # 是否需要确认
    ack_user: Optional[str] = None  # 确认用户
    ack_time: Optional[datetime] = None  # 确认时间
    clear_user: Optional[str] = None  # 清除用户
    clear_time: Optional[datetime] = None  # 清除时间
    metadata: Optional[Dict[str, Any]] = None  # 扩展元数据


class CompletionMessage(BaseModel):
    """工单完成消息

    工单加工完成报告。
    """

    model_config = ConfigDict(
        ser_json_timedelta="iso8601",
    )

    type: str = "completion"
    mes_id: str  # MES工单号
    lot_id: str  # 批次ID
    equipment_id: str  # 设备ID
    recipe_name: str  # 配方名称
    wafer_count: int  # 投入晶圆数量
    completed_count: int  # 完成数量
    good_count: int  # 良品数量
    reject_count: int  # 不良品数量
    yield_rate: float = Field(ge=0.0, le=100.0)  # 良率百分比
    start_time: datetime  # 开始时间
    end_time: datetime  # 结束时间
    cycle_time: Optional[float] = None  # 周期时间（秒）
    metadata: Optional[Dict[str, Any]] = None  # 扩展元数据


class ProcessStartMessage(BaseModel):
    """加工开始消息

    工单加工开始通知。
    """

    model_config = ConfigDict(
        ser_json_timedelta="iso8601",
    )

    type: str = "process_start"
    mes_id: str  # MES工单号
    lot_id: str  # 批次ID
    equipment_id: str  # 设备ID
    recipe_name: str  # 配方名称
    wafer_count: int  # 晶圆数量
    start_time: datetime = Field(default_factory=datetime.utcnow)  # 开始时间
    carrier_id: Optional[str] = None  # 载具ID
    slot_map: Optional[List[int]] = None  # 槽位映射
    metadata: Optional[Dict[str, Any]] = None  # 扩展元数据


class ProcessEndMessage(BaseModel):
    """加工结束消息

    工单加工结束通知。
    """

    model_config = ConfigDict(
        ser_json_timedelta="iso8601",
    )

    type: str = "process_end"
    mes_id: str  # MES工单号
    lot_id: str  # 批次ID
    equipment_id: str  # 设备ID
    wafer_count: int  # 晶圆数量
    end_time: datetime = Field(default_factory=utcnow)  # 结束时间
    reason: Optional[str] = None  # 结束原因 (COMPLETED, ABORTED, PAUSED)
    metadata: Optional[Dict[str, Any]] = None  # 扩展元数据


class MaterialMoveMessage(BaseModel):
    """物料移动消息

    物料在设备间移动的通知。
    """

    model_config = ConfigDict(
        ser_json_timedelta="iso8601",
    )

    type: str = "material_move"
    lot_id: str  # 批次ID
    carrier_id: str  # 载具ID
    from_equipment_id: Optional[str] = None  # 源设备ID
    to_equipment_id: Optional[str] = None  # 目标设备ID
    from_location: Optional[str] = None  # 源位置
    to_location: Optional[str] = None  # 目标位置
    wafer_count: int  # 晶圆数量
    timestamp: datetime = Field(default_factory=utcnow)  # 时间戳
    reason: Optional[str] = None  # 移动原因
    metadata: Optional[Dict[str, Any]] = None  # 扩展元数据


class DataCollectionMessage(BaseModel):
    """数据采集消息

    设备采集的数据报告。
    """

    model_config = ConfigDict(
        ser_json_timedelta="iso8601",
    )

    type: str = "data_collection"
    equipment_id: str  # 设备ID
    lot_id: Optional[str] = None  # 批次ID
    data_collection_plan_id: Optional[str] = None  # 数据采集计划ID
    data: Dict[str, Any]  # 采集的数据
    timestamp: datetime = Field(default_factory=utcnow)  # 时间戳
    triggered_by: Optional[str] = None  # 触发原因
    metadata: Optional[Dict[str, Any]] = None  # 扩展元数据


class RecipeMessage(BaseModel):
    """配方消息

    配方相关的消息。
    """

    model_config = ConfigDict(
        ser_json_timedelta="iso8601",
    )

    type: str = "recipe"
    recipe_name: str  # 配方名称
    action: str  # 操作类型 (DOWNLOAD, UPLOAD, DELETE, LIST)
    equipment_id: Optional[str] = None  # 设备ID
    recipe_path: Optional[str] = None  # 配方路径
    recipe_content: Optional[str] = None  # 配方内容（Base64编码）
    version: Optional[str] = None  # 配方版本
    timestamp: datetime = Field(default_factory=utcnow)  # 时间戳
    metadata: Optional[Dict[str, Any]] = None  # 扩展元数据


class CommandMessage(BaseModel):
    """命令消息

    MES发送给EAP的命令。
    """

    model_config = ConfigDict(
        ser_json_timedelta="iso8601",
    )

    type: str = "command"
    command_id: str  # 命令ID
    command_type: str  # 命令类型
    equipment_id: Optional[str] = None  # 目标设备ID
    parameters: Optional[Dict[str, Any]] = None  # 命令参数
    timestamp: datetime = Field(default_factory=utcnow)  # 时间戳
    priority: int = Field(default=5, ge=1, le=9)  # 优先级
    timeout: Optional[int] = None  # 超时时间（秒）
    metadata: Optional[Dict[str, Any]] = None  # 扩展元数据


class ResponseMessage(BaseModel):
    """响应消息

    EAP响应MES的消息。
    """

    model_config = ConfigDict(
        ser_json_timedelta="iso8601",
    )

    type: str = "response"
    original_message_id: Optional[str] = None  # 原消息ID
    status: str  # 响应状态 (SUCCESS, FAILED, PENDING)
    result: Optional[Dict[str, Any]] = None  # 结果数据
    error_code: Optional[str] = None  # 错误代码
    error_message: Optional[str] = None  # 错误消息
    timestamp: datetime = Field(default_factory=utcnow)  # 时间戳
    metadata: Optional[Dict[str, Any]] = None  # 扩展元数据


def parse_mes_message(data: Dict[str, Any]) -> BaseModel:
    """解析MES消息

    根据消息类型自动解析为对应的Pydantic模型。

    Args:
        data: 消息数据字典

    Returns:
        对应的Pydantic模型实例

    Raises:
        ValueError: 未知消息类型
    """
    message_type = data.get("type", "")

    type_mapping = {
        MESMessageType.WORK_ORDER.value: WorkOrderMessage,
        MESMessageType.EQUIPMENT_STATUS.value: EquipmentStatusMessage,
        MESMessageType.ALARM.value: AlarmMessage,
        MESMessageType.COMPLETION.value: CompletionMessage,
        MESMessageType.PROCESS_START.value: ProcessStartMessage,
        MESMessageType.PROCESS_END.value: ProcessEndMessage,
        MESMessageType.MATERIAL_MOVE.value: MaterialMoveMessage,
        MESMessageType.DATA_COLLECTION.value: DataCollectionMessage,
        MESMessageType.RECIPE.value: RecipeMessage,
        MESMessageType.COMMAND.value: CommandMessage,
        MESMessageType.RESPONSE.value: ResponseMessage,
    }

    model_class = type_mapping.get(message_type)
    if model_class:
        return model_class(**data)

    raise ValueError(f"Unknown MES message type: {message_type}")
