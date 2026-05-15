"""OpenTelemetry分布式追踪

提供统一的追踪接口，支持：
- 自动追踪SECS消息
- 追踪MES通信
- 追踪数据库操作
- 追踪业务流程
"""

import functools
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, Optional

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode, Span
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.context import Context


# 全局tracer
_tracer: Optional[trace.Tracer] = None
_propagator = TraceContextTextMapPropagator()


def setup_tracing(
    service_name: str,
    service_version: str = "0.1.0",
    enable_console_export: bool = False,
    exporter_endpoint: Optional[str] = None,
) -> None:
    """设置分布式追踪

    Args:
        service_name: 服务名称
        service_version: 服务版本
        enable_console_export: 是否启用控制台导出（调试用）
        exporter_endpoint: OTLP导出器端点（如 "http://localhost:4317"）
    """
    global _tracer

    # 创建资源
    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
        "deployment.environment": "development",
    })

    # 创建追踪提供者
    provider = TracerProvider(resource=resource)

    # 添加控制台导出器（调试用）
    if enable_console_export:
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(console_exporter))

    # 添加OTLP导出器（生产用）
    if exporter_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            otlp_exporter = OTLPSpanExporter(endpoint=exporter_endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        except ImportError:
            pass

    # 设置全局追踪提供者
    trace.set_tracer_provider(provider)

    # 获取tracer
    _tracer = trace.get_tracer(
        instrumenting_module_name=service_name,
        instrumenting_library_version=service_version,
    )


def get_tracer() -> trace.Tracer:
    """获取全局tracer"""
    global _tracer
    if _tracer is None:
        # 默认tracer
        setup_tracing("myeap")
        _tracer = trace.get_tracer("myeap")
    return _tracer


def trace_async(
    span_name: str,
    attributes: Optional[Dict[str, Any]] = None,
):
    """异步函数追踪装饰器

    Args:
        span_name: Span名称
        attributes: 额外的span属性

    Example:
        @trace_async("secs_message_process")
        async def process_message(msg):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(
                span_name,
                kind=trace.SpanKind.INTERNAL,
            ) as span:
                # 设置属性
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, str(value) if value is not None else "")

                # 设置函数名
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)

                try:
                    # 执行函数
                    result = await func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    # 记录异常
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise

        return wrapper
    return decorator


def trace_sync(
    span_name: str,
    attributes: Optional[Dict[str, Any]] = None,
):
    """同步函数追踪装饰器

    Args:
        span_name: Span名称
        attributes: 额外的span属性
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(
                span_name,
                kind=trace.SpanKind.INTERNAL,
            ) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, str(value) if value is not None else "")

                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)

                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise

        return wrapper
    return decorator


@contextmanager
def create_span(
    name: str,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Any]] = None,
):
    """创建span的上下文管理器

    Example:
        with create_span("process_batch", attributes={"batch_id": "123"}) as span:
            process_batch()
            span.set_attribute("batch_size", len(batch))
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name, kind=kind) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, str(value) if value is not None else "")
        yield span


class SecsMessageSpan:
    """SECS消息追踪上下文

    用于追踪SECS消息的完整生命周期。
    """

    def __init__(
        self,
        equipment_id: str,
        message_id: str,
        stream: int,
        function: int,
        direction: str,  # "send" or "receive"
        session_id: Optional[int] = None,
    ):
        self.equipment_id = equipment_id
        self.message_id = message_id
        self.stream = stream
        self.function = function
        self.direction = direction
        self.session_id = session_id
        self.span: Optional[Span] = None
        self.start_time: Optional[float] = None

    def __enter__(self) -> "SecsMessageSpan":
        tracer = get_tracer()
        self.span = tracer.start_span(
            f"SECS {self.direction} {self.message_id}",
            kind=trace.SpanKind.CLIENT if self.direction == "send" else trace.SpanKind.SERVER,
        )

        # 设置标准属性
        self.span.set_attribute("secs.equipment_id", self.equipment_id)
        self.span.set_attribute("secs.message_id", self.message_id)
        self.span.set_attribute("secs.stream", self.stream)
        self.span.set_attribute("secs.function", self.function)
        self.span.set_attribute("secs.direction", self.direction)

        if self.session_id:
            self.span.set_attribute("secs.session_id", self.session_id)

        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.span:
            duration = time.perf_counter() - self.start_time if self.start_time else 0
            self.span.set_attribute("secs.duration_ms", duration * 1000)

            if exc_type:
                self.span.record_exception(exc_val)
                self.span.set_status(Status(StatusCode.ERROR, str(exc_val)))
            else:
                self.span.set_status(Status(StatusCode.OK))

            self.span.end()
        return False

    def set_attribute(self, key: str, value: Any) -> None:
        """设置span属性"""
        if self.span:
            self.span.set_attribute(key, str(value) if value is not None else "")

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """添加span事件"""
        if self.span:
            self.span.add_event(name, attributes=attributes)


def inject_context(carrier: Dict[str, str]) -> Dict[str, str]:
    """注入追踪上下文到carrier（用于消息传播）"""
    return _propagator.inject(carrier)


def extract_context(carrier: Dict[str, str]) -> Context:
    """从carrier提取追踪上下文"""
    return _propagator.extract(carrier)
