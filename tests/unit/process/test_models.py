"""流程模型测试"""

import pytest
from datetime import datetime, timedelta

from myeap.process.models import (
    ProcessContext,
    ProcessDefinition,
    ProcessState,
    ProcessStep,
    StepResult,
    StepStatus,
    StepType,
)


class TestProcessState:
    """流程状态测试"""

    def test_state_values(self):
        assert ProcessState.CREATED.value == "created"
        assert ProcessState.READY.value == "ready"
        assert ProcessState.RUNNING.value == "running"
        assert ProcessState.PAUSED.value == "paused"
        assert ProcessState.COMPLETED.value == "completed"
        assert ProcessState.ABORTED.value == "aborted"
        assert ProcessState.FAILED.value == "failed"

    def test_state_count(self):
        assert len(ProcessState) == 7


class TestStepType:
    """步骤类型测试"""

    def test_step_type_values(self):
        assert StepType.PUMP_DOWN.value == "pump_down"
        assert StepType.PURGE.value == "purge"
        assert StepType.HEAT.value == "heat"
        assert StepType.STABILIZE.value == "stabilize"
        assert StepType.PROCESS.value == "process"
        assert StepType.VENT.value == "vent"
        assert StepType.CLEAN.value == "clean"
        assert StepType.COOL_DOWN.value == "cool_down"
        assert StepType.WAIT.value == "wait"
        assert StepType.CONDITIONAL.value == "conditional"
        assert StepType.PARALLEL.value == "parallel"
        assert StepType.LOOP.value == "loop"

    def test_special_step_types_exist(self):
        """验证特殊步骤类型存在"""
        special = {StepType.CONDITIONAL, StepType.PARALLEL, StepType.LOOP}
        assert len(special) == 3


class TestStepStatus:
    """步骤状态测试"""

    def test_status_values(self):
        assert StepStatus.PENDING.value == "pending"
        assert StepStatus.RUNNING.value == "running"
        assert StepStatus.COMPLETED.value == "completed"
        assert StepStatus.SKIPPED.value == "skipped"
        assert StepStatus.FAILED.value == "failed"
        assert StepStatus.TIMEOUT.value == "timeout"


class TestProcessStep:
    """工艺步骤测试"""

    def test_creation_basic(self):
        step = ProcessStep(
            step_id="step_01",
            name="Preheat",
            step_type=StepType.HEAT,
        )
        assert step.step_id == "step_01"
        assert step.name == "Preheat"
        assert step.step_type == StepType.HEAT
        assert step.parameters == {}
        assert step.duration is None
        assert step.timeout is None
        assert step.retry_count == 0
        assert step.retry_delay == 0.0

    def test_creation_full(self):
        step = ProcessStep(
            step_id="step_02",
            name="Pump Down",
            step_type=StepType.PUMP_DOWN,
            parameters={"target_pressure": 0.01},
            duration=30.0,
            timeout=60.0,
            retry_count=3,
            retry_delay=5.0,
        )
        assert step.parameters["target_pressure"] == 0.01
        assert step.duration == 30.0
        assert step.timeout == 60.0
        assert step.retry_count == 3
        assert step.retry_delay == 5.0

    def test_conditional_step(self):
        step = ProcessStep(
            step_id="cond_01",
            name="Check Temperature",
            step_type=StepType.CONDITIONAL,
            pre_condition="temperature",
            branch_targets={"stable": "step_process", "unstable": "step_heat"},
        )
        assert step.pre_condition == "temperature"
        assert step.branch_targets["stable"] == "step_process"
        assert step.branch_targets["unstable"] == "step_heat"

    def test_parallel_step(self):
        sub_steps = [
            ProcessStep(step_id="sub_01", name="Sub 1", step_type=StepType.HEAT),
            ProcessStep(step_id="sub_02", name="Sub 2", step_type=StepType.PURGE),
        ]
        step = ProcessStep(
            step_id="parallel_01",
            name="Parallel Operations",
            step_type=StepType.PARALLEL,
            parallel_steps=sub_steps,
        )
        assert len(step.parallel_steps) == 2
        assert step.parallel_steps[0].step_id == "sub_01"

    def test_loop_step(self):
        loop_body = [
            ProcessStep(step_id="loop_sub_01", name="Check", step_type=StepType.WAIT),
        ]
        step = ProcessStep(
            step_id="loop_01",
            name="Repeat Check",
            step_type=StepType.LOOP,
            loop_steps=loop_body,
            loop_condition="counter < 5",
            max_iterations=10,
        )
        assert len(step.loop_steps) == 1
        assert step.loop_condition == "counter < 5"
        assert step.max_iterations == 10


class TestStepResult:
    """步骤结果测试"""

    def test_success_result(self):
        result = StepResult.success(
            step_id="step_01",
            data={"temperature": 150.0},
        )
        assert result.step_id == "step_01"
        assert result.status == StepStatus.COMPLETED
        assert result.is_success
        assert not result.is_failure
        assert result.data["temperature"] == 150.0
        assert result.error is None
        assert result.completed_at is not None

    def test_failure_result(self):
        start = datetime.utcnow()
        result = StepResult.failure(
            step_id="step_01",
            error="Temperature exceeded limit",
            retry_attempts=2,
            started_at=start,
        )
        assert result.status == StepStatus.FAILED
        assert result.is_failure
        assert not result.is_success
        assert result.error == "Temperature exceeded limit"
        assert result.retry_attempts == 2
        assert result.duration >= 0

    def test_timeout_result(self):
        start = datetime.utcnow()
        result = StepResult.timeout(
            step_id="step_01",
            error="Step timed out",
            started_at=start,
        )
        assert result.status == StepStatus.TIMEOUT
        assert result.is_failure
        assert "timed out" in result.error

    def test_default_values(self):
        result = StepResult(step_id="step_01")
        assert result.status == StepStatus.PENDING
        assert result.data == {}
        assert result.error is None
        assert result.duration == 0.0
        assert result.retry_attempts == 0


class TestProcessDefinition:
    """流程定义测试"""

    def test_creation_basic(self):
        steps = [
            ProcessStep(step_id="s1", name="Step 1", step_type=StepType.HEAT),
            ProcessStep(step_id="s2", name="Step 2", step_type=StepType.PROCESS),
            ProcessStep(step_id="s3", name="Step 3", step_type=StepType.VENT),
        ]
        definition = ProcessDefinition(
            process_id="proc_def_001",
            name="Test Process",
            equipment_type="CVD",
            steps=steps,
            transitions={"s1": "s2", "s2": "s3"},
        )
        assert definition.process_id == "proc_def_001"
        assert definition.name == "Test Process"
        assert definition.equipment_type == "CVD"
        assert len(definition.steps) == 3
        assert definition.transitions["s1"] == "s2"

    def test_get_step(self):
        step = ProcessStep(step_id="s1", name="Step 1", step_type=StepType.HEAT)
        definition = ProcessDefinition(
            process_id="proc_001",
            name="Test",
            equipment_type="CVD",
            steps=[step],
        )
        assert definition.get_step("s1") is step
        assert definition.get_step("nonexistent") is None

    def test_get_next_step_id(self):
        definition = ProcessDefinition(
            process_id="proc_001",
            name="Test",
            equipment_type="CVD",
            steps=[
                ProcessStep(step_id="s1", name="S1", step_type=StepType.HEAT),
                ProcessStep(step_id="s2", name="S2", step_type=StepType.PROCESS),
            ],
            transitions={"s1": "s2"},
        )
        assert definition.get_next_step_id("s1") == "s2"
        assert definition.get_next_step_id("s2") is None
        assert definition.get_next_step_id("nonexistent") is None

    def test_get_error_handler(self):
        definition = ProcessDefinition(
            process_id="proc_001",
            name="Test",
            equipment_type="CVD",
            steps=[
                ProcessStep(step_id="s1", name="S1", step_type=StepType.HEAT),
                ProcessStep(step_id="error_handler", name="Error", step_type=StepType.VENT),
            ],
            error_handlers={"TEMP_ERROR": "error_handler"},
        )
        assert definition.get_error_handler("TEMP_ERROR") == "error_handler"
        assert definition.get_error_handler("UNKNOWN") is None

    def test_validate_empty_steps(self):
        definition = ProcessDefinition(
            process_id="proc_001",
            name="Test",
            equipment_type="CVD",
            steps=[],
        )
        errors = definition.validate()
        assert len(errors) > 0
        assert "at least one step" in errors[0]

    def test_validate_duplicate_step_ids(self):
        definition = ProcessDefinition(
            process_id="proc_001",
            name="Test",
            equipment_type="CVD",
            steps=[
                ProcessStep(step_id="s1", name="S1", step_type=StepType.HEAT),
                ProcessStep(step_id="s1", name="S1 Dup", step_type=StepType.PROCESS),
            ],
        )
        errors = definition.validate()
        assert "Duplicate step IDs" in errors[0]

    def test_validate_invalid_transition(self):
        definition = ProcessDefinition(
            process_id="proc_001",
            name="Test",
            equipment_type="CVD",
            steps=[
                ProcessStep(step_id="s1", name="S1", step_type=StepType.HEAT),
            ],
            transitions={"s1": "s_nonexistent"},
        )
        errors = definition.validate()
        assert len(errors) > 0
        assert any("s_nonexistent" in e for e in errors)

    def test_validate_parallel_no_substeps(self):
        definition = ProcessDefinition(
            process_id="proc_001",
            name="Test",
            equipment_type="CVD",
            steps=[
                ProcessStep(step_id="parallel_1", name="P1", step_type=StepType.PARALLEL),
            ],
        )
        errors = definition.validate()
        assert any("no parallel_steps" in e.lower() for e in errors)

    def test_validate_loop_no_substeps(self):
        definition = ProcessDefinition(
            process_id="proc_001",
            name="Test",
            equipment_type="CVD",
            steps=[
                ProcessStep(step_id="loop_1", name="L1", step_type=StepType.LOOP),
            ],
        )
        errors = definition.validate()
        assert any("no loop_steps" in e.lower() for e in errors)

    def test_validate_loop_invalid_iterations(self):
        sub = ProcessStep(step_id="sub", name="Sub", step_type=StepType.WAIT)
        definition = ProcessDefinition(
            process_id="proc_001",
            name="Test",
            equipment_type="CVD",
            steps=[
                ProcessStep(
                    step_id="loop_1",
                    name="L1",
                    step_type=StepType.LOOP,
                    loop_steps=[sub],
                    max_iterations=0,
                ),
            ],
        )
        errors = definition.validate()
        assert any("max_iterations" in e.lower() for e in errors)

    def test_validate_valid(self):
        definition = ProcessDefinition(
            process_id="proc_001",
            name="Valid Process",
            equipment_type="CVD",
            steps=[
                ProcessStep(step_id="s1", name="S1", step_type=StepType.PUMP_DOWN),
                ProcessStep(step_id="s2", name="S2", step_type=StepType.PROCESS),
                ProcessStep(step_id="s3", name="S3", step_type=StepType.VENT),
            ],
            transitions={"s1": "s2", "s2": "s3"},
            error_handlers={"PUMP_ERROR": "s3"},
        )
        errors = definition.validate()
        assert len(errors) == 0


class TestProcessContext:
    """流程上下文测试"""

    def test_creation(self):
        context = ProcessContext(
            process_id="proc_001",
            equipment_id="eq_001",
        )
        assert context.process_id == "proc_001"
        assert context.equipment_id == "eq_001"
        assert context.state == ProcessState.CREATED
        assert context.variables == {}
        assert context.step_results == {}

    def test_variables(self):
        context = ProcessContext(
            process_id="proc_001",
            equipment_id="eq_001",
        )
        context.set_var("temperature", 150.0)
        assert context.get_var("temperature") == 150.0
        assert context.get_var("nonexistent", 0) == 0
        assert context.get_var("nonexistent") is None

    def test_step_results(self):
        context = ProcessContext(
            process_id="proc_001",
            equipment_id="eq_001",
        )
        result = StepResult.success(step_id="s1")
        context.set_step_result("s1", result)
        assert context.get_step_result("s1") is result
        assert context.get_step_result("s2") is None

    def test_is_active(self):
        context = ProcessContext(
            process_id="proc_001",
            equipment_id="eq_001",
        )
        assert not context.is_active

        context.state = ProcessState.RUNNING
        assert context.is_active

        context.state = ProcessState.PAUSED
        assert context.is_active

        context.state = ProcessState.COMPLETED
        assert not context.is_active

    def test_is_terminal(self):
        context = ProcessContext(
            process_id="proc_001",
            equipment_id="eq_001",
        )
        assert not context.is_terminal

        context.state = ProcessState.COMPLETED
        assert context.is_terminal

        context.state = ProcessState.ABORTED
        assert context.is_terminal

        context.state = ProcessState.FAILED
        assert context.is_terminal

        context.state = ProcessState.RUNNING
        assert not context.is_terminal

    def test_elapsed_time(self):
        context = ProcessContext(
            process_id="proc_001",
            equipment_id="eq_001",
        )
        assert context.elapsed_time == 0.0

        context.started_at = datetime.utcnow() - timedelta(seconds=10)
        assert context.elapsed_time == pytest.approx(10.0, rel=0.1)

        context.completed_at = datetime.utcnow()
        assert context.elapsed_time == pytest.approx(10.0, rel=0.1)

    def test_to_dict(self):
        context = ProcessContext(
            process_id="proc_001",
            equipment_id="eq_001",
            chamber_id="ch_01",
        )
        context.state = ProcessState.RUNNING
        context.started_at = datetime.utcnow()
        context.set_var("counter", 3)
        context.set_step_result("s1", StepResult.success("s1", {"temp": 100}))

        d = context.to_dict()
        assert d["process_id"] == "proc_001"
        assert d["state"] == "running"
        assert d["chamber_id"] == "ch_01"
        assert d["variables"]["counter"] == 3
        assert "s1" in d["step_results"]
        assert d["started_at"] is not None

    def test_repr(self):
        context = ProcessContext(
            process_id="proc_001",
            equipment_id="eq_001",
        )
        r = repr(context)
        assert "proc_001" in r
        assert "created" in r
