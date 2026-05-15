"""流程引擎测试"""

import asyncio
import pytest

from myeap.process.engine import ProcessEngine, ProcessError
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


# ---- 辅助函数 ----

def make_linear_definition(process_id="proc_001", step_count=3):
    """创建线性流程定义"""
    steps = []
    transitions = {}
    for i in range(step_count):
        sid = f"s{i + 1}"
        steps.append(ProcessStep(
            step_id=sid,
            name=f"Step {i + 1}",
            step_type=StepType.PROCESS,
            parameters={"index": i},
        ))
        if i < step_count - 1:
            transitions[sid] = f"s{i + 2}"

    return ProcessDefinition(
        process_id=process_id,
        name="Linear Process",
        equipment_type="CVD",
        steps=steps,
        transitions=transitions,
    )


def make_context(process_id="proc_001", equipment_id="eq_001"):
    return ProcessContext(
        process_id=process_id,
        equipment_id=equipment_id,
    )


async def noop_handler(step, context):
    return {"ok": True}


class TestProcessEngineBasic:
    """流程引擎基础测试"""

    @pytest.mark.asyncio
    async def test_creation(self):
        engine = ProcessEngine()
        assert engine.active_count == 0
        assert engine.active_processes == []

    @pytest.mark.asyncio
    async def test_creation_with_executor(self):
        executor = ProcessExecutor()
        engine = ProcessEngine(executor)
        assert engine.executor is executor

    @pytest.mark.asyncio
    async def test_execute_linear_process(self):
        """测试顺序执行线性流程"""
        executor = ProcessExecutor()
        executor.register_handler(StepType.PROCESS, noop_handler)

        engine = ProcessEngine(executor)
        definition = make_linear_definition()
        context = make_context()

        result = await engine.execute(definition, context)

        assert result.state == ProcessState.COMPLETED
        assert result.started_at is not None
        assert result.completed_at is not None
        assert len(result.step_results) == 3
        assert result.get_step_result("s1").status == StepStatus.COMPLETED
        assert result.get_step_result("s2").status == StepStatus.COMPLETED
        assert result.get_step_result("s3").status == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_empty_steps(self):
        """测试空步骤流程（立即完成）"""
        executor = ProcessExecutor()
        engine = ProcessEngine(executor)

        definition = ProcessDefinition(
            process_id="empty_proc",
            name="Empty",
            equipment_type="CVD",
            steps=[],
        )
        context = make_context("empty_proc")

        result = await engine.execute(definition, context)
        assert result.state == ProcessState.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_with_start_step_id(self):
        """测试指定起始步骤"""
        executor = ProcessExecutor()
        executor.register_handler(StepType.PROCESS, noop_handler)

        engine = ProcessEngine(executor)

        steps = [
            ProcessStep(step_id="s1", name="S1", step_type=StepType.PROCESS),
            ProcessStep(step_id="s2", name="S2", step_type=StepType.PROCESS),
            ProcessStep(step_id="s3", name="S3", step_type=StepType.PROCESS),
        ]
        definition = ProcessDefinition(
            process_id="proc_001",
            name="Skip First",
            equipment_type="CVD",
            steps=steps,
            transitions={"s2": "s3"},
            start_step_id="s2",
        )
        context = make_context()

        result = await engine.execute(definition, context)
        assert result.state == ProcessState.COMPLETED
        assert "s1" not in result.step_results
        assert result.get_step_result("s2").status == StepStatus.COMPLETED
        assert result.get_step_result("s3").status == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_already_active(self):
        """测试重复执行同一流程会报错"""
        executor = ProcessExecutor()
        executor.register_handler(StepType.PROCESS, noop_handler)

        engine = ProcessEngine(executor)
        definition = make_linear_definition()
        context = make_context()

        # 模拟已在活跃列表
        engine._active_contexts["proc_001"] = context

        with pytest.raises(ProcessError, match="already active"):
            await engine.execute(definition, context)

    @pytest.mark.asyncio
    async def test_execute_invalid_definition(self):
        """测试无效流程定义"""
        engine = ProcessEngine()

        definition = ProcessDefinition(
            process_id="invalid_proc",
            name="Invalid",
            equipment_type="CVD",
            steps=[
                ProcessStep(step_id="s1", name="S1", step_type=StepType.PARALLEL),
            ],
        )
        context = make_context("invalid_proc")

        with pytest.raises(ProcessError, match="Invalid process definition"):
            await engine.execute(definition, context)


class TestProcessEngineCallbacks:
    """流程引擎回调测试"""

    @pytest.mark.asyncio
    async def test_on_step_start_callback(self):
        executor = ProcessExecutor()
        executor.register_handler(StepType.PROCESS, noop_handler)

        engine = ProcessEngine(executor)
        started_steps = []

        def on_start(step, context):
            started_steps.append(step.step_id)

        engine.on_step_start = on_start

        definition = make_linear_definition()
        context = make_context()

        await engine.execute(definition, context)
        assert started_steps == ["s1", "s2", "s3"]

    @pytest.mark.asyncio
    async def test_on_step_complete_callback(self):
        executor = ProcessExecutor()
        executor.register_handler(StepType.PROCESS, noop_handler)

        engine = ProcessEngine(executor)
        completed_steps = []

        def on_complete(result, context):
            completed_steps.append(result.step_id)

        engine.on_step_complete = on_complete

        definition = make_linear_definition()
        context = make_context()

        await engine.execute(definition, context)
        assert completed_steps == ["s1", "s2", "s3"]

    @pytest.mark.asyncio
    async def test_on_complete_callback(self):
        executor = ProcessExecutor()
        executor.register_handler(StepType.PROCESS, noop_handler)

        engine = ProcessEngine(executor)
        completed_contexts = []

        def on_complete(context):
            completed_contexts.append(context)

        engine.on_complete = on_complete

        definition = make_linear_definition()
        context = make_context()

        await engine.execute(definition, context)
        assert len(completed_contexts) == 1
        assert completed_contexts[0].process_id == "proc_001"

    @pytest.mark.asyncio
    async def test_on_error_callback(self):
        executor = ProcessExecutor()

        async def fail_handler(step, context):
            raise RuntimeError("Test error")

        executor.register_handler(StepType.PROCESS, fail_handler)

        engine = ProcessEngine(executor)
        errors = []

        def on_error(error_code, step, context):
            errors.append((error_code, step.step_id))

        engine.on_error = on_error

        definition = make_linear_definition()
        context = make_context()

        await engine.execute(definition, context)
        assert len(errors) == 1
        assert errors[0][1] == "s1"

    @pytest.mark.asyncio
    async def test_on_progress_callback(self):
        executor = ProcessExecutor()
        executor.register_handler(StepType.PROCESS, noop_handler)

        engine = ProcessEngine(executor)
        progress_entries = []

        def on_progress(step, idx, total, context):
            progress_entries.append((idx, total))

        engine.on_progress = on_progress

        definition = make_linear_definition()
        context = make_context()

        await engine.execute(definition, context)
        assert progress_entries == [(0, 3), (1, 3), (2, 3)]

    @pytest.mark.asyncio
    async def test_async_callback(self):
        executor = ProcessExecutor()
        executor.register_handler(StepType.PROCESS, noop_handler)

        engine = ProcessEngine(executor)
        async_steps = []

        async def async_on_complete(context):
            await asyncio.sleep(0.01)
            async_steps.append(context.process_id)

        engine.on_complete = async_on_complete

        definition = make_linear_definition()
        context = make_context()

        await engine.execute(definition, context)
        assert len(async_steps) == 1


class TestProcessEngineConditional:
    """条件步骤测试"""

    @pytest.mark.asyncio
    async def test_conditional_with_pre_condition(self):
        executor = ProcessExecutor()
        executor.register_handler(StepType.HEAT, noop_handler)

        engine = ProcessEngine(executor)

        steps = [
            ProcessStep(
                step_id="cond",
                name="Check",
                step_type=StepType.CONDITIONAL,
                pre_condition="temp_ok",
                branch_targets={"temp_ok": "heat_step"},
            ),
            ProcessStep(step_id="heat_step", name="Heat", step_type=StepType.HEAT),
        ]
        definition = ProcessDefinition(
            process_id="proc_001",
            name="Conditional",
            equipment_type="CVD",
            steps=steps,
            transitions={"cond": "heat_step"},
        )
        context = make_context()
        context.set_var("temp_ok", "heat_step")

        result = await engine.execute(definition, context)
        assert result.state == ProcessState.COMPLETED
        cond_result = result.get_step_result("cond")
        assert cond_result.status == StepStatus.COMPLETED
        assert cond_result.data["branch"] == "heat_step"

    @pytest.mark.asyncio
    async def test_conditional_with_default(self):
        executor = ProcessExecutor()
        executor.register_handler(StepType.HEAT, noop_handler)

        engine = ProcessEngine(executor)

        steps = [
            ProcessStep(
                step_id="cond",
                name="Check",
                step_type=StepType.CONDITIONAL,
                branch_targets={"default": "heat_step", "other": "other_step"},
            ),
            ProcessStep(step_id="heat_step", name="Heat", step_type=StepType.HEAT),
        ]
        definition = ProcessDefinition(
            process_id="proc_001",
            name="Conditional",
            equipment_type="CVD",
            steps=steps,
            transitions={"cond": "heat_step"},
        )
        context = make_context()

        result = await engine.execute(definition, context)
        assert result.state == ProcessState.COMPLETED
        cond_result = result.get_step_result("cond")
        assert cond_result.data["branch"] == "heat_step"

    @pytest.mark.asyncio
    async def test_conditional_no_match(self):
        executor = ProcessExecutor()
        engine = ProcessEngine(executor)

        steps = [
            ProcessStep(
                step_id="cond",
                name="Check",
                step_type=StepType.CONDITIONAL,
                pre_condition="unknown_condition",
                branch_targets={"known": "next"},
            ),
        ]
        definition = ProcessDefinition(
            process_id="proc_001",
            name="Conditional",
            equipment_type="CVD",
            steps=steps,
        )
        context = make_context()

        result = await engine.execute(definition, context)
        assert result.state == ProcessState.FAILED
        cond_result = result.get_step_result("cond")
        assert cond_result.status == StepStatus.FAILED


class TestProcessEngineParallel:
    """并行步骤测试"""

    @pytest.mark.asyncio
    async def test_parallel_execution(self):
        executor = ProcessExecutor()

        async def handler(step, context):
            await asyncio.sleep(0.02)
            return {"step": step.step_id}

        executor.register_handler(StepType.HEAT, handler)
        executor.register_handler(StepType.PURGE, handler)
        executor.register_handler(StepType.PROCESS, handler)

        engine = ProcessEngine(executor)

        parallel_step = ProcessStep(
            step_id="parallel_1",
            name="Parallel",
            step_type=StepType.PARALLEL,
            parallel_steps=[
                ProcessStep(step_id="sub_1", name="Heat A", step_type=StepType.HEAT),
                ProcessStep(step_id="sub_2", name="Purge B", step_type=StepType.PURGE),
            ],
        )
        definition = ProcessDefinition(
            process_id="proc_001",
            name="Parallel",
            equipment_type="CVD",
            steps=[parallel_step],
        )
        context = make_context()

        result = await engine.execute(definition, context)
        assert result.state == ProcessState.COMPLETED

        pr = result.get_step_result("parallel_1")
        assert pr.status == StepStatus.COMPLETED
        assert pr.data["sub_step_count"] == 2

        # 所有子步骤结果都记录
        sub1 = result.get_step_result("sub_1")
        sub2 = result.get_step_result("sub_2")
        assert sub1.status == StepStatus.COMPLETED
        assert sub2.status == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_parallel_with_failure(self):
        executor = ProcessExecutor()

        async def success_handler(step, context):
            return {"ok": True}

        async def fail_handler(step, context):
            raise RuntimeError("Sub-step failed")

        executor.register_handler(StepType.HEAT, success_handler)
        executor.register_handler(StepType.PURGE, fail_handler)

        engine = ProcessEngine(executor)

        parallel_step = ProcessStep(
            step_id="parallel_1",
            name="Parallel",
            step_type=StepType.PARALLEL,
            parallel_steps=[
                ProcessStep(step_id="sub_1", name="OK", step_type=StepType.HEAT),
                ProcessStep(step_id="sub_2", name="Fail", step_type=StepType.PURGE),
            ],
        )
        definition = ProcessDefinition(
            process_id="proc_001",
            name="Parallel Fail",
            equipment_type="CVD",
            steps=[parallel_step],
        )
        context = make_context()

        result = await engine.execute(definition, context)
        assert result.state == ProcessState.FAILED
        pr = result.get_step_result("parallel_1")
        assert pr.status == StepStatus.FAILED


class TestProcessEngineLoop:
    """循环步骤测试"""

    @pytest.mark.asyncio
    async def test_loop_fixed_iterations(self):
        executor = ProcessExecutor()

        async def counter_handler(step, context):
            cnt = context.get_var("loop_count", 0)
            context.set_var("loop_count", cnt + 1)
            return {"count": cnt + 1}

        executor.register_handler(StepType.PROCESS, counter_handler)

        engine = ProcessEngine(executor)

        loop_step = ProcessStep(
            step_id="loop_1",
            name="Repeat",
            step_type=StepType.LOOP,
            loop_steps=[
                ProcessStep(step_id="loop_sub", name="Increment", step_type=StepType.PROCESS),
            ],
            loop_condition="loop_count < 5",
            max_iterations=10,
        )
        definition = ProcessDefinition(
            process_id="proc_001",
            name="Loop",
            equipment_type="CVD",
            steps=[loop_step],
        )
        context = make_context()
        context.set_var("loop_count", 0)

        result = await engine.execute(definition, context)
        assert result.state == ProcessState.COMPLETED
        assert context.get_var("loop_count") == 5

        lr = result.get_step_result("loop_1")
        assert lr.status == StepStatus.COMPLETED
        assert lr.data["iterations"] == 5

    @pytest.mark.asyncio
    async def test_loop_with_condition(self):
        executor = ProcessExecutor()

        async def handler(step, context):
            val = context.get_var("value", 0)
            context.set_var("value", val + 2)
            return {}

        executor.register_handler(StepType.PROCESS, handler)

        engine = ProcessEngine(executor)

        loop_step = ProcessStep(
            step_id="loop_1",
            name="Loop",
            step_type=StepType.LOOP,
            loop_steps=[
                ProcessStep(step_id="sub", name="Add", step_type=StepType.PROCESS),
            ],
            loop_condition="value < 10",
            max_iterations=100,
        )
        definition = ProcessDefinition(
            process_id="proc_001",
            name="Loop2",
            equipment_type="CVD",
            steps=[loop_step],
        )
        context = make_context()
        context.set_var("value", 0)

        result = await engine.execute(definition, context)
        assert result.state == ProcessState.COMPLETED
        assert context.get_var("value") == 10

    @pytest.mark.asyncio
    async def test_loop_max_iterations(self):
        """循环在达到最大迭代次数时停止"""
        executor = ProcessExecutor()

        async def handler(step, context):
            return {}

        executor.register_handler(StepType.PROCESS, handler)

        engine = ProcessEngine(executor)

        loop_step = ProcessStep(
            step_id="loop_1",
            name="Infinite",
            step_type=StepType.LOOP,
            loop_steps=[
                ProcessStep(step_id="sub", name="Noop", step_type=StepType.PROCESS),
            ],
            max_iterations=3,
        )
        definition = ProcessDefinition(
            process_id="proc_001",
            name="Limited Loop",
            equipment_type="CVD",
            steps=[loop_step],
        )
        context = make_context()

        result = await engine.execute(definition, context)
        assert result.state == ProcessState.COMPLETED
        lr = result.get_step_result("loop_1")
        assert lr.data["iterations"] == 3

    @pytest.mark.asyncio
    async def test_loop_empty(self):
        """空循环体应在验证时被拒绝"""
        engine = ProcessEngine()

        loop_step = ProcessStep(
            step_id="loop_1",
            name="Empty Loop",
            step_type=StepType.LOOP,
            loop_steps=[],
            max_iterations=10,
        )
        definition = ProcessDefinition(
            process_id="proc_001",
            name="Empty",
            equipment_type="CVD",
            steps=[loop_step],
        )
        context = make_context()

        with pytest.raises(ProcessError, match="Invalid process definition"):
            await engine.execute(definition, context)


class TestProcessEngineErrorHandling:
    """错误处理测试"""

    @pytest.mark.asyncio
    async def test_error_handler_executed(self):
        executor = ProcessExecutor()

        async def fail_handler(step, context):
            raise RuntimeError("Main step failed")

        async def recovery_handler(step, context):
            context.set_var("recovered", True)
            return {"recovered": True}

        executor.register_handler(StepType.PROCESS, fail_handler)
        executor.register_handler(StepType.VENT, recovery_handler)

        engine = ProcessEngine(executor)

        definition = ProcessDefinition(
            process_id="proc_001",
            name="Error Handling",
            equipment_type="CVD",
            steps=[
                ProcessStep(step_id="s1", name="Main", step_type=StepType.PROCESS),
                ProcessStep(step_id="recovery", name="Recovery", step_type=StepType.VENT),
            ],
            transitions={"s1": "recovery"},
            error_handlers={"Test error": "recovery", "*": "recovery"},
        )
        context = make_context()

        result = await engine.execute(definition, context)
        assert context.get_var("recovered") is True

    @pytest.mark.asyncio
    async def test_no_error_handler(self):
        executor = ProcessExecutor()

        async def fail_handler(step, context):
            raise RuntimeError("Fatal error")

        executor.register_handler(StepType.PROCESS, fail_handler)

        engine = ProcessEngine(executor)

        definition = ProcessDefinition(
            process_id="proc_001",
            name="No Error Handler",
            equipment_type="CVD",
            steps=[
                ProcessStep(step_id="s1", name="Fatal", step_type=StepType.PROCESS),
            ],
        )
        context = make_context()

        result = await engine.execute(definition, context)
        assert result.state == ProcessState.FAILED
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_wildcard_error_handler(self):
        executor = ProcessExecutor()

        async def fail_handler(step, context):
            raise RuntimeError("Any error")

        async def recovery_handler(step, context):
            context.set_var("wildcard_recovered", True)
            return {"ok": True}

        executor.register_handler(StepType.PROCESS, fail_handler)
        executor.register_handler(StepType.VENT, recovery_handler)

        engine = ProcessEngine(executor)

        definition = ProcessDefinition(
            process_id="proc_001",
            name="Wildcard",
            equipment_type="CVD",
            steps=[
                ProcessStep(step_id="s1", name="Main", step_type=StepType.PROCESS),
                ProcessStep(step_id="recovery", name="Recovery", step_type=StepType.VENT),
            ],
            transitions={"s1": "recovery"},
            error_handlers={"*": "recovery"},
        )
        context = make_context()

        result = await engine.execute(definition, context)
        assert context.get_var("wildcard_recovered") is True


class TestProcessEngineControl:
    """流程控制测试（暂停/恢复/中止）"""

    @pytest.mark.asyncio
    async def test_pause(self):
        """测试暂停"""
        engine = ProcessEngine()
        context = make_context()
        context.state = ProcessState.RUNNING
        engine._active_contexts["proc_001"] = context
        engine._pause_events["proc_001"] = asyncio.Event()
        engine._pause_events["proc_001"].set()

        assert await engine.pause("proc_001")
        assert context.state == ProcessState.PAUSED
        assert context.paused_at is not None

    @pytest.mark.asyncio
    async def test_pause_nonexistent(self):
        engine = ProcessEngine()
        assert not await engine.pause("nonexistent")

    @pytest.mark.asyncio
    async def test_pause_already_paused(self):
        engine = ProcessEngine()
        context = make_context()
        context.state = ProcessState.PAUSED
        engine._active_contexts["proc_001"] = context

        assert not await engine.pause("proc_001")

    @pytest.mark.asyncio
    async def test_resume(self):
        """测试恢复"""
        engine = ProcessEngine()
        context = make_context()
        context.state = ProcessState.PAUSED
        context.paused_at = None  # 初始
        engine._active_contexts["proc_001"] = context
        engine._pause_events["proc_001"] = asyncio.Event()
        engine._pause_events["proc_001"].clear()

        assert await engine.resume("proc_001")
        assert context.state == ProcessState.RUNNING

    @pytest.mark.asyncio
    async def test_resume_not_paused(self):
        engine = ProcessEngine()
        context = make_context()
        context.state = ProcessState.RUNNING
        engine._active_contexts["proc_001"] = context

        assert not await engine.resume("proc_001")

    @pytest.mark.asyncio
    async def test_abort(self):
        """测试中止"""
        engine = ProcessEngine()
        context = make_context()
        context.state = ProcessState.RUNNING
        engine._active_contexts["proc_001"] = context
        engine._pause_events["proc_001"] = asyncio.Event()
        engine._pause_events["proc_001"].set()

        assert await engine.abort("proc_001")
        assert context.state == ProcessState.ABORTED
        assert "proc_001" in engine._abort_flags

    @pytest.mark.asyncio
    async def test_abort_terminal(self):
        """终态流程不能中止"""
        engine = ProcessEngine()
        context = make_context()
        context.state = ProcessState.COMPLETED
        engine._active_contexts["proc_001"] = context

        assert not await engine.abort("proc_001")

    @pytest.mark.asyncio
    async def test_pause_resume_abort_callbacks(self):
        engine = ProcessEngine()
        pause_called = []
        abort_called = []

        engine.on_pause = lambda ctx: pause_called.append(ctx.process_id)
        engine.on_abort = lambda ctx: abort_called.append(ctx.process_id)

        context = make_context()
        context.state = ProcessState.RUNNING
        engine._active_contexts["proc_001"] = context
        engine._pause_events["proc_001"] = asyncio.Event()
        engine._pause_events["proc_001"].set()

        await engine.pause("proc_001")
        assert len(pause_called) == 1

        await engine.abort("proc_001")
        assert len(abort_called) == 1


class TestProcessEngineWait:
    """等待步骤测试"""

    @pytest.mark.asyncio
    async def test_wait_step(self):
        executor = ProcessExecutor()

        async def noop(step, context):
            return {}

        executor.register_handler(StepType.PROCESS, noop)

        engine = ProcessEngine(executor)

        wait_step = ProcessStep(
            step_id="wait_1",
            name="Wait",
            step_type=StepType.WAIT,
            duration=0.05,
        )
        definition = ProcessDefinition(
            process_id="proc_001",
            name="Wait Test",
            equipment_type="CVD",
            steps=[wait_step],
        )
        context = make_context()

        result = await engine.execute(definition, context)
        assert result.state == ProcessState.COMPLETED
        wr = result.get_step_result("wait_1")
        assert wr.status == StepStatus.COMPLETED
        assert wr.data["waited"] == 0.05

    @pytest.mark.asyncio
    async def test_wait_step_from_parameters(self):
        executor = ProcessExecutor()
        engine = ProcessEngine(executor)

        wait_step = ProcessStep(
            step_id="wait_1",
            name="Wait",
            step_type=StepType.WAIT,
            parameters={"duration": 0.03},
        )
        definition = ProcessDefinition(
            process_id="proc_001",
            name="Wait Test",
            equipment_type="CVD",
            steps=[wait_step],
        )
        context = make_context()

        result = await engine.execute(definition, context)
        assert result.state == ProcessState.COMPLETED
        wr = result.get_step_result("wait_1")
        assert wr.status == StepStatus.COMPLETED
        assert wr.data["waited"] == 0.03


class TestProcessEngineExpression:
    """表达式求值测试"""

    def test_evaluate_simple_truthy(self):
        engine = ProcessEngine()
        context = make_context()
        context.set_var("flag", True)
        assert engine._evaluate_expression("flag", context)

    def test_evaluate_simple_falsy(self):
        engine = ProcessEngine()
        context = make_context()
        context.set_var("flag", False)
        assert not engine._evaluate_expression("flag", context)

    def test_evaluate_nonexistent(self):
        engine = ProcessEngine()
        context = make_context()
        assert not engine._evaluate_expression("nonexistent", context)

    def test_evaluate_equality(self):
        engine = ProcessEngine()
        context = make_context()
        context.set_var("status", "ok")
        assert engine._evaluate_expression("status == ok", context)
        assert not engine._evaluate_expression("status == fail", context)

    def test_evaluate_not_equal(self):
        engine = ProcessEngine()
        context = make_context()
        context.set_var("status", "ok")
        assert engine._evaluate_expression("status != fail", context)

    def test_evaluate_greater_than(self):
        engine = ProcessEngine()
        context = make_context()
        context.set_var("count", 10)
        assert engine._evaluate_expression("count > 5", context)
        assert not engine._evaluate_expression("count > 15", context)

    def test_evaluate_greater_equal(self):
        engine = ProcessEngine()
        context = make_context()
        context.set_var("count", 5)
        assert engine._evaluate_expression("count >= 5", context)
        assert engine._evaluate_expression("count >= 4", context)

    def test_evaluate_less_than(self):
        engine = ProcessEngine()
        context = make_context()
        context.set_var("count", 3)
        assert engine._evaluate_expression("count < 5", context)
        assert not engine._evaluate_expression("count < 2", context)

    def test_evaluate_less_equal(self):
        engine = ProcessEngine()
        context = make_context()
        context.set_var("count", 5)
        assert engine._evaluate_expression("count <= 5", context)
        assert engine._evaluate_expression("count <= 10", context)
        assert not engine._evaluate_expression("count <= 4", context)

    def test_evaluate_none_value(self):
        engine = ProcessEngine()
        context = make_context()
        assert not engine._evaluate_expression("missing > 5", context)


class TestProcessEngineRepr:
    """repr 测试"""

    def test_repr(self):
        engine = ProcessEngine()
        r = repr(engine)
        assert "active=0" in r
