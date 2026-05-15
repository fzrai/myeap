"""报警模型定义

定义报警相关的所有数据模型，包括报警实体、报警定义、升级策略等。
使用Pydantic进行数据验证。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AlarmSeverity(str, Enum):
    """报警严重程度枚举

    - CRITICAL: 必须立即处理
    - MAJOR: 需要尽快处理
    - MINOR: 需要处理但可以延迟
    - WARNING: 警告信息
    """

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    WARNING = "warning"

    @property
    def priority(self) -> int:
        """获取优先级数值，数值越小优先级越高"""
        priority_map = {
            AlarmSeverity.CRITICAL: 1,
            AlarmSeverity.MAJOR: 2,
            AlarmSeverity.MINOR: 3,
            AlarmSeverity.WARNING: 4,
        }
        return priority_map[self]

    @classmethod
    def from_string(cls, value: str) -> "AlarmSeverity":
        """从字符串转换为枚举值"""
        value_lower = value.lower()
        for member in cls:
            if member.value == value_lower:
                return member
        # 默认返回WARNING
        return cls.WARNING


class AlarmStatus(str, Enum):
    """报警状态枚举"""

    RAISED = "raised"  # 刚产生
    ACKNOWLEDGED = "acknowledged"  # 已确认
    CLEARED = "cleared"  # 已清除
    SUPPRESSED = "suppressed"  # 已屏蔽


class Alarm(BaseModel):
    """报警实体

    表示一个具体的设备报警实例。

    Attributes:
        id: 报警唯一标识
        equipment_id: 设备ID
        alarm_code: 报警代码
        alarm_text: 报警文本描述
        severity: 报警严重程度
        raised_at: 报警产生时间
        acknowledged_by: 确认人
        acknowledged_at: 确认时间
        cleared_by: 清除人
        cleared_at: 清除时间
        status: 报警状态
        escalated: 是否已升级
        escalation_level: 升级级别
        suppressed: 是否已屏蔽
        suppressed_until: 屏蔽截止时间
        parameters: 附加参数
    """

    id: str
    equipment_id: str
    alarm_code: str
    alarm_text: str
    severity: AlarmSeverity

    # 时间
    raised_at: datetime
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    cleared_by: Optional[str] = None
    cleared_at: Optional[datetime] = None

    # 状态
    status: AlarmStatus = AlarmStatus.RAISED

    # 升级
    escalated: bool = False
    escalation_level: int = 0

    # 屏蔽
    suppressed: bool = False
    suppressed_until: Optional[datetime] = None

    # 附加信息
    parameters: Optional[Dict[str, Any]] = None

    @property
    def is_active(self) -> bool:
        """判断报警是否处于活跃状态"""
        return self.status in (AlarmStatus.RAISED, AlarmStatus.ACKNOWLEDGED)

    @property
    def is_acknowledged(self) -> bool:
        """判断报警是否已确认"""
        return self.status == AlarmStatus.ACKNOWLEDGED

    @property
    def is_cleared(self) -> bool:
        """判断报警是否已清除"""
        return self.status == AlarmStatus.CLEARED

    @property
    def needs_attention(self) -> bool:
        """判断报警是否需要关注（未确认且未清除）"""
        return self.status == AlarmStatus.RAISED

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "equipment_id": self.equipment_id,
            "alarm_code": self.alarm_code,
            "alarm_text": self.alarm_text,
            "severity": self.severity.value,
            "raised_at": self.raised_at.isoformat() if self.raised_at else None,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "cleared_by": self.cleared_by,
            "cleared_at": self.cleared_at.isoformat() if self.cleared_at else None,
            "status": self.status.value,
            "escalated": self.escalated,
            "escalation_level": self.escalation_level,
            "suppressed": self.suppressed,
            "suppressed_until": self.suppressed_until.isoformat() if self.suppressed_until else None,
            "parameters": self.parameters,
        }

    def __repr__(self) -> str:
        return (
            f"Alarm(id={self.id}, code={self.alarm_code}, severity={self.severity.value}, "
            f"status={self.status.value}, equipment={self.equipment_id})"
        )


class AlarmDefinition(BaseModel):
    """报警定义

    定义某一类报警的默认属性和行为。

    Attributes:
        alarm_code: 报警代码
        equipment_type: 适用的设备类型
        severity: 默认严重程度
        description: 报警描述
        default_text: 默认报警文本
        suggested_action: 建议的处理动作
        auto_clear: 是否自动清除
        auto_clear_delay: 自动清除延迟（秒）
    """

    alarm_code: str
    equipment_type: str
    severity: AlarmSeverity
    description: str
    default_text: str
    suggested_action: Optional[str] = None
    auto_clear: bool = False
    auto_clear_delay: int = 0  # 秒

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "alarm_code": self.alarm_code,
            "equipment_type": self.equipment_type,
            "severity": self.severity.value,
            "description": self.description,
            "default_text": self.default_text,
            "suggested_action": self.suggested_action,
            "auto_clear": self.auto_clear,
            "auto_clear_delay": self.auto_clear_delay,
        }


class AlarmEscalationPolicy(BaseModel):
    """报警升级策略

    定义报警升级的规则和参数。

    Attributes:
        severity: 适用的严重程度
        initial_delay: 初始升级延迟（秒）
        escalation_interval: 升级间隔（秒）
        max_escalation_level: 最大升级级别
        notify_channels: 通知渠道列表
        assignees: 通知对象列表
    """

    severity: AlarmSeverity
    initial_delay: int  # 秒
    escalation_interval: int  # 秒
    max_escalation_level: int
    notify_channels: List[str]  # email, sms, webhook
    assignees: List[str]  # 用户列表

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "severity": self.severity.value,
            "initial_delay": self.initial_delay,
            "escalation_interval": self.escalation_interval,
            "max_escalation_level": self.max_escalation_level,
            "notify_channels": self.notify_channels,
            "assignees": self.assignees,
        }


class AlarmStatistics(BaseModel):
    """报警统计信息

    用于记录和展示报警统计数据。

    Attributes:
        total_count: 总报警数
        active_count: 活跃报警数
        by_severity: 按严重程度分类的报警数
        by_equipment: 按设备分类的报警数
        mtta: 平均确认时间（秒）
        escalation_count: 升级次数
        timestamp: 统计时间
    """

    total_count: int = 0
    active_count: int = 0
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_equipment: Dict[str, int] = Field(default_factory=dict)
    mtta: Optional[float] = None  # 平均确认时间（秒）
    escalation_count: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_count": self.total_count,
            "active_count": self.active_count,
            "by_severity": self.by_severity,
            "by_equipment": self.by_equipment,
            "mtta": self.mtta,
            "escalation_count": self.escalation_count,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
