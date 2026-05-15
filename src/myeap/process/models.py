"""工艺流程数据模型

定义工艺流程引擎使用的所有数据结构，包括步骤定义、流程定义、
执行结果和执行上下文。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from dataclasses import dataclass, field


class ProcessState(Enum):
    """流程状态"""

    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABORTED = "aborted"
    FAILED = "failed"


class StepType(Enum):
    """步骤类型"""

    PUMP_DOWN = "pump_down"
    PURGE = "purge"
    HEAT = "heat"
    STABILIZE = "stabilize"
    PROCESS = "process"
    VENT = "vent"
    CLEAN = "clean"
    COOL_DOWN = "cool_down"
    WAIT = "wait"
    CONDITIONAL = "conditional"
    PARALLEL = "parallel"
    LOOP = "loop"


class StepStatus(Enum):
    """步骤执行状态"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class ProcessStep:
    """工艺步骤定义

    Attributes:
        step_id: 步骤唯一标识
        name: 步骤名称
        step_type: 步骤类型
        parameters: 步骤参数
        duration: 目标执行时长（秒）
        timeout: 最大允许执行时间（秒），None表示无限制
        retry_count: 失败最大重试次数
        retry_delay: 重试间隔（秒）
        pre_condition: 前置条件表达式（用于条件步骤）
        branch_targets: 分支目标步骤映射（用于条件步骤）
        parallel_steps: 并行步骤列表（用于并行步骤）
        loop_steps: 循环体步骤列表（用于循环步骤）
        loop_condition: 循环条件表达式
        max_iterations: 最大循环次数
    """

    step_id: str
    name: str
    step_type: StepType
    parameters: Dict[str, Any] = field(default_factory=dict)
    duration: Optional[float] = None
    timeout: Optional[float] = None
    retry_count: int = 0
    retry_delay: float = 0.0
    pre_condition: Optional[str] = None
    branch_targets: Dict[str, str] = field(default_factory=dict)
    parallel_steps: List["ProcessStep"] = field(default_factory=list)
    loop_steps: List["ProcessStep"] = field(default_factory=list)
    loop_condition: Optional[str] = None
    max_iterations: int = 100


@dataclass
class StepResult:
    """步骤执行结果

    Attributes:
        step_id: 步骤ID
        status: 执行状态
        data: 结果数据
        error: 错误信息
        started_at: 开始时间
        completed_at: 完成时间
        duration: 实际执行时长（秒）
        retry_attempts: 实际重试次数
    """

    step_id: str
    status: StepStatus = StepStatus.PENDING
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration: float = 0.0
    retry_attempts: int = 0

    @classmethod
    def success(cls, step_id: str, data: Optional[Dict[str, Any]] = None,
                started_at: Optional[datetime] = None,
                completed_at: Optional[datetime] = None) -> "StepResult":
        """创建成功结果"""
        result = cls(step_id=step_id, status=StepStatus.COMPLETED, data=data or {})
        result.started_at = started_at
        result.completed_at = completed_at or datetime.utcnow()
        if started_at:
            result.duration = (result.completed_at - started_at).total_seconds()
        return result

    @classmethod
    def failure(cls, step_id: str, error: str, retry_attempts: int = 0,
                started_at: Optional[datetime] = None) -> "StepResult":
        """创建失败结果"""
        result = cls(
            step_id=step_id,
            status=StepStatus.FAILED,
            error=error,
            retry_attempts=retry_attempts,
            started_at=started_at,
        )
        result.completed_at = datetime.utcnow()
        if started_at:
            result.duration = (result.completed_at - started_at).total_seconds()
        return result

    @classmethod
    def timeout(cls, step_id: str, error: str = "Step timed out",
                started_at: Optional[datetime] = None) -> "StepResult":
        """创建超时结果"""
        result = cls(
            step_id=step_id,
            status=StepStatus.TIMEOUT,
            error=error,
            started_at=started_at,
        )
        result.completed_at = datetime.utcnow()
        if started_at:
            result.duration = (result.completed_at - started_at).total_seconds()
        return result

    @property
    def is_success(self) -> bool:
        return self.status == StepStatus.COMPLETED

    @property
    def is_failure(self) -> bool:
        return self.status in (StepStatus.FAILED, StepStatus.TIMEOUT)


@dataclass
class ProcessDefinition:
    """流程定义

    定义完整的工艺流程，包括步骤序列、转换规则和错误处理。

    Attributes:
        process_id: 流程唯一标识
        name: 流程名称
        equipment_type: 适用的设备类型
        steps: 步骤列表
        transitions: 步骤转换映射 (step_id -> next_step_id)
        error_handlers: 错误处理映射 (error_code -> handler_step_id)
        start_step_id: 起始步骤ID
        max_retries: 全局最大重试次数
        process_timeout: 流程总超时（秒）
        metadata: 流程元数据
    """

    process_id: str
    name: str
    equipment_type: str
    steps: List[ProcessStep] = field(default_factory=list)
    transitions: Dict[str, str] = field(default_factory=dict)
    error_handlers: Dict[str, str] = field(default_factory=dict)
    start_step_id: Optional[str] = None
    max_retries: int = 3
    process_timeout: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_step(self, step_id: str) -> Optional[ProcessStep]:
        """获取指定步骤"""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def get_next_step_id(self, current_step_id: str) -> Optional[str]:
        """获取下一步骤ID"""
        return self.transitions.get(current_step_id)

    def get_error_handler(self, error_code: str) -> Optional[str]:
        """获取错误处理步骤ID"""
        return self.error_handlers.get(error_code)

    def validate(self) -> List[str]:
        """验证流程定义，返回错误列表

        仅检查结构性错误（引用不存在的步骤、重复ID等）。
        运行时行为（空并行/空循环等）由引擎处理。
        """
        errors = []

        if not self.steps:
            errors.append("Process definition must contain at least one step")

        step_ids = {s.step_id for s in self.steps}
        if len(step_ids) != len(self.steps):
            errors.append("Duplicate step IDs detected")

        first_step_id = self.start_step_id
        if not first_step_id and self.steps:
            first_step_id = self.steps[0].step_id

        if first_step_id and first_step_id not in step_ids:
            errors.append(f"Start step '{first_step_id}' not found in steps")

        # 验证转换目标
        for src, dst in self.transitions.items():
            if src not in step_ids:
                errors.append(f"Transition source '{src}' not found in steps")
            if dst not in step_ids:
                errors.append(f"Transition target '{dst}' not found in steps")

        # 验证错误处理目标
        for error_code, handler in self.error_handlers.items():
            if handler not in step_ids:
                errors.append(f"Error handler step '{handler}' not found for '{error_code}'")

        # 验证逻辑约束（仅结构性）
        for step in self.steps:
            if step.step_type == StepType.PARALLEL and not step.parallel_steps:
                errors.append(
                    f"Parallel step '{step.step_id}' has no parallel_steps defined"
                )
            if step.step_type == StepType.LOOP:
                if not step.loop_steps:
                    errors.append(
                        f"Loop step '{step.step_id}' has no loop_steps defined"
                    )
                if step.max_iterations < 1:
                    errors.append(
                        f"Loop step '{step.step_id}' has invalid max_iterations"
                    )

        return errors


@dataclass
class ProcessContext:
    """流程执行上下文

    保存流程执行过程中的变量、结果和状态信息。

    Attributes:
        process_id: 流程ID
        equipment_id: 设备ID
        chamber_id: 腔体ID（可选）
        state: 当前流程状态
        current_step_id: 当前步骤ID
        variables: 流程变量
        step_results: 步骤结果映射
        started_at: 开始时间
        completed_at: 完成时间
        paused_at: 暂停时间
        error: 错误信息
    """

    process_id: str
    equipment_id: str
    chamber_id: Optional[str] = None
    state: ProcessState = ProcessState.CREATED
    current_step_id: Optional[str] = None
    variables: Dict[str, Any] = field(default_factory=dict)
    step_results: Dict[str, StepResult] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    error: Optional[str] = None

    def get_var(self, name: str, default: Any = None) -> Any:
        """获取变量值"""
        return self.variables.get(name, default)

    def set_var(self, name: str, value: Any) -> None:
        """设置变量值"""
        self.variables[name] = value

    def get_step_result(self, step_id: str) -> Optional[StepResult]:
        """获取步骤结果"""
        return self.step_results.get(step_id)

    def set_step_result(self, step_id: str, result: StepResult) -> None:
        """设置步骤结果"""
        self.step_results[step_id] = result

    @property
    def is_active(self) -> bool:
        """是否处于活跃状态"""
        return self.state in (ProcessState.RUNNING, ProcessState.PAUSED)

    @property
    def is_terminal(self) -> bool:
        """是否处于终态"""
        return self.state in (
            ProcessState.COMPLETED,
            ProcessState.ABORTED,
            ProcessState.FAILED,
        )

    @property
    def elapsed_time(self) -> float:
        """已运行时间（秒）"""
        if not self.started_at:
            return 0.0
        end = self.completed_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "process_id": self.process_id,
            "equipment_id": self.equipment_id,
            "chamber_id": self.chamber_id,
            "state": self.state.value,
            "current_step_id": self.current_step_id,
            "variables": self.variables,
            "step_result_count": len(self.step_results),
            "step_results": {
                sid: {
                    "status": r.status.value,
                    "error": r.error,
                    "duration": r.duration,
                    "retry_attempts": r.retry_attempts,
                }
                for sid, r in self.step_results.items()
            },
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "elapsed_time": self.elapsed_time,
            "error": self.error,
        }

    def __repr__(self) -> str:
        return (
            f"ProcessContext(process_id={self.process_id!r}, "
            f"state={self.state.value}, "
            f"current_step={self.current_step_id!r})"
        )
