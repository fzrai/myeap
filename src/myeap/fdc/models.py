"""FDC数据模型

定义FDC引擎使用的数据类型，包括故障类型、故障实体等。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FaultType(str, Enum):
    """故障类型"""

    # 温度相关
    TEMP_DRIFT = "temp_drift"  # 温度漂移
    TEMP_SPIKE = "temp_spike"  # 温度尖峰
    TEMP_OSCILLATION = "temp_oscillation"  # 温度振荡

    # 压力相关
    PRESSURE_DRIFT = "pressure_drift"  # 压力漂移
    PRESSURE_DROP = "pressure_drop"  # 压力下降
    PRESSURE_SPIKE = "pressure_spike"  # 压力尖峰

    # 气体相关
    GAS_FLOW_ERROR = "gas_flow_error"  # 气体流量异常
    GAS_LEAK = "gas_leak"  # 气体泄漏
    MFC_DRIFT = "mfc_drift"  # MFC漂移

    # 等离子体相关
    PLASMA_UNSTABLE = "plasma_unstable"  # 等离子体不稳定
    PLASMA_EXTINCTION = "plasma_extinction"  # 等离子体熄灭

    # 工艺相关
    ENDPOINT_EARLY = "endpoint_early"  # 终点提前
    ENDPOINT_LATE = "endpoint_late"  # 终点延迟
    FILM_THICKNESS_ERROR = "film_thickness_error"  # 膜厚异常

    # 设备相关
    CHAMBER_CONTAMINATION = "chamber_contamination"  # 腔体污染
    ESC_HEATER_FAILURE = "esc_heater_failure"  # ESC加热器故障
    RF_POWER_ERROR = "rf_power_error"  # RF功率异常

    # 未知类型
    UNKNOWN = "unknown"


class FaultSeverity(str, Enum):
    """故障严重程度"""

    INFO = "info"  # 信息
    WARNING = "warning"  # 警告
    CRITICAL = "critical"  # 严重
    FATAL = "fatal"  # 致命

    @property
    def priority(self) -> int:
        """获取优先级数值，数值越小优先级越高"""
        priority_map = {
            FaultSeverity.FATAL: 1,
            FaultSeverity.CRITICAL: 2,
            FaultSeverity.WARNING: 3,
            FaultSeverity.INFO: 4,
        }
        return priority_map[self]


class FaultStatus(str, Enum):
    """故障状态"""

    DETECTED = "detected"  # 已检测
    ANALYZING = "analyzing"  # 分析中
    CONFIRMED = "confirmed"  # 已确认
    RESOLVED = "resolved"  # 已解决
    DISMISSED = "dismissed"  # 已忽略


class FaultCategory(str, Enum):
    """故障类别"""

    TEMPERATURE = "temperature"  # 温度相关
    PRESSURE = "pressure"  # 压力相关
    GAS = "gas"  # 气体相关
    PLASMA = "plasma"  # 等离子体相关
    PROCESS = "process"  # 工艺相关
    EQUIPMENT = "equipment"  # 设备相关
    UNKNOWN = "unknown"  # 未知

    @classmethod
    def from_fault_type(cls, fault_type: FaultType) -> "FaultCategory":
        """从故障类型获取故障类别"""
        mapping = {
            FaultType.TEMP_DRIFT: cls.TEMPERATURE,
            FaultType.TEMP_SPIKE: cls.TEMPERATURE,
            FaultType.TEMP_OSCILLATION: cls.TEMPERATURE,
            FaultType.PRESSURE_DRIFT: cls.PRESSURE,
            FaultType.PRESSURE_DROP: cls.PRESSURE,
            FaultType.PRESSURE_SPIKE: cls.PRESSURE,
            FaultType.GAS_FLOW_ERROR: cls.GAS,
            FaultType.GAS_LEAK: cls.GAS,
            FaultType.MFC_DRIFT: cls.GAS,
            FaultType.PLASMA_UNSTABLE: cls.PLASMA,
            FaultType.PLASMA_EXTINCTION: cls.PLASMA,
            FaultType.ENDPOINT_EARLY: cls.PROCESS,
            FaultType.ENDPOINT_LATE: cls.PROCESS,
            FaultType.FILM_THICKNESS_ERROR: cls.PROCESS,
            FaultType.CHAMBER_CONTAMINATION: cls.EQUIPMENT,
            FaultType.ESC_HEATER_FAILURE: cls.EQUIPMENT,
            FaultType.RF_POWER_ERROR: cls.EQUIPMENT,
        }
        return mapping.get(fault_type, cls.UNKNOWN)


class Fault(BaseModel):
    """故障实体

    表示一个检测到的故障实例。

    Attributes:
        fault_id: 故障唯一标识
        fault_type: 故障类型
        severity: 故障严重程度
        status: 故障状态
        equipment_id: 设备ID
        chamber_id: 腔体ID（可选）
        start_time: 故障开始时间
        end_time: 故障结束时间（可选）
        affected_parameters: 受影响的参数列表
        feature_vector: 特征向量（可选）
        root_cause: 根本原因（可选）
        confidence: 置信度
        recommendations: 建议的处理措施
        metadata: 附加元数据
    """

    fault_id: str
    fault_type: FaultType
    severity: FaultSeverity

    equipment_id: str
    chamber_id: Optional[str] = None

    # 时间和状态
    start_time: datetime
    end_time: Optional[datetime] = None
    status: FaultStatus = FaultStatus.DETECTED

    # 特征
    affected_parameters: List[str] = Field(default_factory=list)
    feature_vector: Optional[Dict[str, Any]] = None

    # 根因分析
    root_cause: Optional[str] = None
    confidence: float = 0.0

    # 建议
    recommendations: List[str] = Field(default_factory=list)

    # 附加信息
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def category(self) -> FaultCategory:
        """获取故障类别"""
        return FaultCategory.from_fault_type(self.fault_type)

    @property
    def duration(self) -> Optional[float]:
        """获取故障持续时间（秒）"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    @property
    def is_active(self) -> bool:
        """判断故障是否处于活跃状态"""
        return self.status in (
            FaultStatus.DETECTED,
            FaultStatus.ANALYZING,
            FaultStatus.CONFIRMED,
        )

    def resolve(self, end_time: Optional[datetime] = None) -> None:
        """解决故障"""
        self.end_time = end_time or datetime.now(timezone.utc)
        self.status = FaultStatus.RESOLVED

    def dismiss(self, reason: Optional[str] = None) -> None:
        """忽略故障"""
        self.end_time = datetime.now(timezone.utc)
        self.status = FaultStatus.DISMISSED
        if reason:
            self.metadata["dismiss_reason"] = reason

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "fault_id": self.fault_id,
            "fault_type": self.fault_type.value,
            "severity": self.severity.value,
            "status": self.status.value,
            "equipment_id": self.equipment_id,
            "chamber_id": self.chamber_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "affected_parameters": self.affected_parameters,
            "feature_vector": self.feature_vector,
            "root_cause": self.root_cause,
            "confidence": self.confidence,
            "recommendations": self.recommendations,
            "metadata": self.metadata,
            "category": self.category.value,
        }

    def __repr__(self) -> str:
        return (
            f"Fault(id={self.fault_id}, type={self.fault_type.value}, "
            f"severity={self.severity.value}, equipment={self.equipment_id})"
        )


@dataclass
class DetectionResult:
    """检测结果

    Attributes:
        is_anomaly: 是否为异常
        score: 异常分数 (0-1)
        z_scores: Z分数列表（可选）
        anomaly_indices: 异常索引列表（可选）
        change_point_index: 变化点索引（可选）
    """

    is_anomaly: bool
    score: float
    z_scores: Optional[List[float]] = None
    anomaly_indices: Optional[List[int]] = None
    change_point_index: Optional[int] = None


@dataclass
class FaultClassification:
    """故障分类结果

    Attributes:
        fault_type: 故障类型
        confidence: 置信度
        matched_rule: 匹配的规则名称（可选）
    """

    fault_type: FaultType
    confidence: float
    matched_rule: Optional[str] = None


@dataclass
class FDCEvent:
    """FDC事件

    表示FDC引擎产生的事件。

    Attributes:
        event_type: 事件类型
        equipment_id: 设备ID
        chamber_id: 腔体ID（可选）
        fault: 关联的故障（可选）
        timestamp: 事件时间
        data: 事件数据
    """

    event_type: str
    equipment_id: str
    chamber_id: Optional[str] = None
    fault: Optional[Fault] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    data: Dict[str, Any] = field(default_factory=dict)


class FDCEventType(str, Enum):
    """FDC事件类型"""

    FAULT_DETECTED = "fault_detected"  # 故障检测到
    FAULT_CONFIRMED = "fault_confirmed"  # 故障确认
    FAULT_RESOLVED = "fault_resolved"  # 故障解决
    BASELINE_UPDATED = "baseline_updated"  # 基线更新
    ANOMALY_DETECTED = "anomaly_detected"  # 异常检测
    CLASSIFICATION_COMPLETE = "classification_complete"  # 分类完成
