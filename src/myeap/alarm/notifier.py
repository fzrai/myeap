"""报警通知服务

提供多种报警通知渠道，包括邮件、短信、Webhook等。
支持通知模板和通知历史记录。
"""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from myeap.alarm.models import Alarm, AlarmSeverity


class NotificationChannel(ABC):
    """通知渠道抽象基类

    所有通知渠道需要继承此类并实现send方法。
    """

    name: str = "base"

    @abstractmethod
    async def send(
        self,
        alarm: Alarm,
        recipient: Optional[str] = None,
        escalation_level: int = 0,
        message: Optional[str] = None,
        **kwargs: Any,
    ) -> bool:
        """发送通知

        Args:
            alarm: 报警对象
            recipient: 接收人
            escalation_level: 升级级别
            message: 附加消息
            **kwargs: 其他参数

        Returns:
            是否发送成功
        """
        pass

    def format_alarm_message(self, alarm: Alarm, escalation_level: int = 0, message: Optional[str] = None) -> str:
        """格式化报警消息"""
        parts = [
            f"[{alarm.severity.value.upper()}] {alarm.alarm_text}",
            f"Equipment: {alarm.equipment_id}",
            f"Code: {alarm.alarm_code}",
            f"Raised at: {alarm.raised_at.isoformat()}",
        ]

        if alarm.is_acknowledged:
            parts.append(f"Acknowledged by {alarm.acknowledged_by} at {alarm.acknowledged_at}")

        if escalation_level > 0:
            parts.append(f"Escalation Level: {escalation_level}")

        if message:
            parts.append(f"Message: {message}")

        return "\n".join(parts)


class EmailChannel(NotificationChannel):
    """邮件通知渠道

    通过SMTP发送邮件通知。
    """

    name: str = "email"

    def __init__(
        self,
        smtp_host: str = "localhost",
        smtp_port: int = 587,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        from_address: str = "alarm@myeap.local",
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_address = from_address
        self.use_tls = use_tls

    async def send(
        self,
        alarm: Alarm,
        recipient: Optional[str] = None,
        escalation_level: int = 0,
        message: Optional[str] = None,
        **kwargs: Any,
    ) -> bool:
        """发送邮件通知"""
        if not recipient:
            recipient = kwargs.get("default_recipient", "admin@myeap.local")

        subject = self._get_subject(alarm, escalation_level)
        body = self.format_alarm_message(alarm, escalation_level, message)

        # 实际实现中这里会调用SMTP发送邮件
        # 目前为模拟实现
        await asyncio.sleep(0.01)  # 模拟网络延迟

        return True

    def _get_subject(self, alarm: Alarm, escalation_level: int) -> str:
        """生成邮件主题"""
        prefix = "[CRITICAL]" if alarm.severity == AlarmSeverity.CRITICAL else ""
        if escalation_level > 0:
            prefix = f"[ESCALATED L{escalation_level}]"
        return f"{prefix} Alarm: {alarm.alarm_code} - {alarm.alarm_text[:50]}"


class SMSChannel(NotificationChannel):
    """短信通知渠道

    通过短信网关发送短信通知。
    """

    name: str = "sms"

    def __init__(
        self,
        api_url: str = "http://sms-gateway.local/api/send",
        api_key: Optional[str] = None,
    ):
        self.api_url = api_url
        self.api_key = api_key

    async def send(
        self,
        alarm: Alarm,
        recipient: Optional[str] = None,
        escalation_level: int = 0,
        message: Optional[str] = None,
        **kwargs: Any,
    ) -> bool:
        """发送短信通知"""
        if not recipient:
            return False

        # 格式化短信内容（限制长度）
        sms_text = self._format_sms(alarm, escalation_level)

        # 实际实现中这里会调用短信API发送
        await asyncio.sleep(0.01)  # 模拟网络延迟

        return True

    def _format_sms(self, alarm: Alarm, escalation_level: int) -> str:
        """格式化短信内容"""
        severity = alarm.severity.value.upper()
        if escalation_level > 0:
            severity = f"{severity}+L{escalation_level}"
        return f"[{severity}] {alarm.alarm_code}: {alarm.alarm_text[:50]}"


class WebhookChannel(NotificationChannel):
    """Webhook通知渠道

    通过HTTP POST发送Webhook通知。
    """

    name: str = "webhook"

    def __init__(
        self,
        webhook_url: str = "http://webhook.local/notify",
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 10,
    ):
        self.webhook_url = webhook_url
        self.headers = headers or {}
        self.timeout = timeout

    async def send(
        self,
        alarm: Alarm,
        recipient: Optional[str] = None,
        escalation_level: int = 0,
        message: Optional[str] = None,
        **kwargs: Any,
    ) -> bool:
        """发送Webhook通知"""
        payload = self._build_payload(alarm, escalation_level, message)

        # 实际实现中这里会发送HTTP请求
        await asyncio.sleep(0.01)  # 模拟网络延迟

        return True

    def _build_payload(
        self,
        alarm: Alarm,
        escalation_level: int,
        message: Optional[str],
    ) -> Dict[str, Any]:
        """构建Webhook载荷"""
        return {
            "type": "alarm",
            "alarm": alarm.to_dict(),
            "escalation_level": escalation_level,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }


class InAppChannel(NotificationChannel):
    """站内通知渠道

    发送应用内通知。
    """

    name: str = "inapp"

    def __init__(self):
        self._notifications: List[Dict[str, Any]] = []

    async def send(
        self,
        alarm: Alarm,
        recipient: Optional[str] = None,
        escalation_level: int = 0,
        message: Optional[str] = None,
        **kwargs: Any,
    ) -> bool:
        """发送站内通知"""
        notification = {
            "id": f"notif-{alarm.id}-{len(self._notifications)}",
            "alarm_id": alarm.id,
            "recipient": recipient,
            "title": self._get_title(alarm),
            "body": alarm.alarm_text,
            "severity": alarm.severity.value,
            "escalation_level": escalation_level,
            "message": message,
            "created_at": datetime.utcnow().isoformat(),
            "read": False,
        }

        self._notifications.append(notification)
        return True

    def _get_title(self, alarm: Alarm) -> str:
        """获取通知标题"""
        severity_labels = {
            AlarmSeverity.CRITICAL: "Critical Alarm",
            AlarmSeverity.MAJOR: "Major Alarm",
            AlarmSeverity.MINOR: "Minor Alarm",
            AlarmSeverity.WARNING: "Warning",
        }
        return severity_labels.get(alarm.severity, "Alarm")

    def get_notifications(self, recipient: Optional[str] = None, unread_only: bool = False) -> List[Dict[str, Any]]:
        """获取通知列表"""
        notifications = self._notifications
        if recipient:
            notifications = [n for n in notifications if n["recipient"] == recipient]
        if unread_only:
            notifications = [n for n in notifications if not n["read"]]
        return notifications


class AlarmNotifier:
    """报警通知服务

    统一管理多种通知渠道，支持渠道注册和批量通知。

    Attributes:
        channels: 已注册的通知渠道字典
    """

    def __init__(self):
        self.channels: Dict[str, NotificationChannel] = {}
        # 注册默认渠道
        self.register_channel(InAppChannel())

    def register_channel(self, channel: NotificationChannel) -> None:
        """注册通知渠道

        Args:
            channel: 通知渠道实例
        """
        self.channels[channel.name] = channel

    def unregister_channel(self, name: str) -> bool:
        """取消注册通知渠道

        Args:
            name: 渠道名称

        Returns:
            是否成功取消
        """
        if name in self.channels and name != "inapp":  # 保护内置渠道
            del self.channels[name]
            return True
        return False

    def get_channel(self, name: str) -> Optional[NotificationChannel]:
        """获取指定渠道

        Args:
            name: 渠道名称

        Returns:
            渠道实例，不存在返回None
        """
        return self.channels.get(name)

    async def notify(
        self,
        alarm: Alarm,
        recipient: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """发送报警通知到所有适用渠道

        Args:
            alarm: 报警对象
            recipient: 接收人
            **kwargs: 其他参数
        """
        channels = self._get_channels_for_alarm(alarm)

        tasks = []
        for channel_name in channels:
            channel = self.channels.get(channel_name)
            if channel:
                tasks.append(
                    channel.send(
                        alarm,
                        recipient=recipient,
                        escalation_level=kwargs.get("escalation_level", 0),
                        message=kwargs.get("message"),
                    )
                )

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def notify_alarm(
        self,
        alarm: Alarm,
        recipient: str,
        escalation_level: int,
        message: str,
    ) -> None:
        """发送升级通知

        Args:
            alarm: 报警对象
            recipient: 接收人
            escalation_level: 升级级别
            message: 通知消息
        """
        # 获取升级策略中指定的渠道
        channels = self._get_channels_for_alarm(alarm)

        tasks = []
        for channel_name in channels:
            channel = self.channels.get(channel_name)
            if channel:
                tasks.append(
                    channel.send(
                        alarm,
                        recipient=recipient,
                        escalation_level=escalation_level,
                        message=message,
                    )
                )

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def notify_custom(
        self,
        alarm: Alarm,
        channel_names: List[str],
        recipient: Optional[str] = None,
        escalation_level: int = 0,
        message: Optional[str] = None,
    ) -> None:
        """通过指定渠道发送通知

        Args:
            alarm: 报警对象
            channel_names: 渠道名称列表
            recipient: 接收人
            escalation_level: 升级级别
            message: 通知消息
        """
        tasks = []
        for channel_name in channel_names:
            channel = self.channels.get(channel_name)
            if channel:
                tasks.append(
                    channel.send(
                        alarm,
                        recipient=recipient,
                        escalation_level=escalation_level,
                        message=message,
                    )
                )

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _get_channels_for_alarm(self, alarm: Alarm) -> List[str]:
        """获取报警的通知渠道

        根据严重程度决定使用哪些渠道。

        Args:
            alarm: 报警对象

        Returns:
            渠道名称列表
        """
        if alarm.severity == AlarmSeverity.CRITICAL:
            return ["sms", "email", "webhook", "inapp"]
        elif alarm.severity == AlarmSeverity.MAJOR:
            return ["email", "webhook", "inapp"]
        else:
            return ["webhook", "inapp"]
