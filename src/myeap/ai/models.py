"""AI/ML数据模型

定义AI智能分析模块使用的数据类型，包括故障预测、良率预测和根因分析结果。
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class AnalysisStatus(str, Enum):
    """分析状态枚举

    表示AI分析任务的状态。

    Values:
        PENDING: 等待中
        RUNNING: 运行中
        COMPLETED: 已完成
        FAILED: 失败
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PredictionConfidence(str, Enum):
    """预测置信度等级枚举

    Values:
        HIGH: 高置信度 (>0.8)
        MEDIUM: 中置信度 (0.5-0.8)
        LOW: 低置信度 (<0.5)
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @classmethod
    def from_score(cls, score: float) -> "PredictionConfidence":
        """从分数获取置信度等级

        Args:
            score: 置信度分数 (0-1)

        Returns:
            PredictionConfidence: 对应的置信度等级
        """
        if score >= 0.8:
            return cls.HIGH
        elif score >= 0.5:
            return cls.MEDIUM
        else:
            return cls.LOW


@dataclass
class FailurePrediction:
    """故障预测结果

    表示对设备未来故障的预测分析结果。

    Attributes:
        equipment_id: 设备标识
        failure_probability: 故障概率 (0-1)
        predicted_failure_time: 预测故障时间
        remaining_useful_life_hours: 剩余使用寿命(小时)
        confidence_interval: 置信区间 (lower, upper)
        risk_factors: 风险因素列表
        recommended_actions: 建议措施
    """

    equipment_id: str
    failure_probability: float
    predicted_failure_time: Optional[datetime]
    remaining_useful_life_hours: float
    confidence_interval: Tuple[float, float]
    risk_factors: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)

    @property
    def risk_level(self) -> str:
        """获取风险等级

        Returns:
            str: risk level (critical, high, medium, low)
        """
        if self.failure_probability >= 0.8:
            return "critical"
        elif self.failure_probability >= 0.6:
            return "high"
        elif self.failure_probability >= 0.3:
            return "medium"
        else:
            return "low"

    @property
    def time_to_failure_hours(self) -> float:
        """距离预测失效时间的小时数

        Returns:
            float: time to failure in hours, or inf if no prediction
        """
        if self.predicted_failure_time is None:
            return float("inf")
        remaining = (self.predicted_failure_time - datetime.now()).total_seconds() / 3600
        return max(0, remaining)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "equipment_id": self.equipment_id,
            "failure_probability": self.failure_probability,
            "predicted_failure_time": (
                self.predicted_failure_time.isoformat()
                if self.predicted_failure_time
                else None
            ),
            "remaining_useful_life_hours": self.remaining_useful_life_hours,
            "confidence_interval": list(self.confidence_interval),
            "risk_factors": self.risk_factors,
            "recommended_actions": self.recommended_actions,
            "risk_level": self.risk_level,
        }


@dataclass
class YieldPrediction:
    """良率预测结果

    表示对批次良率的预测分析结果。

    Attributes:
        batch_id: 批次标识
        predicted_yield: 预测良率 (0-1)
        confidence_interval: 置信区间 (lower, upper)
        key_influence_factors: 关键影响因素列表
        feature_contributions: 各特征的贡献度
        confidence_level: 置信度等级
    """

    batch_id: str
    predicted_yield: float
    confidence_interval: Tuple[float, float]
    key_influence_factors: List[Tuple[str, float]] = field(default_factory=list)
    feature_contributions: Dict[str, float] = field(default_factory=dict)
    confidence_level: PredictionConfidence = PredictionConfidence.MEDIUM

    @property
    def yield_rate_percent(self) -> float:
        """获取百分比良率"""
        return self.predicted_yield * 100

    @property
    def is_acceptable(self) -> bool:
        """检查良率是否可接受 (>= 95%)"""
        return self.predicted_yield >= 0.95

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "batch_id": self.batch_id,
            "predicted_yield": self.predicted_yield,
            "yield_rate_percent": self.yield_rate_percent,
            "confidence_interval": list(self.confidence_interval),
            "key_influence_factors": [
                {"factor": f, "contribution": v}
                for f, v in self.key_influence_factors
            ],
            "feature_contributions": self.feature_contributions,
            "confidence_level": self.confidence_level.value,
            "is_acceptable": self.is_acceptable,
        }


@dataclass
class RootCauseResult:
    """根因分析结果

    表示根因分析的结果，包含候选根因及其排序。

    Attributes:
        incident_id: 事件标识
        root_causes: 候选根因列表 (因子, 置信度)
        propagation_path: 异常传播路径
        correlation_scores: 关联性分数
        analysis_time: 分析时间
        evidence: 支持证据
    """

    incident_id: str
    root_causes: List[Tuple[str, float]] = field(default_factory=list)
    propagation_path: List[str] = field(default_factory=list)
    correlation_scores: Dict[str, float] = field(default_factory=dict)
    analysis_time: Optional[datetime] = None
    evidence: List[str] = field(default_factory=list)

    @property
    def primary_cause(self) -> Optional[Tuple[str, float]]:
        """获取主要根因

        Returns:
            Optional[Tuple[str, float]]: (根因, 置信度)
        """
        if self.root_causes:
            return self.root_causes[0]
        return None

    @property
    def has_root_cause(self) -> bool:
        """是否存在有效的根因"""
        return len(self.root_causes) > 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "incident_id": self.incident_id,
            "root_causes": [
                {"cause": c, "confidence": v} for c, v in self.root_causes
            ],
            "primary_cause": (
                {"cause": self.primary_cause[0], "confidence": self.primary_cause[1]}
                if self.primary_cause
                else None
            ),
            "propagation_path": self.propagation_path,
            "correlation_scores": self.correlation_scores,
            "analysis_time": (
                self.analysis_time.isoformat() if self.analysis_time else None
            ),
            "evidence": self.evidence,
        }


class ProcessParameter(BaseModel):
    """工艺参数

    表示影响良率的工艺参数。

    Attributes:
        name: 参数名称
        value: 参数值
        unit: 单位
        target: 目标值
        tolerance_upper: 上公差
        tolerance_lower: 下公差
        importance: 重要性权重
    """

    name: str = Field(description="参数名称")
    value: float = Field(description="参数值")
    unit: str = Field(default="", description="单位")
    target: Optional[float] = Field(default=None, description="目标值")
    tolerance_upper: Optional[float] = Field(default=None, description="上公差")
    tolerance_lower: Optional[float] = Field(default=None, description="下公差")
    importance: float = Field(default=1.0, description="重要性权重")

    @property
    def deviation(self) -> Optional[float]:
        """计算与目标值的偏差

        Returns:
            Optional[float]: 偏差值，如果没有目标值则返回None
        """
        if self.target is not None:
            return self.value - self.target
        return None

    @property
    def is_within_tolerance(self) -> bool:
        """检查是否在公差范围内

        Returns:
            bool: 是否在公差范围内
        """
        if self.target is None:
            return True
        if self.tolerance_upper is not None and self.value > self.target + self.tolerance_upper:
            return False
        if self.tolerance_lower is not None and self.value < self.target - self.tolerance_lower:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "target": self.target,
            "tolerance_upper": self.tolerance_upper,
            "tolerance_lower": self.tolerance_lower,
            "importance": self.importance,
            "deviation": self.deviation,
            "is_within_tolerance": self.is_within_tolerance,
        }


@dataclass
class MaintenanceRecommendation:
    """维护建议

    表示基于预测性维护生成的维护建议。

    Attributes:
        equipment_id: 设备标识
        priority: 优先级 (1=最高)
        action: 建议动作
        reason: 原因
        estimated_duration_hours: 预计维护时长
        suggested_date: 建议执行日期
    """

    equipment_id: str
    priority: int
    action: str
    reason: str
    estimated_duration_hours: float = 1.0
    suggested_date: Optional[datetime] = None

    @property
    def is_urgent(self) -> bool:
        """是否为紧急维护"""
        return self.priority <= 1


@dataclass
class AnomalyPattern:
    """异常模式

    表示从历史数据中识别的异常模式。

    Attributes:
        pattern_id: 模式标识
        equipment_id: 关联设备ID
        feature_signature: 特征签名
        occurrence_count: 出现次数
        last_seen: 最后出现时间
        severity: 严重程度
        description: 模式描述
    """

    pattern_id: str
    equipment_id: str
    feature_signature: Dict[str, float] = field(default_factory=dict)
    occurrence_count: int = 1
    last_seen: Optional[datetime] = None
    severity: float = 0.5
    description: str = ""

    def increment_occurrence(self) -> None:
        """增加出现次数"""
        self.occurrence_count += 1
        self.last_seen = datetime.now()


@dataclass
class TrainingResult:
    """训练结果

    表示AI模型训练的结果。

    Attributes:
        model_name: 模型名称
        status: 训练状态
        training_time_seconds: 训练耗时
        metrics: 性能指标
        parameters: 模型参数
        data_points_count: 训练数据点数
    """

    model_name: str
    status: AnalysisStatus
    training_time_seconds: float = 0.0
    metrics: Dict[str, float] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    data_points_count: int = 0

    @property
    def is_successful(self) -> bool:
        """检查训练是否成功"""
        return self.status == AnalysisStatus.COMPLETED

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "model_name": self.model_name,
            "status": self.status.value,
            "training_time_seconds": self.training_time_seconds,
            "metrics": self.metrics,
            "parameters": self.parameters,
            "data_points_count": self.data_points_count,
        }


@dataclass
class EquipmentHealthReport:
    """设备健康报告

    综合设备健康状态报告，包含故障预测、维护建议和整体评分。

    Attributes:
        equipment_id: 设备标识
        health_score: 健康评分 (0-100)
        failure_prediction: 故障预测结果
        maintenance_recommendations: 维护建议列表
        active_alerts: 活跃告警数量
        trend: 健康趋势 (improving, stable, declining)
        last_updated: 最后更新时间
    """

    equipment_id: str
    health_score: float
    failure_prediction: Optional[FailurePrediction] = None
    maintenance_recommendations: List[MaintenanceRecommendation] = field(default_factory=list)
    active_alerts: int = 0
    trend: str = "stable"
    last_updated: Optional[datetime] = None

    @property
    def health_status(self) -> str:
        """获取健康状态描述

        Returns:
            str: 健康状态 (good, fair, poor, critical)
        """
        if self.health_score >= 80:
            return "good"
        elif self.health_score >= 60:
            return "fair"
        elif self.health_score >= 30:
            return "poor"
        else:
            return "critical"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "equipment_id": self.equipment_id,
            "health_score": self.health_score,
            "health_status": self.health_status,
            "failure_prediction": (
                self.failure_prediction.to_dict() if self.failure_prediction else None
            ),
            "maintenance_recommendations": [
                {
                    "action": r.action,
                    "priority": r.priority,
                    "reason": r.reason,
                }
                for r in self.maintenance_recommendations
            ],
            "active_alerts": self.active_alerts,
            "trend": self.trend,
            "last_updated": (
                self.last_updated.isoformat() if self.last_updated else None
            ),
        }
