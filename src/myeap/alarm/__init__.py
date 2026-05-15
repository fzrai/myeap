"""报警管理模块

提供设备报警的接收、确认、清除、升级和通知功能。

主要组件:
- AlarmManager: 报警管理器，负责报警的生命周期管理
- AlarmEscalationService: 报警升级服务，自动升级未处理的报警
- AlarmNotifier: 报警通知服务，支持多种通知渠道
"""

from myeap.alarm.models import (
    Alarm,
    AlarmDefinition,
    AlarmEscalationPolicy,
    AlarmSeverity,
    AlarmStatus,
)
from myeap.alarm.manager import AlarmManager
from myeap.alarm.escalation import AlarmEscalationService
from myeap.alarm.notifier import AlarmNotifier, NotificationChannel

__all__ = [
    # Models
    "Alarm",
    "AlarmDefinition",
    "AlarmEscalationPolicy",
    "AlarmSeverity",
    "AlarmStatus",
    # Core classes
    "AlarmManager",
    "AlarmEscalationService",
    "AlarmNotifier",
    "NotificationChannel",
]
