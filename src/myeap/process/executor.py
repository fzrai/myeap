"""工艺流程步骤执行器

提供步骤执行和处理器注册机制，支持超时控制和重试逻辑。
"""

import asyncio
import inspect
import logging
from datetime import datetime
from typing import Any, Callable, Coroutine, Dict, Optional

from myeap.process.models import ProcessStep, ProcessContext, StepResult, StepStatus, StepType

logger = logging.getLogger(__name__)

# 步骤处理器类型：可以是同步或异步函数，接收 (ProcessStep, ProcessContext) 返回 Dict 或 StepResult
StepHandler = Callable[[ProcessStep, ProcessContext], Any]


class ProcessExecutor:
    """工艺步骤执行器

    管理步骤处理器注册，提供步骤执行、超时控制和重试机制。

    Example:
        >>> executor = ProcessExecutor()
        >>> executor.register_handler(StepType.HEAT, heat_handler)
        >>> result = await executor.execute_step(step, context)
    """

    def __init__(self):
        self._handlers: Dict[StepType, StepHandler] = {}
        self._default_timeout: float = 300.0  # 默认超时 5 分钟

    def register_handler(self, step_type: StepType, handler: StepHandler) -> None:
        """注册步骤处理器

        Args:
            step_type: 步骤类型
            handler: 处理器函数，签名: (ProcessStep, ProcessContext) -> Any

        处理器可以是同步或异步函数，返回值可以是 Dict 或 StepResult。
        """
        if not callable(handler):
            raise TypeError(f"Handler must be callable, got {type(handler)}")
        self._handlers[step_type] = handler
        logger.debug(f"Registered handler for step type: {step_type.value}")

    def unregister_handler(self, step_type: StepType) -> bool:
        """注销步骤处理器

        Args:
            step_type: 步骤类型

        Returns:
            bool: 是否成功注销
        """
        if step_type in self._handlers:
            del self._handlers[step_type]
            return True
        return False

    def get_handler(self, step_type: StepType) -> Optional[StepHandler]:
        """获取步骤处理器"""
        return self._handlers.get(step_type)

    def has_handler(self, step_type: StepType) -> bool:
        """检查是否有对应处理器"""
        return step_type in self._handlers

    async def execute_step(
        self, step: ProcessStep, context: ProcessContext
    ) -> StepResult:
        """执行单个工艺步骤

        支持超时控制和重试机制。

        Args:
            step: 工艺步骤
            context: 执行上下文

        Returns:
            StepResult: 步骤执行结果
        """
        handler = self._handlers.get(step.step_type)
        if not handler:
            return StepResult(
                step_id=step.step_id,
                status=StepStatus.FAILED,
                error=f"No handler registered for step type: {step.step_type.value}",
                started_at=datetime.utcnow(),
            )

        timeout = step.timeout or self._default_timeout
        max_retries = step.retry_count
        last_error = None

        for attempt in range(max_retries + 1):
            started_at = datetime.utcnow()

            try:
                # 使用超时控制执行处理器
                result_data = await asyncio.wait_for(
                    self._invoke_handler(handler, step, context),
                    timeout=timeout,
                )

                completed_at = datetime.utcnow()

                # 如果处理器返回 StepResult，直接使用
                if isinstance(result_data, StepResult):
                    result = result_data
                    result.started_at = result.started_at or started_at
                    result.completed_at = result.completed_at or completed_at
                    result.retry_attempts = attempt
                    if not result.duration:
                        result.duration = (completed_at - started_at).total_seconds()
                    return result

                # 构造成功结果
                duration = (completed_at - started_at).total_seconds()
                return StepResult(
                    step_id=step.step_id,
                    status=StepStatus.COMPLETED,
                    data=result_data if isinstance(result_data, dict) else {"result": result_data},
                    started_at=started_at,
                    completed_at=completed_at,
                    duration=duration,
                    retry_attempts=attempt,
                )

            except asyncio.TimeoutError:
                last_error = f"Step '{step.step_id}' timed out after {timeout}s"
                logger.warning(
                    f"Step timeout: {step.step_id} (attempt {attempt + 1}/{max_retries + 1})"
                )
                if attempt < max_retries:
                    await asyncio.sleep(step.retry_delay)
                continue

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"Step error: {step.step_id} - {e} "
                    f"(attempt {attempt + 1}/{max_retries + 1})",
                    exc_info=True,
                )
                if attempt < max_retries:
                    await asyncio.sleep(step.retry_delay)
                continue

        # 所有重试都失败
        completed_at = datetime.utcnow()
        return StepResult(
            step_id=step.step_id,
            status=StepStatus.FAILED,
            error=last_error or "Unknown error",
            started_at=started_at,
            completed_at=completed_at,
            duration=(completed_at - started_at).total_seconds() if started_at else 0,
            retry_attempts=max_retries,
        )

    async def _invoke_handler(
        self,
        handler: StepHandler,
        step: ProcessStep,
        context: ProcessContext,
    ) -> Any:
        """调用处理器（自动处理同步/异步）"""
        if inspect.iscoroutinefunction(handler):
            return await handler(step, context)
        else:
            # 同步处理器在线程池中执行
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, handler, step, context)

    def set_default_timeout(self, timeout: float) -> None:
        """设置默认超时时间

        Args:
            timeout: 超时时间（秒）
        """
        if timeout <= 0:
            raise ValueError("Timeout must be positive")
        self._default_timeout = timeout

    def __repr__(self) -> str:
        registered = [t.value for t in self._handlers]
        return f"ProcessExecutor(handlers={registered})"
