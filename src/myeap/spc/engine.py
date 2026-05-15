"""SPC引擎

统计过程控制引擎，负责管理控制图、处理数据和触发报警。
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union

from myeap.spc.capability import ProcessCapability, calculate_capability
from myeap.spc.charts import ControlChart, _calculate_limits
from myeap.spc.models import ChartStatistics, ChartType, ControlLimits, DataPoint
from myeap.spc.rules import SPCRule, SPCViolation, get_default_rules


class SPCEngine:
    """SPC引擎

    统计过程控制引擎，管理多个控制图，处理数据流并检测异常。

    Example:
        >>> engine = SPCEngine()
        >>> chart = engine.create_chart("temp_01", ChartType.X_MR)
        >>> violations = engine.add_data_point("temp_01", 25.5, datetime.now())
        >>> if violations:
        ...     print(f"检测到 {len(violations)} 个违规")
    """

    def __init__(
        self,
        on_violation: Optional[Callable[[SPCViolation], None]] = None,
        on_limit_update: Optional[Callable[[str, ControlLimits], None]] = None,
    ):
        """初始化SPC引擎

        Args:
            on_violation: 违规回调函数
            on_limit_update: 限值更新回调函数
        """
        self._charts: Dict[str, ControlChart] = {}
        self._rules: List[SPCRule] = get_default_rules()
        self._on_violation = on_violation
        self._on_limit_update = on_limit_update

    @property
    def charts(self) -> Dict[str, ControlChart]:
        """获取所有控制图"""
        return self._charts.copy()

    @property
    def rules(self) -> List[SPCRule]:
        """获取当前启用的SPC规则"""
        return self._rules.copy()

    def set_rules(self, rules: List[SPCRule]) -> None:
        """设置SPC规则

        Args:
            rules: 要启用的规则列表
        """
        self._rules = rules.copy()

    def add_rule(self, rule: SPCRule) -> None:
        """添加SPC规则

        Args:
            rule: 要添加的规则
        """
        if rule not in self._rules:
            self._rules.append(rule)

    def remove_rule(self, rule: SPCRule) -> None:
        """移除SPC规则

        Args:
            rule: 要移除的规则
        """
        if rule in self._rules:
            self._rules.remove(rule)

    def create_chart(
        self,
        chart_id: str,
        chart_type: ChartType,
        name: Optional[str] = None,
        control_limits: Optional[ControlLimits] = None,
        auto_update_limits: bool = True,
        min_samples: int = 20,
    ) -> ControlChart:
        """创建控制图

        Args:
            chart_id: 控制图唯一标识
            chart_type: 控制图类型
            name: 控制图名称 (可选)
            control_limits: 预设控制限 (可选)
            auto_update_limits: 是否自动更新限值
            min_samples: 计算限值所需的最少样本数

        Returns:
            创建的ControlChart对象

        Raises:
            ValueError: 如果chart_id已存在
        """
        if chart_id in self._charts:
            raise ValueError(f"Chart with id '{chart_id}' already exists")

        chart = ControlChart(
            chart_id=chart_id,
            chart_type=chart_type,
            name=name,
            control_limits=control_limits,
            auto_update_limits=auto_update_limits,
            min_samples=min_samples,
        )
        self._charts[chart_id] = chart
        return chart

    def get_chart(self, chart_id: str) -> Optional[ControlChart]:
        """获取控制图

        Args:
            chart_id: 控制图ID

        Returns:
            控制图对象，如果不存在返回None
        """
        return self._charts.get(chart_id)

    def delete_chart(self, chart_id: str) -> bool:
        """删除控制图

        Args:
            chart_id: 控制图ID

        Returns:
            是否成功删除
        """
        if chart_id in self._charts:
            del self._charts[chart_id]
            return True
        return False

    def add_data_point(
        self,
        chart_id: str,
        value: float,
        timestamp: Optional[datetime] = None,
        group_id: Optional[str] = None,
        quality: str = "normal",
    ) -> List[SPCViolation]:
        """添加数据点并检查规则

        Args:
            chart_id: 控制图ID
            value: 数据值
            timestamp: 时间戳 (默认当前时间)
            group_id: 组ID (用于X-bar图表)
            quality: 数据质量 (normal, suspect, invalid)

        Returns:
            违规列表

        Raises:
            ValueError: 如果chart_id不存在
        """
        chart = self._charts.get(chart_id)
        if not chart:
            raise ValueError(f"Chart '{chart_id}' not found")

        # 添加数据点
        chart.add_point(value, timestamp, group_id, quality)

        # 自动更新限值
        if chart.auto_update_limits and len(chart.data) >= chart.min_samples:
            if chart._update_count == 0 or len(chart.data) % 10 == 0:
                chart.update_limits()
                if chart.control_limits and self._on_limit_update:
                    self._on_limit_update(chart_id, chart.control_limits)

        # 检查SPC规则
        violations = chart.check_rules(self._rules)

        # 触发回调
        if violations and self._on_violation:
            self._on_violation(violations[0])

        return violations

    def add_batch(
        self,
        chart_id: str,
        data: List[float],
        timestamps: Optional[List[datetime]] = None,
    ) -> List[SPCViolation]:
        """批量添加数据点

        Args:
            chart_id: 控制图ID
            data: 数据值列表
            timestamps: 时间戳列表 (与data对应)

        Returns:
            所有违规列表
        """
        all_violations = []
        timestamps = timestamps or [None] * len(data)

        for value, timestamp in zip(data, timestamps):
            violations = self.add_data_point(chart_id, value, timestamp)
            all_violations.extend(violations)

        return all_violations

    def calculate_capability(
        self,
        chart_id: str,
        usl: float,
        lsl: float,
        target: Optional[float] = None,
    ) -> ProcessCapability:
        """计算过程能力

        Args:
            chart_id: 控制图ID
            usl: 规格上限
            lsl: 规格下限
            target: 目标值 (可选)

        Returns:
            过程能力分析结果

        Raises:
            ValueError: 如果chart_id不存在或数据不足
        """
        chart = self._charts.get(chart_id)
        if not chart:
            raise ValueError(f"Chart '{chart_id}' not found")

        if len(chart.data) < 2:
            raise ValueError("需要至少2个数据点来计算过程能力")

        return calculate_capability(chart.data, usl, lsl, target)

    def get_chart_statistics(self, chart_id: str) -> Optional[ChartStatistics]:
        """获取控制图统计信息

        Args:
            chart_id: 控制图ID

        Returns:
            统计信息，如果不存在返回None
        """
        chart = self._charts.get(chart_id)
        if chart:
            return chart.statistics
        return None

    def get_violations(
        self,
        chart_id: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> List[SPCViolation]:
        """获取违规记录

        Args:
            chart_id: 控制图ID (可选，None表示所有图表)
            severity: 严重程度过滤 (可选)

        Returns:
            违规列表
        """
        violations = []

        if chart_id:
            chart = self._charts.get(chart_id)
            if chart:
                violations = [
                    SPCViolation(
                        rule=SPCRule(v.rule.value),
                        data_index=p.index,
                        value=p.value,
                        expected_range=(
                            chart.control_limits.lcl,
                            chart.control_limits.ucl,
                        ) if chart.control_limits else (0, 0),
                        severity=severity or "minor",
                    )
                    for p in chart.points
                    if p.is_violation
                ]
        else:
            for chart in self._charts.values():
                for p in chart.points:
                    if p.is_violation:
                        violations.append(
                            SPCViolation(
                                rule=SPCRule(p.violations[0]) if p.violations else SPCRule.RULE_1,
                                data_index=p.index,
                                value=p.value,
                                expected_range=(
                                    chart.control_limits.lcl,
                                    chart.control_limits.ucl,
                                ) if chart.control_limits else (0, 0),
                                severity=severity or "minor",
                            )
                        )

        return violations

    def get_summary(self) -> Dict[str, Any]:
        """获取引擎摘要

        Returns:
            包含所有控制图状态的字典
        """
        return {
            "total_charts": len(self._charts),
            "active_rules": [r.value for r in self._rules],
            "charts": {
                chart_id: {
                    "type": chart.chart_type.value,
                    "name": chart.name,
                    "point_count": len(chart.data),
                    "violation_count": sum(1 for p in chart.data if p.is_violation),
                    "is_ready": chart.is_ready,
                    "has_limits": chart.control_limits is not None,
                }
                for chart_id, chart in self._charts.items()
            },
        }

    def reset_chart(self, chart_id: str) -> bool:
        """重置控制图

        Args:
            chart_id: 控制图ID

        Returns:
            是否成功重置
        """
        chart = self._charts.get(chart_id)
        if chart:
            chart.reset()
            return True
        return False

    def export_chart_data(
        self,
        chart_id: str,
        format: str = "dict",
    ) -> Any:
        """导出控制图数据

        Args:
            chart_id: 控制图ID
            format: 输出格式 ("dict", "list")

        Returns:
            导出的数据
        """
        chart = self._charts.get(chart_id)
        if not chart:
            raise ValueError(f"Chart '{chart_id}' not found")

        if format == "list":
            return [p.to_dict() for p in chart.points]
        else:
            return chart.to_dict()

    def __repr__(self) -> str:
        return f"SPCEngine(charts={len(self._charts)}, rules={len(self._rules)})"


class AsyncSPCEngine(SPCEngine):
    """异步SPC引擎

    支持异步回调的SPC引擎版本。
    """

    def __init__(
        self,
        on_violation: Optional[Callable[[SPCViolation], None]] = None,
        on_limit_update: Optional[Callable[[str, ControlLimits], None]] = None,
    ):
        super().__init__(on_violation, on_limit_update)

    async def add_data_point_async(
        self,
        chart_id: str,
        value: float,
        timestamp: Optional[datetime] = None,
        group_id: Optional[str] = None,
        quality: str = "normal",
    ) -> List[SPCViolation]:
        """异步添加数据点

        Args:
            chart_id: 控制图ID
            value: 数据值
            timestamp: 时间戳
            group_id: 组ID
            quality: 数据质量

        Returns:
            违规列表
        """
        chart = self._charts.get(chart_id)
        if not chart:
            raise ValueError(f"Chart '{chart_id}' not found")

        chart.add_point(value, timestamp, group_id, quality)

        if chart.auto_update_limits and len(chart.data) >= chart.min_samples:
            if chart._update_count == 0 or len(chart.data) % 10 == 0:
                chart.update_limits()
                if chart.control_limits and self._on_limit_update:
                    if asyncio.iscoroutinefunction(self._on_limit_update):
                        await self._on_limit_update(chart_id, chart.control_limits)
                    else:
                        self._on_limit_update(chart_id, chart.control_limits)

        violations = chart.check_rules(self._rules)

        if violations and self._on_violation:
            callback = self._on_violation
            if asyncio.iscoroutinefunction(callback):
                await callback(violations[0])
            else:
                callback(violations[0])

        return violations

    def add_data_point(
        self,
        chart_id: str,
        value: float,
        timestamp: Optional[datetime] = None,
        group_id: Optional[str] = None,
        quality: str = "normal",
    ) -> List[SPCViolation]:
        """添加数据点 (同步版本)

        自动检测回调类型并选择合适的处理方式。
        """
        chart = self._charts.get(chart_id)
        if not chart:
            raise ValueError(f"Chart '{chart_id}' not found")

        chart.add_point(value, timestamp, group_id, quality)

        if chart.auto_update_limits and len(chart.data) >= chart.min_samples:
            if chart._update_count == 0 or len(chart.data) % 10 == 0:
                chart.update_limits()
                if chart.control_limits and self._on_limit_update:
                    self._on_limit_update(chart_id, chart.control_limits)

        violations = chart.check_rules(self._rules)

        if violations and self._on_violation:
            self._on_violation(violations[0])

        return violations
