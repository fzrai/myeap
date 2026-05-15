"""工艺流程引擎

核心流程执行引擎，支持顺序、并行、条件和循环步骤执行，
以及错误处理、暂停/恢复/中止等控制功能。
"""

import asyncio
import inspect
import logging
from datetime import datetime
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

from myeap.core.exceptions import MyEAPException
from myeap.process.executor import ProcessExecutor
from myeap.process.models import (
    ProcessContext,
    ProcessDefinition,
    ProcessState,
    ProcessStep,
    StepResult,
    StepStatus,
    StepType,
)

logger = logging.getLogger(__name__)


class ProcessError(MyEAPException):
    """流程引擎错误"""

    def __init__(self, message: str, process_id: Optional[str] = None, **kwargs: Any):
        super().__init__(message, code="PROCESS_ERROR", **kwargs)
        self.process_id = process_id


class ProcessEngine:
    """工艺流程引擎

    核心流程执行引擎，负责解析流程定义、调度步骤执行、处理错误
    和管理流程状态。

    Attributes:
        executor: 步骤执行器
        on_step_start: 步骤开始回调
        on_step_complete: 步骤完成回调
        on_error: 错误回调
        on_complete: 流程完成回调
        on_pause: 暂停回调
        on_abort: 中止回调
        on_progress: 进度回调

    Example:
        >>> executor = ProcessExecutor()
        >>> engine = ProcessEngine(executor)
        >>> definition = ProcessDefinition(...)
        >>> context = ProcessContext(...)
        >>> await engine.execute(definition, context)
    """

    def __init__(self, executor: Optional[ProcessExecutor] = None):
        """初始化流程引擎

        Args:
            executor: 步骤执行器，如果为None则创建默认执行器
        """
        self.executor = executor or ProcessExecutor()
        self._active_contexts: Dict[str, ProcessContext] = {}
        self._pause_events: Dict[str, asyncio.Event] = {}
        self._abort_flags: Set[str] = set()

        # 事件回调
        self.on_step_start: Optional[Callable[[ProcessStep, ProcessContext], Any]] = None
        self.on_step_complete: Optional[Callable[[StepResult, ProcessContext], Any]] = None
        self.on_error: Optional[Callable[[str, ProcessStep, ProcessContext], Any]] = None
        self.on_complete: Optional[Callable[[ProcessContext], Any]] = None
        self.on_pause: Optional[Callable[[ProcessContext], Any]] = None
        self.on_abort: Optional[Callable[[ProcessContext], Any]] = None
        self.on_progress: Optional[Callable[[ProcessStep, int, int, ProcessContext], Any]] = None

    # ---- 内部辅助 ----

    @staticmethod
    async def _invoke_callback(cb: Callable, *args: Any) -> None:
        """安全地调用回调函数（自动处理同步/异步）"""
        try:
            result = cb(*args)
            if inspect.iscoroutine(result):
                await result
        except Exception:
            pass

    async def _check_pause(self, process_id: str) -> None:
        """检查并等待暂停状态"""
        event = self._pause_events.get(process_id)
        if event:
            await event.wait()

    # ---- 状态属性 ----

    @property
    def active_count(self) -> int:
        """活跃流程数"""
        return len(self._active_contexts)

    @property
    def active_processes(self) -> List[str]:
        """活跃流程ID列表"""
        return list(self._active_contexts.keys())

    def get_context(self, process_id: str) -> Optional[ProcessContext]:
        """获取流程上下文"""
        return self._active_contexts.get(process_id)

    # ---- 流程执行 ----

    async def execute(
        self, definition: ProcessDefinition, context: ProcessContext
    ) -> ProcessContext:
        """执行工艺流程

        按流程定义顺序执行所有步骤，支持条件、并行、循环和错误处理。

        Args:
            definition: 流程定义
            context: 执行上下文

        Returns:
            ProcessContext: 执行后的上下文（包含所有步骤结果）

        Raises:
            ProcessError: 如果流程已经在运行
        """
        if context.process_id in self._active_contexts:
            raise ProcessError(
                f"Process '{context.process_id}' is already active",
                process_id=context.process_id,
            )

        # 空定义直接完成
        if not definition.steps:
            context.state = ProcessState.COMPLETED
            context.started_at = datetime.utcnow()
            context.completed_at = datetime.utcnow()
            return context

        # 验证流程定义
        errors = definition.validate()
        if errors:
            raise ProcessError(
                f"Invalid process definition: {'; '.join(errors)}",
                process_id=definition.process_id,
            )

        # 初始化上下文
        context.state = ProcessState.RUNNING
        context.started_at = datetime.utcnow()
        self._active_contexts[context.process_id] = context
        self._pause_events[context.process_id] = asyncio.Event()
        self._pause_events[context.process_id].set()  # 初始状态为非暂停

        try:
            # 确定起始步骤
            current_step_id = definition.start_step_id or (
                definition.steps[0].step_id if definition.steps else None
            )

            if not current_step_id:
                context.state = ProcessState.COMPLETED
                context.completed_at = datetime.utcnow()
                return context

            # 执行步骤链
            step_index = 0
            total_steps = len(definition.steps)

            while current_step_id:
                # 检查中止标志
                if context.process_id in self._abort_flags:
                    context.state = ProcessState.ABORTED
                    context.completed_at = datetime.utcnow()
                    if self.on_abort:
                        await self._invoke_callback(self.on_abort, context)
                    break

                # 检查暂停
                await self._check_pause(context.process_id)

                step = definition.get_step(current_step_id)
                if not step:
                    context.state = ProcessState.FAILED
                    context.error = f"Step '{current_step_id}' not found"
                    break

                context.current_step_id = current_step_id

                # 进度通知
                if self.on_progress:
                    await self._invoke_callback(
                        self.on_progress, step, step_index, total_steps, context
                    )

                # 执行步骤（根据类型分派）
                result = await self._dispatch_step(step, definition, context)

                context.set_step_result(step.step_id, result)
                step_index += 1

                # 处理步骤结果
                if result.is_success:
                    if self.on_step_complete:
                        await self._invoke_callback(
                            self.on_step_complete, result, context
                        )

                    # 确定下一步
                    next_id = definition.get_next_step_id(current_step_id)
                    current_step_id = next_id

                else:
                    # 步骤失败
                    error_code = result.error or "UNKNOWN_ERROR"
                    logger.error(
                        f"Step '{current_step_id}' failed: {result.error}"
                    )

                    if self.on_error:
                        await self._invoke_callback(
                            self.on_error, error_code, step, context
                        )

                    # 查找错误处理步骤
                    handler_step_id = definition.get_error_handler(error_code)
                    if not handler_step_id:
                        # 尝试通配符错误处理
                        handler_step_id = definition.get_error_handler("*")

                    if handler_step_id:
                        logger.info(
                            f"Executing error handler: {handler_step_id}"
                        )
                        current_step_id = handler_step_id
                    else:
                        # 没有错误处理，流程失败
                        context.state = ProcessState.FAILED
                        context.error = result.error
                        context.completed_at = datetime.utcnow()
                        break

            # 检查最终状态
            if context.state not in (
                ProcessState.FAILED,
                ProcessState.ABORTED,
            ):
                context.state = ProcessState.COMPLETED
                context.completed_at = datetime.utcnow()

        except Exception as e:
            logger.exception(f"Unexpected error in process '{context.process_id}': {e}")
            context.state = ProcessState.FAILED
            context.error = str(e)
            context.completed_at = datetime.utcnow()

        finally:
            # 清理
            self._active_contexts.pop(context.process_id, None)
            self._pause_events.pop(context.process_id, None)
            self._abort_flags.discard(context.process_id)

            # 完成回调
            if self.on_complete:
                await self._invoke_callback(self.on_complete, context)

        return context

    async def _dispatch_step(
        self,
        step: ProcessStep,
        definition: ProcessDefinition,
        context: ProcessContext,
    ) -> StepResult:
        """根据步骤类型分派执行

        Args:
            step: 当前步骤
            definition: 流程定义
            context: 执行上下文

        Returns:
            StepResult: 步骤执行结果
        """
        # 步骤开始回调
        if self.on_step_start:
            await self._invoke_callback(self.on_step_start, step, context)

        # 根据步骤类型执行
        if step.step_type == StepType.CONDITIONAL:
            return await self._execute_conditional(step, context)
        elif step.step_type == StepType.PARALLEL:
            return await self._execute_parallel(step, context)
        elif step.step_type == StepType.LOOP:
            return await self._execute_loop(step, definition, context)
        elif step.step_type == StepType.WAIT:
            return await self._execute_wait(step, context)
        else:
            # 普通步骤：委托给执行器
            return await self.executor.execute_step(step, context)

    async def _execute_conditional(
        self, step: ProcessStep, context: ProcessContext
    ) -> StepResult:
        """执行条件步骤

        根据 pre_condition 表达式或变量值选择分支。

        Args:
            step: 条件步骤
            context: 执行上下文

        Returns:
            StepResult: 计算结果（包含选中分支信息）
        """
        started_at = datetime.utcnow()

        # 计算条件
        condition_key = step.pre_condition or "default"
        selected_target = step.branch_targets.get(condition_key)

        if not selected_target:
            # 尝试从变量解析条件
            condition_value = context.get_var(condition_key)
            if condition_value is not None:
                selected_target = step.branch_targets.get(str(condition_value))

        if not selected_target:
            # 尝试默认分支
            selected_target = step.branch_targets.get("default")

        completed_at = datetime.utcnow()

        if selected_target:
            return StepResult(
                step_id=step.step_id,
                status=StepStatus.COMPLETED,
                data={
                    "branch": selected_target,
                    "condition": condition_key,
                    "next_step": selected_target,
                },
                started_at=started_at,
                completed_at=completed_at,
                duration=(completed_at - started_at).total_seconds(),
            )
        else:
            return StepResult(
                step_id=step.step_id,
                status=StepStatus.FAILED,
                error=f"No branch matched for condition '{condition_key}'",
                started_at=started_at,
                completed_at=completed_at,
                duration=(completed_at - started_at).total_seconds(),
            )

    async def _execute_parallel(
        self, step: ProcessStep, context: ProcessContext
    ) -> StepResult:
        """执行并行步骤

        同时执行多个子步骤。

        Args:
            step: 并行步骤
            context: 执行上下文

        Returns:
            StepResult: 汇总结果
        """
        started_at = datetime.utcnow()

        if not step.parallel_steps:
            return StepResult(
                step_id=step.step_id,
                status=StepStatus.FAILED,
                error="No parallel steps defined",
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        # 并发执行所有子步骤
        tasks = []
        for sub_step in step.parallel_steps:
            task = self.executor.execute_step(sub_step, context)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        completed_at = datetime.utcnow()
        duration = (completed_at - started_at).total_seconds()

        # 汇总结果
        parallel_results: Dict[str, Dict[str, Any]] = {}
        all_success = True
        errors = []

        for i, result in enumerate(results):
            sub_step = step.parallel_steps[i]
            if isinstance(result, Exception):
                parallel_results[sub_step.step_id] = {
                    "status": "failed",
                    "error": str(result),
                }
                all_success = False
                errors.append(f"{sub_step.step_id}: {result}")
            elif isinstance(result, StepResult):
                context.set_step_result(sub_step.step_id, result)
                parallel_results[sub_step.step_id] = {
                    "status": result.status.value,
                    "data": result.data,
                    "error": result.error,
                    "duration": result.duration,
                }
                if result.is_failure:
                    all_success = False
                    errors.append(f"{sub_step.step_id}: {result.error}")
            else:
                parallel_results[sub_step.step_id] = {"status": "unknown"}

        if all_success:
            return StepResult(
                step_id=step.step_id,
                status=StepStatus.COMPLETED,
                data={
                    "parallel_results": parallel_results,
                    "sub_step_count": len(step.parallel_steps),
                },
                started_at=started_at,
                completed_at=completed_at,
                duration=duration,
            )
        else:
            return StepResult(
                step_id=step.step_id,
                status=StepStatus.FAILED,
                error=f"Parallel execution failed: {'; '.join(errors)}",
                data={"parallel_results": parallel_results},
                started_at=started_at,
                completed_at=completed_at,
                duration=duration,
            )

    async def _execute_loop(
        self,
        step: ProcessStep,
        definition: ProcessDefinition,
        context: ProcessContext,
    ) -> StepResult:
        """执行循环步骤

        重复执行循环体步骤直到条件不满足。

        Args:
            step: 循环步骤
            definition: 流程定义
            context: 执行上下文

        Returns:
            StepResult: 循环执行结果
        """
        started_at = datetime.utcnow()

        if not step.loop_steps:
            return StepResult(
                step_id=step.step_id,
                status=StepStatus.FAILED,
                error="No loop steps defined",
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        iteration = 0
        loop_results: List[Dict[str, Any]] = []

        while iteration < step.max_iterations:
            # 检查中止
            if context.process_id in self._abort_flags:
                return StepResult(
                    step_id=step.step_id,
                    status=StepStatus.FAILED,
                    error="Loop aborted",
                    data={"iterations": iteration, "loop_results": loop_results},
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )

            # 检查循环条件
            if step.loop_condition:
                should_continue = self._evaluate_expression(
                    step.loop_condition, context
                )
                if not should_continue and iteration > 0:
                    break

            # 执行循环体中的所有步骤
            for sub_step in step.loop_steps:
                result = await self.executor.execute_step(sub_step, context)
                context.set_step_result(sub_step.step_id, result)
                loop_results.append(
                    {
                        "iteration": iteration,
                        "step_id": sub_step.step_id,
                        "status": result.status.value,
                        "error": result.error,
                        "duration": result.duration,
                    }
                )

                if result.is_failure:
                    completed_at = datetime.utcnow()
                    return StepResult(
                        step_id=step.step_id,
                        status=StepStatus.FAILED,
                        error=f"Loop iteration {iteration} failed at "
                        f"'{sub_step.step_id}': {result.error}",
                        data={
                            "iterations": iteration + 1,
                            "loop_results": loop_results,
                        },
                        started_at=started_at,
                        completed_at=completed_at,
                        duration=(completed_at - started_at).total_seconds(),
                    )

            iteration += 1

        completed_at = datetime.utcnow()
        return StepResult(
            step_id=step.step_id,
            status=StepStatus.COMPLETED,
            data={
                "iterations": iteration,
                "max_iterations": step.max_iterations,
                "loop_results": loop_results,
            },
            started_at=started_at,
            completed_at=completed_at,
            duration=(completed_at - started_at).total_seconds(),
        )

    async def _execute_wait(
        self, step: ProcessStep, context: ProcessContext
    ) -> StepResult:
        """执行等待步骤

        支持可中断的等待（中止时立即返回）。

        Args:
            step: 等待步骤
            context: 执行上下文

        Returns:
            StepResult: 等待结果
        """
        started_at = datetime.utcnow()
        wait_duration = step.duration or step.parameters.get("duration", 1.0)

        try:
            # 支持可中断等待
            await self._check_pause(context.process_id)

            # 分段等待，以便支持中止
            remaining = wait_duration
            while remaining > 0:
                if context.process_id in self._abort_flags:
                    return StepResult(
                        step_id=step.step_id,
                        status=StepStatus.SKIPPED,
                        error="Wait aborted",
                        started_at=started_at,
                        completed_at=datetime.utcnow(),
                    )
                chunk = min(remaining, 0.1)  # 100ms 分段
                await asyncio.sleep(chunk)
                remaining -= chunk

            completed_at = datetime.utcnow()
            return StepResult(
                step_id=step.step_id,
                status=StepStatus.COMPLETED,
                data={"waited": wait_duration},
                started_at=started_at,
                completed_at=completed_at,
                duration=(completed_at - started_at).total_seconds(),
            )

        except asyncio.CancelledError:
            return StepResult(
                step_id=step.step_id,
                status=StepStatus.SKIPPED,
                error="Wait cancelled",
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

    # ---- 流程控制 ----

    async def pause(self, process_id: str) -> bool:
        """暂停流程

        Args:
            process_id: 流程ID

        Returns:
            bool: 是否成功暂停
        """
        context = self._active_contexts.get(process_id)
        if not context:
            return False

        if context.state != ProcessState.RUNNING:
            return False

        context.state = ProcessState.PAUSED
        context.paused_at = datetime.utcnow()

        # 设置暂停事件
        if process_id in self._pause_events:
            self._pause_events[process_id].clear()

        if self.on_pause:
            await self._invoke_callback(self.on_pause, context)

        logger.info(f"Process '{process_id}' paused")
        return True

    async def resume(self, process_id: str) -> bool:
        """恢复流程

        Args:
            process_id: 流程ID

        Returns:
            bool: 是否成功恢复
        """
        context = self._active_contexts.get(process_id)
        if not context:
            return False

        if context.state != ProcessState.PAUSED:
            return False

        context.state = ProcessState.RUNNING
        context.paused_at = None

        # 恢复暂停事件
        if process_id in self._pause_events:
            self._pause_events[process_id].set()

        logger.info(f"Process '{process_id}' resumed")
        return True

    async def abort(self, process_id: str) -> bool:
        """中止流程

        Args:
            process_id: 流程ID

        Returns:
            bool: 是否成功中止
        """
        context = self._active_contexts.get(process_id)
        if not context:
            return False

        if context.is_terminal:
            return False

        # 设置中止标志
        self._abort_flags.add(process_id)

        # 如果处于暂停状态，先恢复以便中止
        if context.state == ProcessState.PAUSED:
            if process_id in self._pause_events:
                self._pause_events[process_id].set()

        context.state = ProcessState.ABORTED
        context.completed_at = datetime.utcnow()

        # 触发中止回调
        if self.on_abort:
            await self._invoke_callback(self.on_abort, context)

        logger.info(f"Process '{process_id}' aborted")
        return True

    # ---- 辅助方法 ----

    def _evaluate_expression(
        self, expression: str, context: ProcessContext
    ) -> bool:
        """简单的表达式求值

        支持的表达式格式：
        - "var_name" — 检查变量是否为真值
        - "var_name == value" — 比较相等
        - "var_name != value" — 比较不等
        - "var_name > value" — 大于比较
        - "var_name < value" — 小于比较
        - "var_name >= value" — 大于等于比较
        - "var_name <= value" — 小于等于比较

        Args:
            expression: 表达式字符串
            context: 执行上下文

        Returns:
            bool: 表达式结果
        """
        if not expression:
            return False

        expression = expression.strip()

        # 尝试比较运算符（按长度降序匹配，避免 >= 被 > 匹配）
        operators = [">=", "<=", "!=", "==", ">", "<"]
        for op in operators:
            if op in expression:
                parts = expression.split(op, 1)
                var_name = parts[0].strip()
                expected = parts[1].strip()
                actual_value = context.get_var(var_name)

                # 尝试类型转换
                try:
                    if "." in expected:
                        expected_value: Any = float(expected)
                    elif expected.isdigit() or (
                        expected.startswith("-") and expected[1:].isdigit()
                    ):
                        expected_value = int(expected)
                    else:
                        expected_value = expected.strip("\"'")
                except ValueError:
                    expected_value = expected.strip("\"'")

                if op == "==":
                    return actual_value == expected_value
                elif op == "!=":
                    return actual_value != expected_value
                elif op == ">":
                    return (
                        actual_value is not None
                        and expected_value is not None
                        and actual_value > expected_value
                    )
                elif op == "<":
                    return (
                        actual_value is not None
                        and expected_value is not None
                        and actual_value < expected_value
                    )
                elif op == ">=":
                    return (
                        actual_value is not None
                        and expected_value is not None
                        and actual_value >= expected_value
                    )
                elif op == "<=":
                    return (
                        actual_value is not None
                        and expected_value is not None
                        and actual_value <= expected_value
                    )

        # 简单变量真值检查
        value = context.get_var(expression)
        return bool(value)

    def __repr__(self) -> str:
        return f"ProcessEngine(active={self.active_count})"
