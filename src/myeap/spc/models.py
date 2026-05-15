"""SPC数据模型

定义SPC模块使用的数据类型，包括控制图类型、控制限、数据点等。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChartType(str, Enum):
    """控制图类型枚举

    支持的SPC控制图类型：
    - X_BAR_R: X-bar and R chart (组容量2-10)
    - X_BAR_S: X-bar and S chart (组容量>10)
    - X_MR: Individual and Moving Range (单值和移动极差)
    - C: C chart (缺陷数)
    - U: U chart (单位缺陷数)
    - P: P chart (不合格率)
    - NP: NP chart (不合格数)
    - EWMA: Exponentially Weighted Moving Average
    - CUSUM: Cumulative Sum
    """

    X_BAR_R = "x_bar_r"
    X_BAR_S = "x_bar_s"
    X_MR = "x_mr"
    C = "c"
    U = "u"
    P = "p"
    NP = "np"
    EWMA = "ewma"
    CUSUM = "cusum"

    @property
    def description(self) -> str:
        """获取控制图类型描述"""
        descriptions = {
            ChartType.X_BAR_R: "X-bar and R Chart (平均值与极差图)",
            ChartType.X_BAR_S: "X-bar and S Chart (平均值与标准差图)",
            ChartType.X_MR: "Individual and Moving Range (单值与移动极差图)",
            ChartType.C: "C Chart (缺陷数控制图)",
            ChartType.U: "U Chart (单位缺陷数控制图)",
            ChartType.P: "P Chart (不合格率控制图)",
            ChartType.NP: "NP Chart (不合格数控制图)",
            ChartType.EWMA: "EWMA Chart (指数加权移动平均图)",
            ChartType.CUSUM: "CUSUM Chart (累积和控制图)",
        }
        return descriptions.get(self, self.value)

    @property
    def is_variable_chart(self) -> bool:
        """是否为计量值控制图"""
        return self in (
            ChartType.X_BAR_R,
            ChartType.X_BAR_S,
            ChartType.X_MR,
            ChartType.EWMA,
            ChartType.CUSUM,
        )

    @property
    def is_attribute_chart(self) -> bool:
        """是否为计数值控制图"""
        return self in (
            ChartType.C,
            ChartType.U,
            ChartType.P,
            ChartType.NP,
        )

    @property
    def requires_group_size(self) -> bool:
        """是否需要组大小参数"""
        return self in (ChartType.X_BAR_R, ChartType.X_BAR_S)

    @property
    def default_group_size(self) -> int:
        """获取默认组大小"""
        if self == ChartType.X_BAR_R:
            return 5
        elif self == ChartType.X_BAR_S:
            return 10
        return 1


class ControlLimits(BaseModel):
    """控制限

    表示控制图的上控制限(UCL)、中心线(CL)和下控制限(LCL)。

    Attributes:
        ucl: 上控制限 (Upper Control Limit)
        cl: 中心线 (Center Line)
        lcl: 下控制限 (Lower Control Limit)
        ucl_secondary: 辅助上控制限 (如R图的UCL)
        lcl_secondary: 辅助下控制限 (如R图的LCL)
        warning_ucl: 警告上限 (2σ区域)
        warning_lcl: 警告下限 (2σ区域)
    """

    ucl: float = Field(description="上控制限")
    cl: float = Field(description="中心线")
    lcl: float = Field(description="下控制限")
    ucl_secondary: Optional[float] = Field(
        default=None, description="辅助上控制限 (R图/S图)"
    )
    lcl_secondary: Optional[float] = Field(
        default=None, description="辅助下控制限 (R图/S图)"
    )
    warning_ucl: Optional[float] = Field(
        default=None, description="警告上限 (2σ)"
    )
    warning_lcl: Optional[float] = Field(
        default=None, description="警告下限 (2σ)"
    )

    @property
    def range(self) -> float:
        """控制限范围"""
        return self.ucl - self.lcl

    @property
    def sigma(self) -> float:
        """估计的sigma值 (基于控制限)"""
        return self.range / 6

    def is_within_limits(self, value: float) -> bool:
        """检查值是否在控制限内"""
        return self.lcl <= value <= self.ucl

    def is_within_warning(self, value: float) -> bool:
        """检查值是否在警告限内"""
        if self.warning_lcl is not None and self.warning_ucl is not None:
            return self.warning_lcl <= value <= self.warning_ucl
        return True

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "ucl": self.ucl,
            "cl": self.cl,
            "lcl": self.lcl,
            "ucl_secondary": self.ucl_secondary,
            "lcl_secondary": self.lcl_secondary,
            "warning_ucl": self.warning_ucl,
            "warning_lcl": self.warning_lcl,
        }


class DataPoint(BaseModel):
    """SPC数据点

    表示一个采集到的工艺参数数据点。

    Attributes:
        value: 参数值
        timestamp: 采集时间戳
        group_id: 组ID (用于X-bar图表)
        quality: 数据质量 (normal, suspect, invalid)
    """

    value: float = Field(description="参数值")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="采集时间戳"
    )
    group_id: Optional[str] = Field(
        default=None, description="组ID (用于X-bar图表)"
    )
    quality: str = Field(
        default="normal",
        description="数据质量: normal, suspect, invalid"
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "group_id": self.group_id,
            "quality": self.quality,
        }


class ChartPoint(BaseModel):
    """控制图数据点

    包含数据点及其在控制图中的位置信息。

    Attributes:
        index: 数据点索引
        value: 参数值
        timestamp: 采集时间
        group_id: 组ID
        is_violation: 是否违反SPC规则
        violations: 违反的规则列表
        in_control: 是否在控制限内
    """

    index: int = Field(description="数据点索引")
    value: float = Field(description="参数值")
    timestamp: datetime = Field(description="采集时间")
    group_id: Optional[str] = Field(default=None, description="组ID")
    is_violation: bool = Field(default=False, description="是否违反SPC规则")
    violations: List[str] = Field(
        default_factory=list, description="违反的规则列表"
    )
    in_control: bool = Field(default=True, description="是否在控制限内")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "index": self.index,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "group_id": self.group_id,
            "is_violation": self.is_violation,
            "violations": self.violations,
            "in_control": self.in_control,
        }


class ChartStatistics(BaseModel):
    """控制图统计信息

    记录控制图的统计指标。

    Attributes:
        mean: 平均值
        std: 标准差
        min: 最小值
        max: 最大值
        range: 极差
        median: 中位数
        sample_count: 样本数量
        violation_count: 违规次数
        update_time: 更新时间
    """

    mean: float = Field(description="平均值")
    std: float = Field(description="标准差")
    min: float = Field(description="最小值")
    max: float = Field(description="最大值")
    range: float = Field(description="极差")
    median: float = Field(description="中位数")
    sample_count: int = Field(description="样本数量")
    violation_count: int = Field(description="违规次数")
    update_time: datetime = Field(
        default_factory=datetime.now, description="更新时间"
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "mean": self.mean,
            "std": self.std,
            "min": self.min,
            "max": self.max,
            "range": self.range,
            "median": self.median,
            "sample_count": self.sample_count,
            "violation_count": self.violation_count,
            "update_time": self.update_time.isoformat(),
        }
