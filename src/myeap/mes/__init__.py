"""MES Integration Module

MyEAP与MES系统通信的模块，支持MQTT、REST、Kafka三种适配器。

Example:
    from myeap.mes import MqttAdapter, MESSHandler
    from myeap.mes.models import WorkOrderMessage

    # 创建适配器
    adapter = MqttAdapter(config=MESConfig(
        adapter_type="mqtt",
        host="localhost",
        port=1883,
    ))

    # 创建处理器
    handler = MESSHandler()

    @handler.register("work_order")
    async def handle_work_order(message: dict):
        print(f"Received work order: {message}")

    # 使用适配器
    await adapter.connect()
    await adapter.subscribe("mes/eap/work_order", handler.handle_message)
"""

from myeap.mes.models import (
    MESMessage,
    WorkOrderMessage,
    EquipmentStatusMessage,
    AlarmMessage,
    CompletionMessage,
    MESMessageType,
    AlarmSeverity,
)
from myeap.mes.handlers import MESSHandler
from myeap.mes.adapters.base import MESAdapter, MESConfig
from myeap.mes.adapters.mqtt import MqttAdapter
from myeap.mes.adapters.rest import RestAdapter
from myeap.mes.adapters.kafka import KafkaAdapter

__all__ = [
    # Models
    "MESMessage",
    "WorkOrderMessage",
    "EquipmentStatusMessage",
    "AlarmMessage",
    "CompletionMessage",
    "MESMessageType",
    "AlarmSeverity",
    # Handlers
    "MESSHandler",
    # Adapters
    "MESAdapter",
    "MESConfig",
    "MqttAdapter",
    "RestAdapter",
    "KafkaAdapter",
]
