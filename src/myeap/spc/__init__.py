"""SPC (Statistical Process Control) 模块

统计过程控制引擎，负责工艺数据分析和控制图绘制。

主要功能：
- 多种控制图类型支持 (X-bar R, X-bar S, X-MR, C, U, P, NP, EWMA, CUSUM)
- SPC规则检查 (Westgard规则)
- 过程能力分析 (Cp, Cpk, Pp, Ppk)
- 实时数据监控和报警

Example:
    >>> from myeap.spc import SPCEngine, ChartType
    >>> engine = SPCEngine()
    >>> chart = engine.create_chart("temp_chart", ChartType.X_BAR_R)
    >>> violations = engine.add_data_point("temp_chart", 25.5, datetime.now())
"""

from myeap.spc.models import (
    ChartType,
    ControlLimits,
    DataPoint,
    ChartPoint,
)
from myeap.spc.rules import (
    SPCRule,
    SPCViolation,
    Severity,
    check_spc_rules,
)
from myeap.spc.charts import (
    ControlChart,
    calculate_x_bar_r_limits,
    calculate_x_bar_s_limits,
    calculate_x_mr_limits,
    calculate_c_limits,
    calculate_u_limits,
    calculate_p_limits,
    calculate_np_limits,
    calculate_ewma_limits,
    calculate_cusum_limits,
)
from myeap.spc.capability import (
    ProcessCapability,
    calculate_capability,
    calculate_pp_apk,
)
from myeap.spc.engine import SPCEngine

__all__ = [
    # Models
    "ChartType",
    "ControlLimits",
    "DataPoint",
    "ChartPoint",
    # Rules
    "SPCRule",
    "SPCViolation",
    "Severity",
    "check_spc_rules",
    # Charts
    "ControlChart",
    "calculate_x_bar_r_limits",
    "calculate_x_bar_s_limits",
    "calculate_x_mr_limits",
    "calculate_c_limits",
    "calculate_u_limits",
    "calculate_p_limits",
    "calculate_np_limits",
    "calculate_ewma_limits",
    "calculate_cusum_limits",
    # Capability
    "ProcessCapability",
    "calculate_capability",
    "calculate_pp_apk",
    # Engine
    "SPCEngine",
]

__version__ = "1.0.0"
