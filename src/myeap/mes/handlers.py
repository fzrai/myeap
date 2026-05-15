"""MES Message Handlers

MES消息处理器，管理消息处理逻辑。
"""

import asyncio
import logging
from typing import Any, Callable, Dict, Optional

from myeap.core.logging import LoggerMixin
from myeap.observability.metrics import get_metrics_collector
from myeap.observability.tracing import create_span, get_tracer


logger = logging.getLogger(__name__)


class MESSHandler(LoggerMixin):
    """MES消息处理器

    管理MES消息的处理逻辑，支持：
    - 按消息类型注册处理器
    - 消息预处理/后处理
    - 错误处理和重试
    - 指标记录

    Example:
        handler = MESSHandler()

        @handler.register("work_order")
        async def handle_work_order(message: dict):
            print(f"Received work order: {message['mes_id']}")

        @handler.register("equipment_status")
        async def handle_equipment_status(message: dict):
            print(f"Equipment {message['equipment_id']} status: {message['status']}")

        # 处理消息
        await handler.handle_message({"type": "work_order", "mes_id": "WO001"})
    """

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._metrics = get_metrics_collector()
        self._default_handler: Optional[Callable] = None
        self._error_handler: Optional[Callable] = None

    def register(
        self,
        message_type: str,
        handler: Optional[Callable] = None,
    ) -> Callable:
        """注册消息处理器

        Args:
            message_type: 消息类型，或直接传入函数（装饰器模式）
            handler: 处理器函数（可以是async或sync）

        Returns:
            装饰器（如果使用装饰器模式）

        Example:
            # 装饰器模式
            @handler.register("work_order")
            async def handle_work_order(message):
                pass

            # 函数模式
            handler.register("work_order", async def handle_work_order(message):
                pass)
        """
        # 如果message_type是callable，说明是装饰器模式使用: @handler.register
        if callable(message_type):
            func = message_type
            # 从函数名获取消息类型
            msg_type = getattr(func, '__name__', 'unknown')
            self._handlers[msg_type] = func
            self.logger.debug(
                f"Registered handler for message type: {msg_type}",
                handler=func.__name__,
            )
            return func

        # 正常注册模式
        def decorator(func: Callable) -> Callable:
            self._handlers[message_type] = func
            self.logger.debug(
                f"Registered handler for message type: {message_type}",
                handler=func.__name__,
            )
            return func

        # 如果handler已提供，直接注册
        if handler is not None:
            self._handlers[message_type] = handler
            self.logger.debug(
                f"Registered handler for message type: {message_type}",
                handler=handler.__name__,
            )
            return handler

        return decorator

    def unregister(self, message_type: str) -> bool:
        """注销消息处理器

        Args:
            message_type: 消息类型

        Returns:
            是否成功注销
        """
        if message_type in self._handlers:
            del self._handlers[message_type]
            self.logger.debug(f"Unregistered handler for message type: {message_type}")
            return True
        return False

    def set_default_handler(self, handler: Callable[[Dict[str, Any]], Any]) -> None:
        """设置默认处理器

        当没有找到特定类型处理器时调用。

        Args:
            handler: 默认处理器函数
        """
        self._default_handler = handler
        self.logger.debug("Set default handler")

    def set_error_handler(self, handler: Callable[[Dict[str, Any], Exception], Any]) -> None:
        """设置错误处理器

        当处理器执行出错时调用。

        Args:
            handler: 错误处理器函数，接收message和error参数
        """
        self._error_handler = handler
        self.logger.debug("Set error handler")

    async def handle_message(self, message: Dict[str, Any]) -> Any:
        """处理MES消息

        根据消息类型分发到对应的处理器。

        Args:
            message: MES消息字典

        Returns:
            处理结果

        Raises:
            HandlerNotFoundError: 未找到对应的处理器
            HandlerError: 处理器执行错误
        """
        message_type = message.get("type", "")
        message_id = message.get("message_id", "unknown")

        with create_span(
            "mes_handle_message",
            attributes={
                "message_type": message_type,
                "message_id": message_id,
            },
        ) as span:
            self.logger.info(
                "Handling MES message",
                message_type=message_type,
                message_id=message_id,
            )

            # 查找处理器
            handler = self._handlers.get(message_type)

            if handler is None and self._default_handler:
                handler = self._default_handler
                span.set_attribute("handler.type", "default")
            elif handler:
                span.set_attribute("handler.type", "specific")
            else:
                span.set_attribute("handler.type", "none")
                self.logger.warning(
                    "No handler found for message type",
                    message_type=message_type,
                )
                raise HandlerNotFoundError(f"No handler for message type: {message_type}")

            try:
                # 执行处理器
                result = await self._execute_handler(handler, message)
                span.set_attribute("handler.success", True)

                self.logger.info(
                    "Message handled successfully",
                    message_type=message_type,
                    message_id=message_id,
                )

                return result

            except Exception as e:
                span.set_attribute("handler.success", False)
                span.set_attribute("error", str(e))

                self.logger.error(
                    "Error handling message",
                    message_type=message_type,
                    message_id=message_id,
                    error=str(e),
                )

                # 调用错误处理器
                if self._error_handler:
                    try:
                        await self._execute_handler(self._error_handler, message, e)
                    except Exception as error_e:
                        self.logger.error(
                            "Error in error handler",
                            error=str(error_e),
                        )

                raise HandlerError(f"Handler error for {message_type}: {str(e)}") from e

    async def _execute_handler(
        self,
        handler: Callable,
        message: Dict[str, Any],
        error: Optional[Exception] = None,
    ) -> Any:
        """执行处理器

        支持async和sync处理器。

        Args:
            handler: 处理器函数
            message: 消息数据
            error: 可选的错误信息

        Returns:
            处理结果
        """
        import asyncio

        # 判断是否为async函数
        if asyncio.iscoroutinefunction(handler):
            if error:
                return await handler(message, error)
            return await handler(message)
        else:
            if error:
                return handler(message, error)
            return handler(message)

    def get_registered_handlers(self) -> Dict[str, str]:
        """获取已注册的处理器列表

        Returns:
            消息类型到处理器名称的映射
        """
        return {
            msg_type: handler.__name__
            for msg_type, handler in self._handlers.items()
        }

    def has_handler(self, message_type: str) -> bool:
        """检查是否有对应类型的处理器

        Args:
            message_type: 消息类型

        Returns:
            是否存在处理器
        """
        return message_type in self._handlers


class HandlerNotFoundError(Exception):
    """处理器未找到异常"""

    pass


class HandlerError(Exception):
    """处理器执行异常"""

    pass


class BatchMESSHandler(MESSHandler):
    """批量MES消息处理器

    支持批量处理MES消息。
    """

    def __init__(self, batch_size: int = 10, batch_timeout: float = 1.0):
        super().__init__()
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self._batch_queues: Dict[str, asyncio.Queue] = {}
        self._batch_tasks: Dict[str, asyncio.Task] = {}

    async def subscribe_to_batch(
        self,
        message_type: str,
        adapter: Any,
        topic: str,
    ) -> None:
        """订阅批量消息

        Args:
            message_type: 消息类型
            adapter: MES适配器
            topic: 订阅主题
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=self.batch_size * 2)
        self._batch_queues[message_type] = queue

        async def batch_collector(message: Dict[str, Any]) -> None:
            await queue.put(message)

        await adapter.subscribe(topic, batch_collector)

        handler = self._handlers.get(message_type)
        if handler:
            task = asyncio.create_task(self._batch_processor(message_type, handler, queue))
            self._batch_tasks[message_type] = task

    async def _batch_processor(
        self,
        message_type: str,
        handler: Callable,
        queue: asyncio.Queue,
    ) -> None:
        """批量处理器

        Args:
            message_type: 消息类型
            handler: 批量处理器函数
            queue: 消息队列
        """
        batch: list = []
        last_batch_time: float = 0

        while True:
            try:
                try:
                    message = await asyncio.wait_for(
                        queue.get(),
                        timeout=self.batch_timeout,
                    )
                    batch.append(message)
                    last_batch_time = asyncio.get_event_loop().time()
                except asyncio.TimeoutError:
                    pass

                # 检查是否需要处理批次
                current_time = asyncio.get_event_loop().time()
                should_process = (
                    len(batch) >= self.batch_size
                    or (len(batch) > 0 and current_time - last_batch_time >= self.batch_timeout)
                )

                if should_process and batch:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(batch)
                        else:
                            handler(batch)
                        batch = []
                    except Exception as e:
                        self.logger.error(
                            "Error in batch handler",
                            message_type=message_type,
                            error=str(e),
                        )
                        batch = []

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(
                    "Error in batch processor",
                    error=str(e),
                )

        # 处理剩余消息
        if batch:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(batch)
                else:
                    handler(batch)
            except Exception as e:
                self.logger.error(
                    "Error processing remaining batch",
                    error=str(e),
                )

    async def shutdown(self) -> None:
        """关闭批量处理器"""
        for task in self._batch_tasks.values():
            task.cancel()

        await asyncio.gather(*self._batch_tasks.values(), return_exceptions=True)
        self._batch_tasks.clear()
        self._batch_queues.clear()
