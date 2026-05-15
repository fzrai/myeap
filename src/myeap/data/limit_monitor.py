"""限值监控器

监控工艺参数是否超出限值，支持控制限和规格限。
"""

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from myeap.data.models import DataBatch, DataPoint

logger = logging.getLogger(__name__)


class LimitType(Enum):
    """限值类型

    Attributes:
        UCL: Upper Control Limit - 上控制限
        LCL: Lower Control Limit - 下控制限
        USL: Upper Spec Limit - 上规格限
        LSL: Lower Spec Limit - 下规格限
    """

    UCL = "ucl"  # Upper Control Limit
    LCL = "lcl"  # Lower Control Limit
    USL = "usl"  # Upper Spec Limit
    LSL = "lsl"  # Lower Spec Limit

    @property
    def is_control_limit(self) -> bool:
        """是否为控制限"""
        return self in (LimitType.UCL, LimitType.LCL)

    @property
    def is_spec_limit(self) -> bool:
        """是否为规格限"""
        return self in (LimitType.USL, LimitType.LSL)


class Limit:
    """限值定义

    Attributes:
        parameter_name: 参数名称
        limit_type: 限值类型
        value: 限值
        severity: 严重程度 (warning, critical)
    """

    def __init__(
        self,
        parameter_name: str,
        limit_type: LimitType,
        value: float,
        severity: str = "warning",
    ):
        self.parameter_name = parameter_name
        self.limit_type = limit_type
        self.value = value
        self.severity = severity

    def __repr__(self) -> str:
        return (
            f"Limit(parameter={self.parameter_name}, "
            f"type={self.limit_type.value}, value={self.value}, "
            f"severity={self.severity})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "parameter_name": self.parameter_name,
            "limit_type": self.limit_type.value,
            "value": self.value,
            "severity": self.severity,
        }


class LimitViolation:
    """限值违规

    Attributes:
        equipment_id: 设备ID
        parameter_name: 参数名称
        value: 当前值
        limit: 违规的限值
        deviation: 偏差量
        timestamp: 违规时间
    """

    def __init__(
        self,
        equipment_id: str,
        parameter_name: str,
        value: float,
        limit: Limit,
        deviation: float,
        timestamp: Optional[datetime] = None,
    ):
        self.equipment_id = equipment_id
        self.parameter_name = parameter_name
        self.value = value
        self.limit = limit
        self.deviation = deviation
        self.timestamp = timestamp or datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return (
            f"LimitViolation(equipment={self.equipment_id}, "
            f"parameter={self.parameter_name}, value={self.value}, "
            f"limit={self.limit.value}, deviation={self.deviation})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "equipment_id": self.equipment_id,
            "parameter_name": self.parameter_name,
            "value": self.value,
            "limit": self.limit.to_dict(),
            "deviation": self.deviation,
            "timestamp": self.timestamp.isoformat(),
        }


class LimitMonitor:
    """限值监控器

    监控工艺参数是否超出限值：
    - 控制限 (UCL/LCL) - 工艺控制
    - 规格限 (USL/LSL) - 产品规格
    - 自动报警

    Attributes:
        on_violation: 违规回调函数

    Example:
        monitor = LimitMonitor()
        monitor.add_limit("eq-001", Limit("Temperature", LimitType.UCL, 100.0))
        violation = await monitor.check(data_point)
    """

    def __init__(self):
        """初始化限值监控器"""
        self._limits: Dict[str, List[Limit]] = {}  # equipment_id -> limits
        self._on_violation: Optional[Callable[[LimitViolation], None]] = None
        self._on_violation_async: Optional[Callable[[LimitViolation], Any]] = None
        self._violation_count = 0

    def set_on_violation(
        self,
        callback: Callable[[LimitViolation], None],
    ) -> None:
        """设置违规回调（同步）

        Args:
            callback: 违规回调函数
        """
        self._on_violation = callback

    def set_on_violation_async(
        self,
        callback: Callable[[LimitViolation], Any],
    ) -> None:
        """设置违规回调（异步）

        Args:
            callback: 异步违规回调函数
        """
        self._on_violation_async = callback

    def add_limit(self, equipment_id: str, limit: Limit) -> None:
        """添加限值

        Args:
            equipment_id: 设备ID
            limit: 限值定义
        """
        if equipment_id not in self._limits:
            self._limits[equipment_id] = []
        self._limits[equipment_id].append(limit)
        logger.debug(f"Added limit for {equipment_id}: {limit}")

    def remove_limit(
        self,
        equipment_id: str,
        parameter_name: str,
        limit_type: Optional[LimitType] = None,
    ) -> bool:
        """移除限值

        Args:
            equipment_id: 设备ID
            parameter_name: 参数名称
            limit_type: 限值类型（可选，指定则只删除指定类型）

        Returns:
            bool: 是否成功删除
        """
        if equipment_id not in self._limits:
            return False

        original_count = len(self._limits[equipment_id])
        if limit_type:
            self._limits[equipment_id] = [
                l for l in self._limits[equipment_id]
                if not (l.parameter_name == parameter_name and l.limit_type == limit_type)
            ]
        else:
            self._limits[equipment_id] = [
                l for l in self._limits[equipment_id]
                if l.parameter_name != parameter_name
            ]

        removed = original_count - len(self._limits[equipment_id])
        return removed > 0

    def get_limits(self, equipment_id: str) -> List[Limit]:
        """获取设备的所有限值

        Args:
            equipment_id: 设备ID

        Returns:
            限值列表
        """
        return self._limits.get(equipment_id, []).copy()

    def clear_limits(self, equipment_id: Optional[str] = None) -> None:
        """清除限值

        Args:
            equipment_id: 设备ID（可选，为None则清除所有）
        """
        if equipment_id:
            self._limits.pop(equipment_id, None)
        else:
            self._limits.clear()

    async def check(self, data_point: DataPoint) -> Optional[LimitViolation]:
        """检查数据点是否违规

        Args:
            data_point: 数据点

        Returns:
            LimitViolation: 违规信息（如果有）
        """
        if data_point.equipment_id not in self._limits:
            return None

        limits = self._limits[data_point.equipment_id]
        for limit in limits:
            if limit.parameter_name != data_point.parameter_name:
                continue

            violated = False
            if limit.limit_type == LimitType.UCL and data_point.value > limit.value:
                violated = True
            elif limit.limit_type == LimitType.LCL and data_point.value < limit.value:
                violated = True
            elif limit.limit_type == LimitType.USL and data_point.value > limit.value:
                violated = True
            elif limit.limit_type == LimitType.LSL and data_point.value < limit.value:
                violated = True

            if violated:
                deviation = data_point.value - limit.value
                violation = LimitViolation(
                    equipment_id=data_point.equipment_id,
                    parameter_name=data_point.parameter_name,
                    value=data_point.value,
                    limit=limit,
                    deviation=deviation,
                    timestamp=data_point.timestamp,
                )

                self._violation_count += 1
                await self._notify_violation(violation)
                return violation

        return None

    async def check_batch(self, batch: DataBatch) -> List[LimitViolation]:
        """检查一批数据

        Args:
            batch: 数据批次

        Returns:
            违规列表
        """
        violations = []
        for point in batch.points:
            violation = await self.check(point)
            if violation:
                violations.append(violation)
        return violations

    async def _notify_violation(self, violation: LimitViolation) -> None:
        """通知违规

        Args:
            violation: 违规信息
        """
        if self._on_violation:
            try:
                self._on_violation(violation)
            except Exception as e:
                logger.error(f"Error in violation callback: {e}")

        if self._on_violation_async:
            try:
                result = self._on_violation_async(violation)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Error in async violation callback: {e}")

    @property
    def violation_count(self) -> int:
        """违规计数"""
        return self._violation_count

    def reset_violation_count(self) -> None:
        """重置违规计数"""
        self._violation_count = 0
