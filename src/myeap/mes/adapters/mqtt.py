"""MQTT MES Adapter

使用aiomqtt实现与MES系统的MQTT通信。
"""

import asyncio
import json
from typing import Any, Callable, Dict, Optional

import aiomqtt

from myeap.mes.adapters.base import MESAdapter, MESConfig
from myeap.observability.tracing import trace_async, create_span


class MqttAdapter(MESAdapter):
    """MQTT MES适配器

    使用aiomqtt库实现与MES系统的MQTT通信。

    Example:
        config = MESConfig(
            adapter_type="mqtt",
            host="localhost",
            port=1883,
            username="user",
            password="pass",
        )
        adapter = MqttAdapter(config)
        await adapter.connect()
        await adapter.subscribe("mes/eap/work_order", handler)
        await adapter.send("mes/eap/status", {"status": "running"})
    """

    def __init__(self, config: MESConfig):
        super().__init__(config)
        self._client: Optional[aiomqtt.Client] = None
        self._subscription_tasks: Dict[str, asyncio.Task] = {}
        self._running = False

    async def connect(self) -> None:
        """连接到MQTT Broker"""
        self.logger.info(
            "Connecting to MQTT broker",
            host=self.config.host,
            port=self.config.port,
            client_id=self.config.client_id,
        )

        try:
            # 解析主机和端口
            host = self.config.host
            port = self.config.port

            # 创建MQTT客户端
            self._client = aiomqtt.Client(
                hostname=host,
                port=port,
                client_id=self.config.client_id,
                keepalive=self.config.keepalive,
                clean_session=True,
            )

            # 设置TLS
            if self.config.tls_enabled:
                self._client.tls_set(
                    ca_certs=self.config.tls_ca_certs,
                    certfile=self.config.tls_certfile,
                    keyfile=self.config.tls_keyfile,
                )

            # 设置认证
            if self.config.username and self.config.password:
                self._client.username_pw_set(
                    self.config.username,
                    self.config.password,
                )

            # 连接
            await self._client.connect()

            self._running = True
            self._update_connection_status(True)

            self.logger.info(
                "Connected to MQTT broker",
                host=host,
                port=port,
            )

        except Exception as e:
            self.logger.error(
                "Failed to connect to MQTT broker",
                error=str(e),
                host=self.config.host,
                port=self.config.port,
            )
            raise

    async def disconnect(self) -> None:
        """断开MQTT连接"""
        self.logger.info("Disconnecting from MQTT broker")

        self._running = False

        # 取消所有订阅任务
        for task in self._subscription_tasks.values():
            task.cancel()
        self._subscription_tasks.clear()

        # 断开连接
        if self._client:
            try:
                await self._client.disconnect()
            except Exception as e:
                self.logger.warning(
                    "Error during MQTT disconnect",
                    error=str(e),
                )
            finally:
                self._client = None

        self._update_connection_status(False)
        self.logger.info("Disconnected from MQTT broker")

    @trace_async("mqtt_send")
    async def send(self, topic: str, message: Dict[str, Any]) -> None:
        """发送MQTT消息

        Args:
            topic: 消息主题（会自动添加前缀）
            message: 消息内容
        """
        if not self._client or not self._connected:
            raise RuntimeError("Not connected to MQTT broker")

        # 拼接完整主题
        full_topic = f"{self.config.topic_prefix}/{topic}" if not topic.startswith(self.config.topic_prefix) else topic

        # 获取消息类型用于指标
        message_type = message.get("type", "unknown")

        with create_span("mqtt_publish", attributes={"topic": full_topic, "message_type": message_type}) as span:
            try:
                payload = json.dumps(message, default=str)
                await self._client.publish(full_topic, payload)

                self._record_message_sent(message_type)
                span.set_attribute("mqtt.topic", full_topic)
                span.set_attribute("mqtt.qos", 0)

                self.logger.debug(
                    "MQTT message sent",
                    topic=full_topic,
                    message_type=message_type,
                )

            except Exception as e:
                self.logger.error(
                    "Failed to send MQTT message",
                    topic=full_topic,
                    error=str(e),
                )
                raise

    @trace_async("mqtt_subscribe")
    async def subscribe(self, topic: str, handler: Callable[[Dict[str, Any]], Any]) -> None:
        """订阅MQTT主题

        Args:
            topic: 订阅主题（会自动添加前缀）
            handler: 消息处理器
        """
        if not self._client or not self._connected:
            raise RuntimeError("Not connected to MQTT broker")

        # 拼接完整主题
        full_topic = f"{self.config.topic_prefix}/{topic}" if not topic.startswith(self.config.topic_prefix) else topic

        # 保存处理器
        self._subscriptions[full_topic] = handler

        # 创建订阅任务
        task = asyncio.create_task(self._subscription_loop(full_topic, handler))
        self._subscription_tasks[full_topic] = task

        self.logger.info(
            "Subscribed to MQTT topic",
            topic=full_topic,
        )

    async def _subscription_loop(self, topic: str, handler: Callable[[Dict[str, Any]], Any]) -> None:
        """订阅循环

        Args:
            topic: 订阅主题
            handler: 消息处理器
        """
        try:
            async with self._client.filtered_messages(topic) as messages:
                await self._client.subscribe(topic)

                self.logger.info(
                    "MQTT subscription active",
                    topic=topic,
                )

                async for message in messages:
                    if not self._running:
                        break

                    try:
                        payload = message.payload.decode("utf-8")
                        data = json.loads(payload)

                        message_type = data.get("type", "unknown")
                        self._record_message_received(message_type)

                        with create_span("mqtt_message_process", attributes={"topic": topic, "message_type": message_type}):
                            await handler(data)

                    except json.JSONDecodeError as e:
                        self.logger.error(
                            "Failed to decode MQTT message",
                            topic=topic,
                            error=str(e),
                        )
                    except Exception as e:
                        self.logger.error(
                            "Error processing MQTT message",
                            topic=topic,
                            error=str(e),
                        )

        except asyncio.CancelledError:
            self.logger.debug("Subscription cancelled", topic=topic)
        except Exception as e:
            self.logger.error(
                "Subscription error",
                topic=topic,
                error=str(e),
            )

    async def unsubscribe(self, topic: str) -> None:
        """取消订阅

        Args:
            topic: 订阅主题
        """
        full_topic = f"{self.config.topic_prefix}/{topic}" if not topic.startswith(self.config.topic_prefix) else topic

        # 取消订阅任务
        if full_topic in self._subscription_tasks:
            self._subscription_tasks[full_topic].cancel()
            del self._subscription_tasks[full_topic]

        # 移除处理器
        if full_topic in self._subscriptions:
            del self._subscriptions[full_topic]

        # 取消MQTT订阅
        if self._client and self._connected:
            await self._client.unsubscribe(full_topic)

        self.logger.info(
            "Unsubscribed from MQTT topic",
            topic=full_topic,
        )

    async def __aenter__(self) -> "MqttAdapter":
        """上下文管理器入口"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器出口"""
        await self.disconnect()
