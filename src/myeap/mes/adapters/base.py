"""MES Adapter Base Classes

定义MES适配器基类，提供统一的接口规范。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from myeap.core.logging import LoggerMixin
from myeap.observability.metrics import get_metrics_collector


@dataclass
class MESConfig:
    """MES配置"""

    adapter_type: str  # mqtt, rest, kafka
    host: str = "localhost"  # Default host
    port: int = 1883  # Default port
    username: Optional[str] = None
    password: Optional[str] = None
    topic_prefix: str = "mes/eap"
    client_id: str = "myeap"
    # REST specific
    base_url: Optional[str] = None
    # Kafka specific
    bootstrap_servers: Optional[str] = None
    consumer_group: Optional[str] = None
    # MQTT specific
    keepalive: int = 60
    tls_enabled: bool = False
    tls_ca_certs: Optional[str] = None
    tls_certfile: Optional[str] = None
    tls_keyfile: Optional[str] = None


class MESAdapter(ABC, LoggerMixin):
    """MES适配器基类

    所有MES通信适配器必须继承此类并实现抽象方法。
    提供统一的接口用于：
    - 连接/断开MES系统
    - 发送消息
    - 订阅消息
    """

    def __init__(self, config: MESConfig):
        self.config = config
        self._connected = False
        self._metrics = get_metrics_collector()
        self._subscriptions: Dict[str, Callable] = {}

    @abstractmethod
    async def connect(self) -> None:
        """连接MES"""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接"""
        pass

    @abstractmethod
    async def send(self, topic: str, message: Dict[str, Any]) -> None:
        """发送消息到MES

        Args:
            topic: 消息主题
            message: 消息内容
        """
        pass

    @abstractmethod
    async def subscribe(self, topic: str, handler: Callable[[Dict[str, Any]], Any]) -> None:
        """订阅MES消息

        Args:
            topic: 订阅主题
            handler: 消息处理器
        """
        pass

    @abstractmethod
    async def unsubscribe(self, topic: str) -> None:
        """取消订阅

        Args:
            topic: 订阅主题
        """
        pass

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._connected

    def _record_message_sent(self, message_type: str) -> None:
        """记录消息发送"""
        self._metrics.mes_messages_sent.labels(
            adapter_type=self.config.adapter_type,
            message_type=message_type,
        ).inc()
        self.logger.debug(
            "MES message sent",
            adapter_type=self.config.adapter_type,
            message_type=message_type,
            topic_prefix=self.config.topic_prefix,
        )

    def _record_message_received(self, message_type: str) -> None:
        """记录消息接收"""
        self._metrics.mes_messages_received.labels(
            adapter_type=self.config.adapter_type,
            message_type=message_type,
        ).inc()

    def _update_connection_status(self, connected: bool) -> None:
        """更新连接状态"""
        self._connected = connected
        self._metrics.mes_connection_status.labels(
            adapter_type=self.config.adapter_type,
        ).set(1 if connected else 0)
