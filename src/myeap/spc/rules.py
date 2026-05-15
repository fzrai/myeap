"""SPC规则定义

实现Westgard规则等SPC规则检查逻辑。
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class SPCRule(str, Enum):
    """SPC规则枚举

    基于Westgard规则的SPC判定规则：
    - RULE_1: 1点落在3σ区域外 (基础规则)
    - RULE_2: 连续9点在中心线同一侧
    - RULE_3: 连续6点递增或递减
    - RULE_4: 连续14点交替上下
    - RULE_5: 连续3点中有2点落在2σ区域外
    - RULE_6: 连续5点中有4点落在1σ区域外
    - RULE_7: 连续15点落在1σ区域内
    - RULE_8: 连续8点落在1σ区域外
    """

    RULE_1 = "rule_1"  # 1点落在3σ区域外
    RULE_2 = "rule_2"  # 连续9点在中心线同一侧
    RULE_3 = "rule_3"  # 连续6点递增或递减
    RULE_4 = "rule_4"  # 连续14点交替上下
    RULE_5 = "rule_5"  # 连续3点中有2点落在2σ区域外
    RULE_6 = "rule_6"  # 连续5点中有4点落在1σ区域外
    RULE_7 = "rule_7"  # 连续15点落在1σ区域内
    RULE_8 = "rule_8"  # 连续8点落在1σ区域外

    @property
    def description(self) -> str:
        """获取规则描述"""
        descriptions = {
            SPCRule.RULE_1: "1点落在3σ控制限外",
            SPCRule.RULE_2: "连续9点在中心线同一侧",
            SPCRule.RULE_3: "连续6点单调递增或递减",
            SPCRule.RULE_4: "连续14点交替上下",
            SPCRule.RULE_5: "连续3点中有2点落在2σ区域外",
            SPCRule.RULE_6: "连续5点中有4点落在1σ区域外",
            SPCRule.RULE_7: "连续15点落在1σ区域内",
            SPCRule.RULE_8: "连续8点落在1σ区域外",
        }
        return descriptions.get(self, self.value)

    @property
    def minimum_points(self) -> int:
        """规则检查所需的最少点数"""
        rule_points = {
            SPCRule.RULE_1: 1,
            SPCRule.RULE_2: 9,
            SPCRule.RULE_3: 6,
            SPCRule.RULE_4: 14,
            SPCRule.RULE_5: 3,
            SPCRule.RULE_6: 5,
            SPCRule.RULE_7: 15,
            SPCRule.RULE_8: 8,
        }
        return rule_points.get(self, 1)


class Severity(str, Enum):
    """SPC违规严重程度"""

    CRITICAL = "critical"  # 严重 - 立即处理
    MAJOR = "major"  # 主要 - 需要关注
    MINOR = "minor"  # 次要 - 轻微异常

    @property
    def priority(self) -> int:
        """获取优先级数值，数值越小优先级越高"""
        priority_map = {
            Severity.CRITICAL: 1,
            Severity.MAJOR: 2,
            Severity.MINOR: 3,
        }
        return priority_map[self]


# 规则与严重程度映射
RULE_SEVERITY_MAP = {
    SPCRule.RULE_1: Severity.CRITICAL,  # 超出控制限
    SPCRule.RULE_2: Severity.MAJOR,
    SPCRule.RULE_3: Severity.MAJOR,  # 趋势
    SPCRule.RULE_4: Severity.MINOR,  # 交替
    SPCRule.RULE_5: Severity.MAJOR,  # 2σ外
    SPCRule.RULE_6: Severity.MINOR,  # 1σ外
    SPCRule.RULE_7: Severity.MINOR,  # 过于集中
    SPCRule.RULE_8: Severity.MINOR,  # 过于分散
}


class SPCViolation(BaseModel):
    """SPC违规记录

    表示检测到的一个SPC规则违反。

    Attributes:
        rule: 违反的规则
        data_index: 数据点索引
        value: 数据值
        expected_range: 期望范围 (控制限)
        severity: 严重程度
        message: 违规描述
        timestamp: 检测时间
    """

    rule: SPCRule = Field(description="违反的规则")
    data_index: int = Field(description="数据点索引")
    value: float = Field(description="数据值")
    expected_range: Tuple[float, float] = Field(
        description="期望范围 (lcl, ucl)"
    )
    severity: Severity = Field(description="严重程度")
    message: str = Field(default="", description="违规描述")
    timestamp: Optional[Any] = Field(
        default=None, description="检测时间"
    )

    def __init__(self, **data):
        if "severity" not in data:
            rule = data.get("rule")
            if rule:
                data["severity"] = RULE_SEVERITY_MAP.get(rule, Severity.MINOR)
        if "message" not in data or not data["message"]:
            rule = data.get("rule")
            value = data.get("value")
            lcl, ucl = data.get("expected_range", (0, 0))
            data["message"] = (
                f"Rule {rule.value}: value {value:.4f} outside limits "
                f"[{lcl:.4f}, {ucl:.4f}]"
            )
        super().__init__(**data)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "rule": self.rule.value,
            "rule_description": self.rule.description,
            "data_index": self.data_index,
            "value": self.value,
            "expected_range": list(self.expected_range),
            "severity": self.severity.value,
            "message": self.message,
        }

    def __repr__(self) -> str:
        return f"SPCViolation(rule={self.rule.value}, index={self.data_index}, value={self.value:.4f})"


def _check_rule_1(
    data: List[float],
    limits: Any,
) -> List[SPCViolation]:
    """Rule 1: 1点落在3σ区域外"""
    violations = []
    for i, value in enumerate(data):
        if value > limits.ucl or value < limits.lcl:
            violations.append(SPCViolation(
                rule=SPCRule.RULE_1,
                data_index=i,
                value=value,
                expected_range=(limits.lcl, limits.ucl),
            ))
    return violations


def _check_rule_2(
    data: List[float],
    limits: Any,
    n: int = 9,
) -> List[SPCViolation]:
    """Rule 2: 连续n点在中心线同一侧"""
    violations = []
    for i in range(len(data) - n + 1):
        window = data[i:i+n]
        if all(x > limits.cl for x in window) or all(x < limits.cl for x in window):
            violations.append(SPCViolation(
                rule=SPCRule.RULE_2,
                data_index=i,
                value=window[0],
                expected_range=(limits.lcl, limits.ucl),
            ))
    return violations


def _check_rule_3(
    data: List[float],
    limits: Any,
    n: int = 6,
) -> List[SPCViolation]:
    """Rule 3: 连续n点递增或递减"""
    violations = []
    for i in range(len(data) - n + 1):
        window = data[i:i+n]
        # 检查递增
        if all(window[j] < window[j+1] for j in range(n-1)):
            violations.append(SPCViolation(
                rule=SPCRule.RULE_3,
                data_index=i,
                value=window[0],
                expected_range=(limits.lcl, limits.ucl),
            ))
        # 检查递减
        elif all(window[j] > window[j+1] for j in range(n-1)):
            violations.append(SPCViolation(
                rule=SPCRule.RULE_3,
                data_index=i,
                value=window[0],
                expected_range=(limits.lcl, limits.ucl),
            ))
    return violations


def _check_rule_4(
    data: List[float],
    limits: Any,
    n: int = 14,
) -> List[SPCViolation]:
    """Rule 4: 连续n点交替上下"""
    violations = []
    for i in range(len(data) - n + 1):
        window = data[i:i+n]
        cl = limits.cl
        # 检查交替
        alternating = all(
            (window[j] - cl) * (window[j+1] - cl) < 0
            for j in range(n - 1)
        )
        if alternating:
            violations.append(SPCViolation(
                rule=SPCRule.RULE_4,
                data_index=i,
                value=window[0],
                expected_range=(limits.lcl, limits.ucl),
            ))
    return violations


def _check_rule_5(
    data: List[float],
    limits: Any,
    n: int = 3,
) -> List[SPCViolation]:
    """Rule 5: 连续n点中有2点落在2σ区域外"""
    violations = []
    sigma = limits.sigma if hasattr(limits, 'sigma') else (limits.ucl - limits.lcl) / 6
    warning_ucl = limits.cl + 2 * sigma
    warning_lcl = limits.cl - 2 * sigma

    for i in range(len(data) - n + 1):
        window = data[i:i+n]
        outside_2sigma = sum(
            1 for x in window if x > warning_ucl or x < warning_lcl
        )
        if outside_2sigma >= 2:
            violations.append(SPCViolation(
                rule=SPCRule.RULE_5,
                data_index=i,
                value=window[0],
                expected_range=(limits.lcl, limits.ucl),
            ))
    return violations


def _check_rule_6(
    data: List[float],
    limits: Any,
    n: int = 5,
) -> List[SPCViolation]:
    """Rule 6: 连续n点中有4点落在1σ区域外"""
    violations = []
    sigma = limits.sigma if hasattr(limits, 'sigma') else (limits.ucl - limits.lcl) / 6
    warning_ucl = limits.cl + sigma
    warning_lcl = limits.cl - sigma

    for i in range(len(data) - n + 1):
        window = data[i:i+n]
        outside_1sigma = sum(
            1 for x in window if x > warning_ucl or x < warning_lcl
        )
        if outside_1sigma >= 4:
            violations.append(SPCViolation(
                rule=SPCRule.RULE_6,
                data_index=i,
                value=window[0],
                expected_range=(limits.lcl, limits.ucl),
            ))
    return violations


def _check_rule_7(
    data: List[float],
    limits: Any,
    n: int = 15,
) -> List[SPCViolation]:
    """Rule 7: 连续n点落在1σ区域内 (过于集中)"""
    violations = []
    sigma = limits.sigma if hasattr(limits, 'sigma') else (limits.ucl - limits.lcl) / 6
    inner_ucl = limits.cl + sigma
    inner_lcl = limits.cl - sigma

    for i in range(len(data) - n + 1):
        window = data[i:i+n]
        if all(inner_lcl <= x <= inner_ucl for x in window):
            violations.append(SPCViolation(
                rule=SPCRule.RULE_7,
                data_index=i,
                value=window[0],
                expected_range=(limits.lcl, limits.ucl),
            ))
    return violations


def _check_rule_8(
    data: List[float],
    limits: Any,
    n: int = 8,
) -> List[SPCViolation]:
    """Rule 8: 连续n点落在1σ区域外 (过于分散)"""
    violations = []
    sigma = limits.sigma if hasattr(limits, 'sigma') else (limits.ucl - limits.lcl) / 6
    inner_ucl = limits.cl + sigma
    inner_lcl = limits.cl - sigma

    for i in range(len(data) - n + 1):
        window = data[i:i+n]
        outside_1sigma = sum(
            1 for x in window if x < inner_lcl or x > inner_ucl
        )
        if outside_1sigma >= n:
            violations.append(SPCViolation(
                rule=SPCRule.RULE_8,
                data_index=i,
                value=window[0],
                expected_range=(limits.lcl, limits.ucl),
            ))
    return violations


def check_spc_rules(
    data: List[float],
    limits: Any,
    rules: Optional[List[SPCRule]] = None,
) -> List[SPCViolation]:
    """检查SPC规则

    Args:
        data: 数据列表
        limits: 控制限对象
        rules: 要检查的规则列表，None表示检查所有规则

    Returns:
        违规列表
    """
    if len(data) == 0:
        return []

    if rules is None:
        rules = list(SPCRule)

    violations = []

    for rule in rules:
        if rule == SPCRule.RULE_1:
            violations.extend(_check_rule_1(data, limits))
        elif rule == SPCRule.RULE_2:
            if len(data) >= rule.minimum_points:
                violations.extend(_check_rule_2(data, limits))
        elif rule == SPCRule.RULE_3:
            if len(data) >= rule.minimum_points:
                violations.extend(_check_rule_3(data, limits))
        elif rule == SPCRule.RULE_4:
            if len(data) >= rule.minimum_points:
                violations.extend(_check_rule_4(data, limits))
        elif rule == SPCRule.RULE_5:
            if len(data) >= rule.minimum_points:
                violations.extend(_check_rule_5(data, limits))
        elif rule == SPCRule.RULE_6:
            if len(data) >= rule.minimum_points:
                violations.extend(_check_rule_6(data, limits))
        elif rule == SPCRule.RULE_7:
            if len(data) >= rule.minimum_points:
                violations.extend(_check_rule_7(data, limits))
        elif rule == SPCRule.RULE_8:
            if len(data) >= rule.minimum_points:
                violations.extend(_check_rule_8(data, limits))

    # 去重 (同一索引可能违反多个规则)
    seen = set()
    unique_violations = []
    for v in violations:
        key = (v.rule, v.data_index)
        if key not in seen:
            seen.add(key)
            unique_violations.append(v)

    return unique_violations


def get_default_rules() -> List[SPCRule]:
    """获取默认的SPC规则列表 (Westgard基本规则)"""
    return [
        SPCRule.RULE_1,
        SPCRule.RULE_2,
        SPCRule.RULE_3,
    ]
