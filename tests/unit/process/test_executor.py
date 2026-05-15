"""步骤执行器测试"""

import asyncio
import pytest

from myeap.process.executor import ProcessExecutor
from myeap.process.models import (
    ProcessContext,
    ProcessStep,
    StepResult,
    StepStatus,
    StepType,
)


class TestProcessExecutor:
    """步骤执行器测试"""

    def test_creation(self):
        executor = ProcessExecutor()
        assert len(executor._handlers) == 0
        assert executor._default_timeout == 300.0

    def test_register_handler(self):
        executor = ProcessExecutor()

        async def heat_handler(step, context):
            return {"temperature": 150.0}

        executor.register_handler(StepType.HEAT, heat_handler)
        assert executor.has_handler(StepType.HEAT)
        assert not executor.has_handler(StepType.PURGE)

    def test_register_invalid_handler(self):
        executor = ProcessExecutor()
        with pytest.raises(TypeError):
            executor.register_handler(StepType.HEAT, "not_callable")

    def test_unregister_handler(self):
        executor = ProcessExecutor()

        async def handler(step, context):
            return {}

        executor.register_handler(StepType.HEAT, handler)
        assert executor.unregister_handler(StepType.HEAT)
        assert not executor.has_handler(StepType.HEAT)
        assert not executor.unregister_handler(StepType.HEAT)  # 重复取消

    def test_get_handler(self):
        executor = ProcessExecutor()

        async def handler(step, context):
            return {}

        executor.register_handler(StepType.PUMP_DOWN, handler)
        h = executor.get_handler(StepType.PUMP_DOWN)
        assert h is handler
        assert executor.get_handler(StepType.PURGE) is None

    @pytest.mark.asyncio
    async def test_execute_step_no_handler(self):
        executor = ProcessExecutor()
        step = ProcessStep(
            step_id="step_01",
            name="Test",
            step_type=StepType.HEAT,
        )
        context = ProcessContext(process_id="proc_001", equipment_id="eq_001")

        result = await executor.execute_step(step, context)
        assert result.status == StepStatus.FAILED
        assert "No handler" in result.error

    @pytest.mark.asyncio
    async def test_execute_step_sync_handler(self):
        executor = ProcessExecutor()

        def sync_handler(step, context):
            return {"temperature": 200.0}

        executor.register_handler(StepType.HEAT, sync_handler)

        step = ProcessStep(
            step_id="step_01",
            name="Heat",
            step_type=StepType.HEAT,
        )
        context = ProcessContext(process_id="proc_001", equipment_id="eq_001")

        result = await executor.execute_step(step, context)
        assert result.status == StepStatus.COMPLETED
        assert result.data["temperature"] == 200.0
        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.duration >= 0

    @pytest.mark.asyncio
    async def test_execute_step_async_handler(self):
        executor = ProcessExecutor()

        async def async_handler(step, context):
            await asyncio.sleep(0.01)
            return {"result": "done"}

        executor.register_handler(StepType.PROCESS, async_handler)

        step = ProcessStep(
            step_id="step_01",
            name="Process",
            step_type=StepType.PROCESS,
        )
        context = ProcessContext(process_id="proc_001", equipment_id="eq_001")

        result = await executor.execute_step(step, context)
        assert result.status == StepStatus.COMPLETED
        assert result.data["result"] == "done"

    @pytest.mark.asyncio
    async def test_execute_step_returns_step_result(self):
        """处理器直接返回 StepResult"""
        executor = ProcessExecutor()

        async def handler(step, context):
            return StepResult.success(step.step_id, {"custom": True})

        executor.register_handler(StepType.HEAT, handler)

        step = ProcessStep(
            step_id="step_01",
            name="Heat",
            step_type=StepType.HEAT,
        )
        context = ProcessContext(process_id="proc_001", equipment_id="eq_001")

        result = await executor.execute_step(step, context)
        assert result.status == StepStatus.COMPLETED
        assert result.data["custom"] is True

    @pytest.mark.asyncio
    async def test_execute_step_with_timeout(self):
        """测试超时功能"""
        executor = ProcessExecutor()

        async def slow_handler(step, context):
            await asyncio.sleep(1.0)
            return {"done": True}

        executor.register_handler(StepType.HEAT, slow_handler)

        step = ProcessStep(
            step_id="step_01",
            name="Slow Heat",
            step_type=StepType.HEAT,
            timeout=0.05,  # 50ms 超时
        )
        context = ProcessContext(process_id="proc_001", equipment_id="eq_001")

        result = await executor.execute_step(step, context)
        assert result.status == StepStatus.FAILED
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_step_with_retry(self):
        """测试重试机制"""
        executor = ProcessExecutor()
        call_count = {"count": 0}

        async def flaky_handler(step, context):
            call_count["count"] += 1
            if call_count["count"] < 3:
                raise ValueError(f"Attempt {call_count['count']} failed")
            return {"success": True}

        executor.register_handler(StepType.HEAT, flaky_handler)

        step = ProcessStep(
            step_id="step_01",
            name="Flaky Heat",
            step_type=StepType.HEAT,
            retry_count=3,
            retry_delay=0.01,
        )
        context = ProcessContext(process_id="proc_001", equipment_id="eq_001")

        result = await executor.execute_step(step, context)
        assert result.status == StepStatus.COMPLETED
        assert result.data["success"] is True
        assert result.retry_attempts == 2  # 第3次成功，2次重试

    @pytest.mark.asyncio
    async def test_execute_step_retry_exhausted(self):
        """测试重试次数耗尽"""
        executor = ProcessExecutor()

        async def always_fail(step, context):
            raise RuntimeError("Always fails")

        executor.register_handler(StepType.HEAT, always_fail)

        step = ProcessStep(
            step_id="step_01",
            name="Failing Step",
            step_type=StepType.HEAT,
            retry_count=2,
            retry_delay=0.01,
        )
        context = ProcessContext(process_id="proc_001", equipment_id="eq_001")

        result = await executor.execute_step(step, context)
        assert result.status == StepStatus.FAILED
        assert result.retry_attempts == 2
        assert "Always fails" in result.error

    @pytest.mark.asyncio
    async def test_execute_step_handler_with_context(self):
        """处理器可以访问和修改上下文"""
        executor = ProcessExecutor()

        async def handler(step, context):
            context.set_var("processed", True)
            prev = context.get_var("counter", 0)
            context.set_var("counter", prev + 1)
            return {"step_completed": True}

        executor.register_handler(StepType.HEAT, handler)

        step = ProcessStep(step_id="step_01", name="Heat", step_type=StepType.HEAT)
        context = ProcessContext(process_id="proc_001", equipment_id="eq_001")

        await executor.execute_step(step, context)
        assert context.get_var("processed") is True
        assert context.get_var("counter") == 1

    def test_set_default_timeout(self):
        executor = ProcessExecutor()
        executor.set_default_timeout(60.0)
        assert executor._default_timeout == 60.0

    def test_set_default_timeout_invalid(self):
        executor = ProcessExecutor()
        with pytest.raises(ValueError):
            executor.set_default_timeout(-1)

    def test_repr(self):
        executor = ProcessExecutor()

        async def handler(step, context):
            return {}

        executor.register_handler(StepType.HEAT, handler)
        r = repr(executor)
        assert "heat" in r
