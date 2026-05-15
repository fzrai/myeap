"""Prometheus指标收集器

提供统一的指标定义和收集接口，支持：
- SECS/GEM协议指标
- 设备连接指标
- MES通信指标
- 业务指标
"""

from functools import lru_cache
from typing import Optional

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Info,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)


class MetricsCollector:
    """指标收集器"""

    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or CollectorRegistry()

        # =========================================
        # SECS/GEM协议指标
        # =========================================
        self.secs_messages_sent = Counter(
            "myeap_secs_messages_sent_total",
            "Total SECS messages sent",
            ["equipment_id", "message_id", "stream", "function"],
            registry=self.registry,
        )

        self.secs_messages_received = Counter(
            "myeap_secs_messages_received_total",
            "Total SECS messages received",
            ["equipment_id", "message_id", "stream", "function"],
            registry=self.registry,
        )

        self.secs_message_errors = Counter(
            "myeap_secs_message_errors_total",
            "Total SECS message errors",
            ["equipment_id", "error_type"],
            registry=self.registry,
        )

        self.secs_message_duration = Histogram(
            "myeap_secs_message_duration_seconds",
            "SECS message processing duration",
            ["equipment_id", "message_id", "operation"],
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0),
            registry=self.registry,
        )

        self.secs_connection_status = Gauge(
            "myeap_secs_connection_status",
            "SECS connection status (0=disconnected, 1=connected)",
            ["equipment_id", "host", "port"],
            registry=self.registry,
        )

        self.secs_active_sessions = Gauge(
            "myeap_secs_active_sessions",
            "Number of active SECS sessions",
            registry=self.registry,
        )

        self.secs_last_message_time = Gauge(
            "myeap_secs_last_message_time_seconds",
            "Unix timestamp of last SECS message",
            ["equipment_id"],
            registry=self.registry,
        )

        # =========================================
        # 设备指标
        # =========================================
        self.equipment_status = Gauge(
            "myeap_equipment_status",
            "Equipment status (enum value)",
            ["equipment_id", "equipment_type", "status"],
            registry=self.registry,
        )

        self.equipment_process_count = Gauge(
            "myeap_equipment_process_count",
            "Number of processes running on equipment",
            ["equipment_id"],
            registry=self.registry,
        )

        self.equipment_throughput = Histogram(
            "myeap_equipment_throughput",
            "Equipment throughput (wafers/hour)",
            ["equipment_id", "equipment_type"],
            buckets=(1, 5, 10, 20, 30, 40, 50, 75, 100, 150, 200),
            registry=self.registry,
        )

        self.equipment_cycle_time = Histogram(
            "myeap_equipment_cycle_time_seconds",
            "Equipment cycle time",
            ["equipment_id", "recipe_name"],
            buckets=(60, 120, 300, 600, 900, 1200, 1800, 3600),
            registry=self.registry,
        )

        # =========================================
        # MES通信指标
        # =========================================
        self.mes_messages_sent = Counter(
            "myeap_mes_messages_sent_total",
            "Total MES messages sent",
            ["adapter_type", "message_type"],
            registry=self.registry,
        )

        self.mes_messages_received = Counter(
            "myeap_mes_messages_received_total",
            "Total MES messages received",
            ["adapter_type", "message_type"],
            registry=self.registry,
        )

        self.mes_message_duration = Histogram(
            "myeap_mes_message_duration_seconds",
            "MES message processing duration",
            ["adapter_type", "operation"],
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
            registry=self.registry,
        )

        self.mes_connection_status = Gauge(
            "myeap_mes_connection_status",
            "MES connection status",
            ["adapter_type"],
            registry=self.registry,
        )

        # =========================================
        # 工单指标
        # =========================================
        self.work_orders_total = Counter(
            "myeap_work_orders_total",
            "Total work orders received",
            ["status", "equipment_type"],
            registry=self.registry,
        )

        self.work_orders_in_progress = Gauge(
            "myeap_work_orders_in_progress",
            "Work orders currently in progress",
            ["equipment_id"],
            registry=self.registry,
        )

        self.work_order_completion_time = Histogram(
            "myeap_work_order_completion_time_seconds",
            "Work order completion time",
            ["equipment_type", "recipe_name"],
            buckets=(60, 120, 300, 600, 900, 1200, 1800, 3600, 7200),
            registry=self.registry,
        )

        self.work_order_yield = Histogram(
            "myeap_work_order_yield_percent",
            "Work order yield percentage",
            ["equipment_type", "recipe_name"],
            buckets=(80, 85, 90, 92, 94, 96, 97, 98, 99, 99.5, 100),
            registry=self.registry,
        )

        # =========================================
        # 报警指标
        # =========================================
        self.alarms_raised = Counter(
            "myeap_alarms_raised_total",
            "Total alarms raised",
            ["equipment_id", "severity", "alarm_code"],
            registry=self.registry,
        )

        self.alarms_active = Gauge(
            "myeap_alarms_active",
            "Active alarms count",
            ["equipment_id", "severity"],
            registry=self.registry,
        )

        self.alarms_mean_time_to_ack = Histogram(
            "myeap_alarms_mtta_seconds",
            "Mean time to acknowledge alarm",
            ["severity"],
            buckets=(30, 60, 120, 300, 600, 1800, 3600),
            registry=self.registry,
        )

        # =========================================
        # 系统指标
        # =========================================
        self.system_info = Info(
            "myeap_system_info",
            "System information",
            registry=self.registry,
        )

        self.active_equipment_count = Gauge(
            "myeap_active_equipment_count",
            "Number of active equipment connections",
            registry=self.registry,
        )

        self.event_queue_size = Gauge(
            "myeap_event_queue_size",
            "Internal event queue size",
            ["queue_name"],
            registry=self.registry,
        )

        self.database_pool_size = Gauge(
            "myeap_database_pool_size",
            "Database connection pool size",
            ["state"],  # active, idle, overflow
            registry=self.registry,
        )

    def record_secs_message_sent(
        self,
        equipment_id: str,
        message_id: str,
        stream: int,
        function: int,
    ) -> None:
        """记录SECS消息发送"""
        self.secs_messages_sent.labels(
            equipment_id=equipment_id,
            message_id=message_id,
            stream=str(stream),
            function=str(function),
        ).inc()

    def record_secs_message_received(
        self,
        equipment_id: str,
        message_id: str,
        stream: int,
        function: int,
    ) -> None:
        """记录SECS消息接收"""
        self.secs_messages_received.labels(
            equipment_id=equipment_id,
            message_id=message_id,
            stream=str(stream),
            function=str(function),
        ).inc()

    def record_secs_message_error(
        self,
        equipment_id: str,
        error_type: str,
    ) -> None:
        """记录SECS消息错误"""
        self.secs_message_errors.labels(
            equipment_id=equipment_id,
            error_type=error_type,
        ).inc()

    def observe_secs_message_duration(
        self,
        equipment_id: str,
        message_id: str,
        operation: str,
        duration_seconds: float,
    ) -> None:
        """记录SECS消息处理时长"""
        self.secs_message_duration.labels(
            equipment_id=equipment_id,
            message_id=message_id,
            operation=operation,
        ).observe(duration_seconds)

    def set_connection_status(
        self,
        equipment_id: str,
        host: str,
        port: int,
        connected: bool,
    ) -> None:
        """设置连接状态"""
        self.secs_connection_status.labels(
            equipment_id=equipment_id,
            host=host,
            port=str(port),
        ).set(1 if connected else 0)

    def generate_metrics(self) -> bytes:
        """生成Prometheus格式的指标"""
        return generate_latest(self.registry)

    def get_content_type(self) -> str:
        """获取Prometheus内容类型"""
        return CONTENT_TYPE_LATEST


@lru_cache
def get_metrics_collector() -> MetricsCollector:
    """获取全局指标收集器单例"""
    return MetricsCollector()
