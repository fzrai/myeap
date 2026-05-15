"""数据模型定义

定义数据采集模块使用的数据类型。
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class DataPoint:
    """数据点

    表示一个采集到的工艺参数数据点。

    Attributes:
        equipment_id: 设备ID
        chamber_id: 腔体ID（可选）
        parameter_name: 参数名称
        value: 参数值
        unit: 参数单位（可选）
        timestamp: 采集时间戳
        quality: 数据质量 (normal, suspect, invalid)
    """

    def __init__(
        self,
        equipment_id: str,
        parameter_name: str,
        value: float,
        chamber_id: Optional[str] = None,
        unit: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        quality: str = "normal",
    ):
        self.equipment_id = equipment_id
        self.chamber_id = chamber_id
        self.parameter_name = parameter_name
        self.value = value
        self.unit = unit
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.quality = quality

    def __repr__(self) -> str:
        return (
            f"DataPoint(equipment_id={self.equipment_id}, "
            f"parameter={self.parameter_name}, value={self.value})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "equipment_id": self.equipment_id,
            "chamber_id": self.chamber_id,
            "parameter_name": self.parameter_name,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp.isoformat(),
            "quality": self.quality,
        }


class DataBatch:
    """数据批次

    表示一批采集到的数据点。

    Attributes:
        equipment_id: 设备ID
        chamber_id: 腔体ID（可选）
        points: 数据点列表
        collected_at: 采集完成时间
    """

    def __init__(
        self,
        equipment_id: str,
        points: List[DataPoint],
        chamber_id: Optional[str] = None,
        collected_at: Optional[datetime] = None,
    ):
        self.equipment_id = equipment_id
        self.chamber_id = chamber_id
        self.points = points
        self.collected_at = collected_at or datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return (
            f"DataBatch(equipment_id={self.equipment_id}, "
            f"points={len(self.points)})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "equipment_id": self.equipment_id,
            "chamber_id": self.chamber_id,
            "points": [p.to_dict() for p in self.points],
            "collected_at": self.collected_at.isoformat(),
        }
