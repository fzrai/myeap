"""数字孪生数据模型

定义数字孪生模块使用的所有数据结构，包括虚拟状态、
健康评估、仿真结果和场景定义。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class HealthStatus(str, Enum):
    """健康状态"""

    HEALTHY = "healthy"          # 健康: 90-100
    NORMAL = "normal"            # 正常: 70-90
    ATTENTION = "attention"      # 需关注: 50-70
    DEGRADED = "degraded"        # 退化中: 30-50
    CRITICAL = "critical"        # 危险: 0-30
    UNKNOWN = "unknown"          # 未知


class RiskLevel(str, Enum):
    """风险等级"""

    NONE = "none"               # 无风险
    LOW = "low"                 # 低风险
    MEDIUM = "medium"           # 中风险
    HIGH = "high"               # 高风险
    CRITICAL = "critical"       # 极高风险

    @property
    def priority(self) -> int:
        """获取优先级数值，数值越小优先级越高"""
        priority_map = {
            RiskLevel.CRITICAL: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.MEDIUM: 3,
            RiskLevel.LOW: 4,
            RiskLevel.NONE: 5,
        }
        return priority_map[self]


@dataclass
class TwinState:
    """虚拟设备状态

    表示数字孪生中设备的当前虚拟状态。

    Attributes:
        equipment_id: 设备ID
        timestamp: 状态时间戳
        chambers: 腔体状态，chamber_id -> {parameter: value}
        status: 设备状态
        sub_status: 子状态
        alarms: 告警列表
        sensor_data: 传感器数据
        metadata: 附加元数据
    """

    equipment_id: str
    timestamp: datetime
    chambers: Dict[str, Dict[str, float]] = field(default_factory=dict)
    status: str = "UNKNOWN"
    sub_status: Optional[str] = None
    alarms: List[dict] = field(default_factory=list)
    sensor_data: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "equipment_id": self.equipment_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "chambers": self.chambers,
            "status": self.status,
            "sub_status": self.sub_status,
            "alarms": self.alarms,
            "sensor_data": self.sensor_data,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"TwinState(equipment={self.equipment_id}, status={self.status}, "
            f"sensors={len(self.sensor_data)}, chambers={len(self.chambers)})"
        )


@dataclass
class TwinHealth:
    """数字孪生健康评估

    基于传感器数据和历史趋势对设备健康状态进行综合评估。

    Attributes:
        equipment_id: 设备ID
        overall_score: 综合健康评分 (0-100)
        status: 健康状态
        component_scores: 各组件健康评分
        anomalies: 异常列表
        recommendations: 建议列表
        assessed_at: 评估时间
        confidence: 评估置信度 (0-1)
    """

    equipment_id: str
    overall_score: float  # 0-100
    component_scores: Dict[str, float] = field(default_factory=dict)
    anomalies: List[dict] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    assessed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: HealthStatus = HealthStatus.UNKNOWN
    confidence: float = 0.0

    def __post_init__(self):
        """初始化后自动设置状态"""
        if self.status == HealthStatus.UNKNOWN:
            self.status = self._score_to_status(self.overall_score)

    @staticmethod
    def _score_to_status(score: float) -> HealthStatus:
        """将评分转换为健康状态"""
        if score >= 90:
            return HealthStatus.HEALTHY
        elif score >= 70:
            return HealthStatus.NORMAL
        elif score >= 50:
            return HealthStatus.ATTENTION
        elif score >= 30:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.CRITICAL

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "equipment_id": self.equipment_id,
            "overall_score": self.overall_score,
            "status": self.status.value,
            "component_scores": self.component_scores,
            "anomalies": self.anomalies,
            "recommendations": self.recommendations,
            "assessed_at": self.assessed_at.isoformat() if self.assessed_at else None,
            "confidence": self.confidence,
        }

    def __repr__(self) -> str:
        return (
            f"TwinHealth(equipment={self.equipment_id}, score={self.overall_score:.1f}, "
            f"status={self.status.value})"
        )


@dataclass
class SimulationStep:
    """仿真步骤结果

    表示仿真过程中单个时间步的计算结果。

    Attributes:
        time_offset: 时间偏移（秒）
        timestamp: 仿真时间戳
        parameters: 参数值映射
        events: 该步产生的事件列表
    """

    time_offset: float
    timestamp: datetime
    parameters: Dict[str, float] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class SimulationResult:
    """仿真结果

    表示一次What-If仿真的完整结果。

    Attributes:
        scenario: 仿真场景（字典形式）
        steps: 各时间步结果列表
        predicted_outcomes: 预测结果（兼容旧接口）
        risk_assessment: 风险评估
        summary: 结果摘要
        started_at: 仿真开始时间
        completed_at: 仿真完成时间
    """

    scenario: Dict[str, Any]
    steps: List[SimulationStep] = field(default_factory=list)
    predicted_outcomes: List[Dict[str, Any]] = field(default_factory=list)
    risk_assessment: Optional[Dict[str, Any]] = None
    summary: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def duration(self) -> Optional[float]:
        """获取仿真耗时（秒）"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def step_count(self) -> int:
        """获取仿真步数"""
        return len(self.steps)

    def get_final_parameters(self) -> Dict[str, float]:
        """获取仿真最终参数"""
        if self.steps:
            return self.steps[-1].parameters.copy()
        return {}

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "scenario": self.scenario,
            "predicted_outcomes": self.predicted_outcomes,
            "risk_assessment": self.risk_assessment,
            "summary": self.summary,
            "step_count": self.step_count,
            "duration": self.duration,
            "final_parameters": self.get_final_parameters(),
        }

    def __repr__(self) -> str:
        return (
            f"SimulationResult(steps={self.step_count}, "
            f"risk={self.risk_assessment.get('level', 'N/A') if self.risk_assessment else 'N/A'})"
        )


class SimulationScenario(BaseModel):
    """仿真场景定义

    定义What-If仿真的输入场景。

    Attributes:
        scenario_id: 场景ID
        name: 场景名称
        description: 场景描述
        equipment_id: 目标设备ID
        parameters: 修改的工艺参数
        duration: 仿真时长（秒）
        step_interval: 仿真步长（秒）
        constraints: 约束条件
        metadata: 附加信息
    """

    scenario_id: str
    name: str
    equipment_id: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    duration: float = 3600.0
    step_interval: float = 60.0
    description: Optional[str] = None
    constraints: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def step_count(self) -> int:
        """获取仿真步数"""
        return max(1, int(self.duration / self.step_interval))

    def to_sim_dict(self) -> dict:
        """转换为仿真器使用的字典"""
        return {
            "parameters": self.parameters,
            "duration": self.duration,
            "step_interval": self.step_interval,
            "scenario_id": self.scenario_id,
            "name": self.name,
        }

    model_config = ConfigDict(use_enum_values=True)


@dataclass
class TwinEvent:
    """数字孪生事件

    表示数字孪生产生的事件。

    Attributes:
        event_type: 事件类型
        equipment_id: 设备ID
        timestamp: 事件时间
        data: 事件数据
    """

    event_type: str
    equipment_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"TwinEvent(type={self.event_type}, equipment={self.equipment_id})"
