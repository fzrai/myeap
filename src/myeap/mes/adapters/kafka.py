"""Kafka MES Adapter

使用aiokafka实现与MES系统的Kafka消息通信。
"""

import asyncio
import json
from typing import Any, Callable, Dict, Optional

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

from myeap.mes.adapters.base import MESAdapter, MESConfig
from myeap.observability.tracing import trace_async, create_span


class KafkaAdapter(MESAdapter):
    """Kafka MES适配器

    使用aiokafka库实现与MES系统的Kafka消息通信。

    支持：
    - 生产者模式发送消息
    - 消费者模式订阅消息
    - 消费者组自动平衡

    Example:
        config = MESConfig(
            adapter_type="kafka",
            bootstrap_servers="localhost:9092",
            consumer_group="myeap",
        )
        adapter = KafkaAdapter(config)
        await adapter.connect()
        await adapter.send("mes-eap-work-orders", {"type": "work_order", "data": {...}})
        await adapter.subscribe("mes-mes-work-orders", handler)
    """

    def __init__(self, config: MESConfig):
        super().__init__(config)
        self._producer: Optional[AIOKafkaProducer] = None
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._consumer_tasks: Dict[str, asyncio.Task] = {}
        self._running = False

    async def connect(self) -> None:
        """连接到Kafka集群"""
        self.logger.info(
            "Connecting to Kafka",
            bootstrap_servers=self.config.bootstrap_servers or self.config.host,
        )

        try:
            bootstrap_servers = self.config.bootstrap_servers or self.config.host

            # 创建生产者
            self._producer = AIOKafkaProducer(
                bootstrap_servers=bootstrap_servers,
                client_id=self.config.client_id,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
            )

            await self._producer.start()

            self._running = True
            self._update_connection_status(True)

            self.logger.info(
                "Connected to Kafka",
                bootstrap_servers=bootstrap_servers,
            )

        except Exception as e:
            self.logger.error(
                "Failed to connect to Kafka",
                error=str(e),
            )
            raise

    async def disconnect(self) -> None:
        """断开Kafka连接"""
        self.logger.info("Disconnecting from Kafka")

        self._running = False

        # 取消所有消费者任务
        for task in self._consumer_tasks.values():
            task.cancel()
        self._consumer_tasks.clear()

        # 停止消费者
        if self._consumer:
            try:
                await self._consumer.stop()
            except Exception as e:
                self.logger.warning(
                    "Error stopping Kafka consumer",
                    error=str(e),
                )
            finally:
                self._consumer = None

        # 停止生产者
        if self._producer:
            try:
                await self._producer.stop()
            except Exception as e:
                self.logger.warning(
                    "Error stopping Kafka producer",
                    error=str(e),
                )
            finally:
                self._producer = None

        self._update_connection_status(False)
        self.logger.info("Disconnected from Kafka")

    @trace_async("kafka_send")
    async def send(self, topic: str, message: Dict[str, Any], key: Optional[str] = None) -> None:
        """发送Kafka消息

        Args:
            topic: Kafka主题
            message: 消息内容
            key: 可选的分区键
        """
        if not self._producer or not self._connected:
            raise RuntimeError("Not connected to Kafka")

        message_type = message.get("type", "unknown")

        with create_span("kafka_produce", attributes={"topic": topic, "message_type": message_type}) as span:
            try:
                # 转换为JSON
                value = json.dumps(message, default=str).encode("utf-8")
                key_bytes = key.encode("utf-8") if key else None

                # 发送消息
                await self._producer.send_and_wait(
                    topic,
                    value=value,
                    key=key_bytes,
                )

                self._record_message_sent(message_type)
                span.set_attribute("kafka.topic", topic)
                span.set_attribute("kafka.key", key or "")

                self.logger.debug(
                    "Kafka message sent",
                    topic=topic,
                    message_type=message_type,
                    key=key,
                )

            except Exception as e:
                self.logger.error(
                    "Failed to send Kafka message",
                    topic=topic,
                    error=str(e),
                )
                raise

    @trace_async("kafka_subscribe")
    async def subscribe(self, topic: str, handler: Callable[[Dict[str, Any]], Any]) -> None:
        """订阅Kafka主题

        Args:
            topic: Kafka主题
            handler: 消息处理器
        """
        if not self._connected:
            raise RuntimeError("Not connected to Kafka")

        # 创建消费者任务
        task = asyncio.create_task(self._consume_loop(topic, handler))
        self._consumer_tasks[topic] = task

        self.logger.info(
            "Started Kafka subscription",
            topic=topic,
            consumer_group=self.config.consumer_group,
        )

    async def _consume_loop(self, topic: str, handler: Callable[[Dict[str, Any]], Any]) -> None:
        """消费循环

        Args:
            topic: Kafka主题
            handler: 消息处理器
        """
        try:
            bootstrap_servers = self.config.bootstrap_servers or self.config.host
            group_id = self.config.consumer_group or self.config.client_id

            # 创建消费者
            consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=bootstrap_servers,
                group_id=group_id,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                auto_offset_reset="earliest",
                enable_auto_commit=True,
            )

            await consumer.start()

            self.logger.info(
                "Kafka consumer started",
                topic=topic,
                group_id=group_id,
            )

            # 消费消息
            async for msg in consumer:
                if not self._running:
                    break

                try:
                    data = msg.value
                    message_type = data.get("type", "unknown")
                    self._record_message_received(message_type)

                    with create_span(
                        "kafka_consume",
                        attributes={
                            "topic": topic,
                            "message_type": message_type,
                            "partition": msg.partition,
                            "offset": msg.offset,
                        },
                    ):
                        await handler(data)

                except json.JSONDecodeError as e:
                    self.logger.error(
                        "Failed to decode Kafka message",
                        topic=topic,
                        error=str(e),
                    )
                except Exception as e:
                    self.logger.error(
                        "Error processing Kafka message",
                        topic=topic,
                        error=str(e),
                    )

        except asyncio.CancelledError:
            self.logger.debug("Kafka consumer cancelled", topic=topic)
        except Exception as e:
            self.logger.error(
                "Kafka consumer error",
                topic=topic,
                error=str(e),
            )
        finally:
            try:
                await consumer.stop()
            except Exception:
                pass

    async def unsubscribe(self, topic: str) -> None:
        """取消订阅

        Args:
            topic: Kafka主题
        """
        if topic in self._consumer_tasks:
            self._consumer_tasks[topic].cancel()
            del self._consumer_tasks[topic]

        self.logger.info(
            "Unsubscribed from Kafka topic",
            topic=topic,
        )

    async def send_batch(self, topic: str, messages: list[Dict[str, Any]]) -> None:
        """批量发送消息

        Args:
            topic: Kafka主题
            messages: 消息列表
        """
        if not self._producer or not self._connected:
            raise RuntimeError("Not connected to Kafka")

        self.logger.debug(
            "Sending batch to Kafka",
            topic=topic,
            count=len(messages),
        )

        for message in messages:
            message_type = message.get("type", "unknown")
            value = json.dumps(message, default=str).encode("utf-8")
            await self._producer.send_and_wait(topic, value=value)
            self._record_message_sent(message_type)

        self.logger.debug(
            "Batch sent to Kafka",
            topic=topic,
            count=len(messages),
        )

    async def __aenter__(self) -> "KafkaAdapter":
        """上下文管理器入口"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器出口"""
        await self.disconnect()
