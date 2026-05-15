"""工艺控制模块

提供工艺流程管理功能，包括工艺的启动、暂停、恢复、中止等。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from dataclasses import dataclass, field


class ProcessState(Enum):
    """工艺状态"""

    QUEUED = "QUEUED"
    LOADING = "LOADING"
    PREPARING = "PREPARING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    FAILED = "FAILED"


class ProcessEvent(Enum):
    """工艺事件"""

    STARTED = "STARTED"
    STEP_STARTED = "STEP_STARTED"
    STEP_COMPLETED = "STEP_COMPLETED"
    PAUSED = "PAUSED"
    RESUMED = "RESUMED"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    ALARM = "ALARM"
    ERROR = "ERROR"


@dataclass
class ProcessStep:
    """工艺步骤"""

    step_id: int
    name: str
    duration: float  # 秒
    parameters: Dict[str, Any] = field(default_factory=dict)

    # 状态
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None

    @property
    def elapsed_time(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.completed_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()

    @property
    def progress(self) -> float:
        if self.started_at is None:
            return 0.0
        elapsed = self.elapsed_time
        return min(elapsed / self.duration, 1.0) if self.duration > 0 else 1.0


@dataclass
class ProcessData:
    """工艺数据点"""

    timestamp: datetime
    step_id: int
    wafer_id: Optional[str]
    values: Dict[str, float]


@dataclass
class ProcessInstance:
    """工艺实例

    表示一次工艺执行的完整信息。
    """

    process_id: str
    equipment_id: str
    chamber_id: str
    recipe_id: str
    recipe_name: str

    # 状态
    state: ProcessState = ProcessState.QUEUED
    current_step: int = 0

    # 配方信息
    steps: List[ProcessStep] = field(default_factory=list)

    # 时间戳
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None

    # 载具
    wafer_ids: List[str] = field(default_factory=list)
    lot_id: Optional[str] = None
    carrier_id: Optional[str] = None

    # 数据收集
    data_points: List[ProcessData] = field(default_factory=list)

    # 结果
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    # 元数据
    priority: int = 5
    created_by: Optional[str] = None
    comments: List[str] = field(default_factory=list)

    @property
    def is_active(self) -> bool:
        """工艺是否处于活跃状态"""
        return self.state in (
            ProcessState.LOADING,
            ProcessState.PREPARING,
            ProcessState.RUNNING,
            ProcessState.PAUSED,
        )

    @property
    def is_terminal(self) -> bool:
        """工艺是否处于终态"""
        return self.state in (
            ProcessState.COMPLETED,
            ProcessState.ABORTED,
            ProcessState.FAILED,
        )

    @property
    def progress(self) -> float:
        """工艺进度"""
        if not self.started_at:
            return 0.0
        if self.is_terminal:
            return 1.0 if self.state == ProcessState.COMPLETED else 0.0

        total_duration = sum(step.duration for step in self.steps)
        if total_duration == 0:
            return 0.0

        elapsed = 0.0
        for i, step in enumerate(self.steps):
            if i < self.current_step:
                elapsed += step.duration
            elif i == self.current_step:
                elapsed += step.elapsed_time

        return min(elapsed / total_duration, 1.0)

    @property
    def current_step_info(self) -> Optional[ProcessStep]:
        """当前步骤信息"""
        if 0 <= self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None

    def start(self) -> None:
        """开始工艺"""
        self.state = ProcessState.RUNNING
        self.started_at = datetime.utcnow()
        if self.steps and self.current_step < len(self.steps):
            self.steps[self.current_step].started_at = datetime.utcnow()

    def pause(self) -> None:
        """暂停工艺"""
        if self.state == ProcessState.RUNNING:
            self.state = ProcessState.PAUSED
            self.paused_at = datetime.utcnow()
            if self.current_step_info:
                self.steps[self.current_step].completed_at = datetime.utcnow()

    def resume(self) -> None:
        """恢复工艺"""
        if self.state == ProcessState.PAUSED:
            self.state = ProcessState.RUNNING
            self.paused_at = None
            if self.current_step_info:
                self.steps[self.current_step].started_at = datetime.utcnow()

    def complete(self, result: Optional[Dict[str, Any]] = None) -> None:
        """完成工艺"""
        self.state = ProcessState.COMPLETED
        self.completed_at = datetime.utcnow()
        self.result = result

    def abort(self) -> None:
        """中止工艺"""
        self.state = ProcessState.ABORTED
        self.completed_at = datetime.utcnow()

    def fail(self, error_message: str) -> None:
        """工艺失败"""
        self.state = ProcessState.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error_message

    def move_to_step(self, step_id: int) -> None:
        """移动到指定步骤"""
        if 0 <= step_id < len(self.steps):
            if self.current_step_info and not self.current_step_info.is_completed:
                self.steps[self.current_step].completed_at = datetime.utcnow()
            self.current_step = step_id
            self.steps[step_id].started_at = datetime.utcnow()

    def add_data_point(self, step_id: int, wafer_id: Optional[str], values: Dict[str, float]) -> None:
        """添加数据点"""
        self.data_points.append(
            ProcessData(
                timestamp=datetime.utcnow(),
                step_id=step_id,
                wafer_id=wafer_id,
                values=values,
            )
        )

    def add_comment(self, comment: str, author: Optional[str] = None) -> None:
        """添加评论"""
        entry = f"[{datetime.utcnow().isoformat()}] {comment}"
        if author:
            entry = f"{entry} - {author}"
        self.comments.append(entry)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "process_id": self.process_id,
            "equipment_id": self.equipment_id,
            "chamber_id": self.chamber_id,
            "recipe_id": self.recipe_id,
            "recipe_name": self.recipe_name,
            "state": self.state.value,
            "current_step": self.current_step,
            "progress": self.progress,
            "steps": [
                {
                    "step_id": s.step_id,
                    "name": s.name,
                    "duration": s.duration,
                    "started_at": s.started_at.isoformat() if s.started_at else None,
                    "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                    "progress": s.progress,
                }
                for s in self.steps
            ],
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "wafer_ids": self.wafer_ids,
            "lot_id": self.lot_id,
            "carrier_id": self.carrier_id,
            "result": self.result,
            "error_message": self.error_message,
            "priority": self.priority,
            "comments": self.comments,
        }


class ProcessManager:
    """工艺管理器

    管理设备的工艺实例。
    """

    def __init__(self, equipment_id: str):
        self.equipment_id = equipment_id
        self._processes: Dict[str, ProcessInstance] = {}

    def add_process(self, process: ProcessInstance) -> None:
        """添加工艺实例"""
        self._processes[process.process_id] = process

    def remove_process(self, process_id: str) -> bool:
        """移除工艺实例"""
        if process_id in self._processes:
            del self._processes[process_id]
            return True
        return False

    def get_process(self, process_id: str) -> Optional[ProcessInstance]:
        """获取工艺实例"""
        return self._processes.get(process_id)

    def get_all_processes(self) -> List[ProcessInstance]:
        """获取所有工艺实例"""
        return list(self._processes.values())

    def get_active_processes(self) -> List[ProcessInstance]:
        """获取活跃工艺"""
        return [p for p in self._processes.values() if p.is_active]

    def get_chamber_processes(self, chamber_id: str) -> List[ProcessInstance]:
        """获取指定腔体的工艺"""
        return [p for p in self._processes.values() if p.chamber_id == chamber_id]

    def get_chamber_active_process(self, chamber_id: str) -> Optional[ProcessInstance]:
        """获取指定腔体的活跃工艺"""
        processes = [p for p in self._processes.values() if p.chamber_id == chamber_id and p.is_active]
        return processes[0] if processes else None

    def get_completed_processes(
        self,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[ProcessInstance]:
        """获取已完成的工艺"""
        completed = [p for p in self._processes.values() if p.is_terminal]
        if since:
            completed = [p for p in completed if p.completed_at and p.completed_at >= since]
        completed.sort(key=lambda p: p.completed_at or datetime.min, reverse=True)
        return completed[:limit]
