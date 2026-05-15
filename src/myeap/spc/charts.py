"""控制图实现

实现各种类型的SPC控制图及其限值计算。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from pydantic import BaseModel, Field

from myeap.spc.models import ChartPoint, ChartStatistics, ChartType, ControlLimits
from myeap.spc.rules import SPCRule, SPCViolation, check_spc_rules


# SPC控制图系数表
# 来源: AIAG SPC手册
_SPC_COEFFICIENTS = {
    # n: (A2, d2, D3, D4, d3)
    2: (0.880, 1.128, 0.000, 3.267, 0.853),
    3: (0.740, 1.693, 0.000, 2.575, 0.888),
    4: (0.577, 2.059, 0.000, 2.282, 0.880),
    5: (0.483, 2.326, 0.000, 2.115, 0.864),
    6: (0.419, 2.534, 0.000, 2.004, 0.848),
    7: (0.373, 2.704, 0.000, 1.924, 0.833),
    8: (0.337, 2.847, 0.000, 1.864, 0.820),
    9: (0.308, 2.970, 0.000, 1.816, 0.808),
    10: (0.283, 3.078, 0.000, 1.777, 0.797),
    11: (0.262, 3.173, 0.076, 1.744, 0.787),
    12: (0.243, 3.258, 0.076, 1.716, 0.778),
    13: (0.228, 3.336, 0.076, 1.693, 0.770),
    14: (0.214, 3.407, 0.076, 1.672, 0.763),
    15: (0.202, 3.472, 0.076, 1.653, 0.756),
    16: (0.191, 3.532, 0.076, 1.637, 0.750),
    17: (0.182, 3.588, 0.076, 1.622, 0.744),
    18: (0.174, 3.640, 0.076, 1.608, 0.739),
    19: (0.166, 3.689, 0.076, 1.596, 0.734),
    20: (0.159, 3.735, 0.076, 1.585, 0.729),
}


def _get_coefficients(n: int) -> Tuple[float, float, float, float, float]:
    """获取指定组大小的SPC系数"""
    if n < 2:
        n = 2
    elif n > 20:
        n = 20
    return _SPC_COEFFICIENTS[n]


def _get_A2(n: int) -> float:
    """获取A2系数"""
    return _get_coefficients(n)[0]


def _get_d2(n: int) -> float:
    """获取d2系数"""
    return _get_coefficients(n)[1]


def _get_D3_D4(n: int) -> Tuple[float, float]:
    """获取D3和D4系数"""
    return _get_coefficients(n)[2], _get_coefficients(n)[3]


def _get_c4(n: int) -> float:
    """获取c4系数 (用于无偏估计sigma)"""
    if n <= 25:
        c4_values = {
            2: 0.7979, 3: 0.8862, 4: 0.9213, 5: 0.9400,
            6: 0.9515, 7: 0.9594, 8: 0.9650, 9: 0.9693,
            10: 0.9727, 11: 0.9754, 12: 0.9776, 13: 0.9794,
            14: 0.9810, 15: 0.9823, 16: 0.9835, 17: 0.9845,
            18: 0.9854, 19: 0.9862, 20: 0.9869, 21: 0.9876,
            22: 0.9882, 23: 0.9887, 24: 0.9892, 25: 0.9896,
        }
        return c4_values.get(n, 0.9896)
    else:
        # 大样本近似
        return 1 - 1 / (4 * n)


def calculate_x_bar_r_limits(
    data: np.ndarray,
    sigma_multiplier: float = 3.0,
) -> ControlLimits:
    """计算X-bar R图的限值

    Args:
        data: 二维数组，每行是一组数据
        sigma_multiplier: sigma倍乘因子 (默认3)

    Returns:
        X-bar图的ControlLimits对象 (包含R图的辅助限)

    计算公式:
        X-bar图:
            UCL = X_bar_bar + A2 * R_bar
            CL = X_bar_bar
            LCL = X_bar_bar - A2 * R_bar

        R图:
            UCL_R = D4 * R_bar
            CL_R = R_bar
            LCL_R = D3 * R_bar
    """
    x_bar = np.mean(data, axis=1)  # 每组的平均值
    r = np.ptp(data, axis=1)  # 每组的极差 (max - min)

    x_bar_bar = np.mean(x_bar)  # 总平均
    r_bar = np.mean(r)  # 平均极差

    n = data.shape[1]  # 组大小
    A2 = _get_A2(n)
    D3, D4 = _get_D3_D4(n)

    # X-bar图限值
    ucl_x = x_bar_bar + A2 * r_bar
    lcl_x = x_bar_bar - A2 * r_bar

    # R图限值
    ucl_r = D4 * r_bar
    lcl_r = max(0, D3 * r_bar)

    # 计算警告限 (2σ)
    sigma = r_bar / _get_d2(n)
    warning_ucl = x_bar_bar + 2 * sigma
    warning_lcl = x_bar_bar - 2 * sigma

    return ControlLimits(
        ucl=float(ucl_x),
        cl=float(x_bar_bar),
        lcl=float(lcl_x),
        ucl_secondary=float(ucl_r),
        lcl_secondary=float(lcl_r),
        warning_ucl=float(warning_ucl),
        warning_lcl=float(warning_lcl),
    )


def calculate_x_bar_s_limits(
    data: np.ndarray,
    sigma_multiplier: float = 3.0,
) -> ControlLimits:
    """计算X-bar S图的限值

    适用于组容量大于10的情况。

    Args:
        data: 二维数组，每行是一组数据
        sigma_multiplier: sigma倍乘因子 (默认3)

    Returns:
        X-bar图的ControlLimits对象 (包含S图的辅助限)

    计算公式:
        X-bar图:
            UCL = X_bar_bar + A3 * S_bar
            CL = X_bar_bar
            LCL = X_bar_bar - A3 * S_bar

        S图:
            UCL_S = B4 * S_bar
            CL_S = S_bar
            LCL_S = B3 * S_bar
    """
    x_bar = np.mean(data, axis=1)  # 每组的平均值
    s = np.std(data, axis=1, ddof=1)  # 每组的标准差

    x_bar_bar = np.mean(x_bar)  # 总平均
    s_bar = np.mean(s)  # 平均标准差

    n = data.shape[1]  # 组大小
    c4 = _get_c4(n)
    sigma = s_bar / c4  # 无偏估计sigma

    # X-bar图系数 A3 = 3 / (c4 * sqrt(n))
    A3 = sigma_multiplier / (c4 * np.sqrt(n))

    # S图系数 B3, B4
    B3 = max(0, 1 - 3 * np.sqrt(1 - c4**2) / c4)
    B4 = 1 + 3 * np.sqrt(1 - c4**2) / c4

    # X-bar图限值
    ucl_x = x_bar_bar + A3 * s_bar
    lcl_x = x_bar_bar - A3 * s_bar

    # S图限值
    ucl_s = B4 * s_bar
    lcl_s = max(0, B3 * s_bar)

    # 计算警告限 (2σ)
    warning_ucl = x_bar_bar + 2 * sigma
    warning_lcl = x_bar_bar - 2 * sigma

    return ControlLimits(
        ucl=float(ucl_x),
        cl=float(x_bar_bar),
        lcl=float(lcl_x),
        ucl_secondary=float(ucl_s),
        lcl_secondary=float(lcl_s),
        warning_ucl=float(warning_ucl),
        warning_lcl=float(warning_lcl),
    )


def calculate_x_mr_limits(
    data: np.ndarray,
    sigma_multiplier: float = 3.0,
) -> ControlLimits:
    """计算X-MR图的限值 (单值控制图)

    适用于单件检测或每次只取一个样本的情况。

    Args:
        data: 一维数组或可以展平为一维的数组
        sigma_multiplier: sigma倍乘因子 (默认3)

    Returns:
        X图的ControlLimits对象 (包含MR图的辅助限)

    计算公式:
        X图:
            UCL = X_bar + 3 * sigma
            CL = X_bar
            LCL = X_bar - 3 * sigma
            其中 sigma = MR_bar / d2

        MR图:
            UCL_MR = D4 * MR_bar
            CL_MR = MR_bar
            LCL_MR = 0
    """
    if data.ndim > 1:
        data = data.flatten()

    x_bar = np.mean(data)
    d2 = 1.128  # n=2时的系数

    # 计算移动极差 (相邻两点的差)
    mr = np.abs(np.diff(data))
    mr_bar = np.mean(mr)

    # 估计标准差
    sigma = mr_bar / d2

    # X图限值
    ucl_x = x_bar + sigma_multiplier * sigma
    lcl_x = x_bar - sigma_multiplier * sigma

    # MR图限值
    D4 = 3.267  # n=2时的D4
    ucl_mr = D4 * mr_bar
    lcl_mr = 0.0

    # 计算警告限 (2σ)
    warning_ucl = x_bar + 2 * sigma
    warning_lcl = x_bar - 2 * sigma

    return ControlLimits(
        ucl=float(ucl_x),
        cl=float(x_bar),
        lcl=float(lcl_x),
        ucl_secondary=float(ucl_mr),
        lcl_secondary=float(lcl_mr),
        warning_ucl=float(warning_ucl),
        warning_lcl=float(warning_lcl),
    )


def calculate_c_limits(
    data: np.ndarray,
    sigma_multiplier: float = 3.0,
) -> ControlLimits:
    """计算C图的限值 (缺陷数控制图)

    适用于样本大小固定的计数型数据。

    Args:
        data: 一维数组，包含每个样本的缺陷数
        sigma_multiplier: sigma倍乘因子 (默认3)

    Returns:
        ControlLimits对象

    计算公式:
        UCL = c_bar + 3 * sqrt(c_bar)
        CL = c_bar
        LCL = max(0, c_bar - 3 * sqrt(c_bar))
    """
    if data.ndim > 1:
        data = data.flatten()

    c_bar = np.mean(data)  # 平均缺陷数

    if c_bar <= 0:
        return ControlLimits(
            ucl=float(sigma_multiplier * 1),
            cl=0.0,
            lcl=0.0,
        )

    sigma_c = np.sqrt(c_bar)

    ucl = c_bar + sigma_multiplier * sigma_c
    lcl = max(0, c_bar - sigma_multiplier * sigma_c)

    # 警告限 (2σ)
    warning_ucl = c_bar + 2 * sigma_c
    warning_lcl = max(0, c_bar - 2 * sigma_c)

    return ControlLimits(
        ucl=float(ucl),
        cl=float(c_bar),
        lcl=float(lcl),
        warning_ucl=float(warning_ucl),
        warning_lcl=float(warning_lcl),
    )


def calculate_u_limits(
    data: np.ndarray,
    sample_sizes: Optional[np.ndarray] = None,
    sigma_multiplier: float = 3.0,
) -> ControlLimits:
    """计算U图的限值 (单位缺陷数控制图)

    适用于样本大小不固定的计数型数据。

    Args:
        data: 一维数组，包含每个样本的缺陷数
        sample_sizes: 样本大小数组，与data对应
        sigma_multiplier: sigma倍乘因子 (默认3)

    Returns:
        ControlLimits对象

    计算公式:
        u_bar = 总缺陷数 / 总检查单位数
        UCL = u_bar + 3 * sqrt(u_bar / n)
        CL = u_bar
        LCL = max(0, u_bar - 3 * sqrt(u_bar / n))
    """
    if data.ndim > 1:
        data = data.flatten()

    if sample_sizes is None:
        sample_sizes = np.ones_like(data)

    total_defects = np.sum(data)
    total_units = np.sum(sample_sizes)

    if total_units <= 0:
        return ControlLimits(ucl=1.0, cl=0.0, lcl=0.0)

    u_bar = total_defects / total_units
    avg_n = np.mean(sample_sizes)

    sigma_u = np.sqrt(u_bar / avg_n)

    ucl = u_bar + sigma_multiplier * sigma_u
    lcl = max(0, u_bar - sigma_multiplier * sigma_u)

    # 警告限 (2σ)
    warning_ucl = u_bar + 2 * sigma_u
    warning_lcl = max(0, u_bar - 2 * sigma_u)

    return ControlLimits(
        ucl=float(ucl),
        cl=float(u_bar),
        lcl=float(lcl),
        warning_ucl=float(warning_ucl),
        warning_lcl=float(warning_lcl),
    )


def calculate_p_limits(
    data: np.ndarray,
    sample_sizes: Optional[np.ndarray] = None,
    sigma_multiplier: float = 3.0,
) -> ControlLimits:
    """计算P图的限值 (不合格率控制图)

    适用于计数型数据的不合格率控制。

    Args:
        data: 一维数组，包含每个样本的不合格数或不合格率
        sample_sizes: 样本大小数组，与data对应
        sigma_multiplier: sigma倍乘因子 (默认3)

    Returns:
        ControlLimits对象

    计算公式:
        p_bar = 总不合格数 / 总检查数
        sigma_p = sqrt(p_bar * (1 - p_bar) / n)
        UCL = p_bar + 3 * sigma_p
        CL = p_bar
        LCL = max(0, p_bar - 3 * sigma_p)
    """
    if data.ndim > 1:
        data = data.flatten()

    if sample_sizes is None:
        sample_sizes = np.ones_like(data)

    total_defects = np.sum(data)
    total_samples = np.sum(sample_sizes)

    if total_samples <= 0:
        return ControlLimits(ucl=1.0, cl=0.0, lcl=0.0)

    p_bar = total_defects / total_samples

    if p_bar <= 0 or p_bar >= 1:
        return ControlLimits(
            ucl=min(1.0, p_bar + 0.1),
            cl=float(p_bar),
            lcl=max(0.0, p_bar - 0.1),
        )

    avg_n = np.mean(sample_sizes)
    sigma_p = np.sqrt(p_bar * (1 - p_bar) / avg_n)

    ucl = p_bar + sigma_multiplier * sigma_p
    lcl = max(0, p_bar - sigma_multiplier * sigma_p)

    # 警告限 (2σ)
    warning_ucl = p_bar + 2 * sigma_p
    warning_lcl = max(0, p_bar - 2 * sigma_p)

    return ControlLimits(
        ucl=float(ucl),
        cl=float(p_bar),
        lcl=float(lcl),
        warning_ucl=float(warning_ucl),
        warning_lcl=float(warning_lcl),
    )


def calculate_np_limits(
    data: np.ndarray,
    sample_size: int,
    sigma_multiplier: float = 3.0,
) -> ControlLimits:
    """计算NP图的限值 (不合格数控制图)

    适用于样本大小固定的计数型数据。

    Args:
        data: 一维数组，包含每个样本的不合格数
        sample_size: 固定样本大小
        sigma_multiplier: sigma倍乘因子 (默认3)

    Returns:
        ControlLimits对象

    计算公式:
        np_bar = 平均不合格数
        sigma_np = sqrt(np_bar * (1 - p_bar))
        UCL = np_bar + 3 * sigma_np
        CL = np_bar
        LCL = max(0, np_bar - 3 * sigma_np)
    """
    if data.ndim > 1:
        data = data.flatten()

    np_bar = np.mean(data)

    if sample_size <= 0:
        return ControlLimits(ucl=1.0, cl=0.0, lcl=0.0)

    p_bar = np_bar / sample_size
    sigma_np = np.sqrt(sample_size * p_bar * (1 - p_bar))

    ucl = np_bar + sigma_multiplier * sigma_np
    lcl = max(0, np_bar - sigma_multiplier * sigma_np)

    # 警告限 (2σ)
    warning_ucl = np_bar + 2 * sigma_np
    warning_lcl = max(0, np_bar - 2 * sigma_np)

    return ControlLimits(
        ucl=float(ucl),
        cl=float(np_bar),
        lcl=float(lcl),
        warning_ucl=float(warning_ucl),
        warning_lcl=float(warning_lcl),
    )


def calculate_ewma_limits(
    data: np.ndarray,
    lambda_: float = 0.2,
    sigma_multiplier: float = 3.0,
    target: Optional[float] = None,
) -> ControlLimits:
    """计算EWMA图的限值

    指数加权移动平均控制图，适用于检测过程的小偏移。

    Args:
        data: 一维数组
        lambda_: 平滑系数 (0 < lambda_ <= 1)，通常0.05-0.3
        sigma_multiplier: sigma倍乘因子 (通常使用3)
        target: 目标值，如果为None则使用数据均值

    Returns:
        ControlLimits对象

    计算公式:
        Z_0 = target 或 X_bar
        Z_i = lambda_ * X_i + (1 - lambda_) * Z_{i-1}
        sigma_Z = sigma * sqrt(lambda_ / (2 - lambda_))
        UCL = Z + sigma_multiplier * sigma_Z
        CL = target
        LCL = Z - sigma_multiplier * sigma_Z
    """
    if data.ndim > 1:
        data = data.flatten()

    n = len(data)
    if target is None:
        target = np.mean(data)

    sigma = np.std(data, ddof=1)

    if sigma <= 0 or lambda_ <= 0 or lambda_ > 1:
        return ControlLimits(
            ucl=float(target + sigma_multiplier),
            cl=float(target),
            lcl=float(target - sigma_multiplier),
        )

    # EWMA的标准差
    sigma_ewma = sigma * np.sqrt(lambda_ / (2 - lambda_))

    ucl = target + sigma_multiplier * sigma_ewma
    lcl = target - sigma_multiplier * sigma_ewma

    return ControlLimits(
        ucl=float(ucl),
        cl=float(target),
        lcl=float(lcl),
    )


def calculate_cusum_limits(
    data: np.ndarray,
    target: Optional[float] = None,
    k: float = 0.5,
    h: float = 5.0,
) -> ControlLimits:
    """计算CUSUM图的限值

    累积和控制图，适用于检测过程的小偏移。

    Args:
        data: 一维数组
        target: 目标值，如果为None则使用数据均值
        k: 参考值 (通常为0.5)，表示要检测的偏移量(单位:sigma)
        h: 决策间隔 (通常4-5)，超过此值触发报警

    Returns:
        ControlLimits对象 (使用简化的单边CUSUM)

    计算公式:
        C_i+ = max(0, C_i+ + X_i - (target + k*sigma))
        C_i- = max(0, C_i- - X_i + (target - k*sigma))
    """
    if data.ndim > 1:
        data = data.flatten()

    if target is None:
        target = np.mean(data)

    sigma = np.std(data, ddof=1)

    if sigma <= 0:
        sigma = 1.0

    # 决策间隔
    ucl = h * sigma
    lcl = -h * sigma

    return ControlLimits(
        ucl=float(ucl),
        cl=0.0,
        lcl=float(lcl),
    )


def _calculate_limits(
    chart_type: ChartType,
    data: np.ndarray,
    **kwargs,
) -> ControlLimits:
    """根据图表类型计算控制限"""
    calculators = {
        ChartType.X_BAR_R: calculate_x_bar_r_limits,
        ChartType.X_BAR_S: calculate_x_bar_s_limits,
        ChartType.X_MR: calculate_x_mr_limits,
        ChartType.C: calculate_c_limits,
        ChartType.U: calculate_u_limits,
        ChartType.P: calculate_p_limits,
        ChartType.NP: calculate_np_limits,
        ChartType.EWMA: calculate_ewma_limits,
        ChartType.CUSUM: calculate_cusum_limits,
    }

    calculator = calculators.get(chart_type)
    if calculator is None:
        raise ValueError(f"Unsupported chart type: {chart_type}")

    return calculator(data, **kwargs)


class ControlChart:
    """控制图

    管理控制图的配置、数据点和限值。

    Attributes:
        chart_id: 控制图唯一标识
        chart_type: 控制图类型
        name: 控制图名称
        control_limits: 控制限
        data: 数据点列表
        auto_update_limits: 是否自动更新限值
        min_samples: 计算限值所需的最少样本数
    """

    def __init__(
        self,
        chart_id: str,
        chart_type: ChartType,
        name: Optional[str] = None,
        control_limits: Optional[ControlLimits] = None,
        auto_update_limits: bool = True,
        min_samples: int = 20,
    ):
        self.chart_id = chart_id
        self.chart_type = chart_type
        self.name = name or f"{chart_type.description}"
        self._control_limits = control_limits
        self._data: List[ChartPoint] = []
        self.auto_update_limits = auto_update_limits
        self.min_samples = min_samples
        self._update_count = 0

    @property
    def control_limits(self) -> Optional[ControlLimits]:
        """获取控制限"""
        return self._control_limits

    @property
    def data(self) -> List[float]:
        """获取数据值列表"""
        return [point.value for point in self._data]

    @property
    def points(self) -> List[ChartPoint]:
        """获取数据点列表"""
        return self._data.copy()

    @property
    def statistics(self) -> Optional[ChartStatistics]:
        """获取统计信息"""
        if len(self._data) == 0:
            return None

        values = self.data
        return ChartStatistics(
            mean=np.mean(values),
            std=np.std(values, ddof=1),
            min=np.min(values),
            max=np.max(values),
            range=np.max(values) - np.min(values),
            median=np.median(values),
            sample_count=len(values),
            violation_count=sum(1 for p in self._data if p.is_violation),
        )

    @property
    def is_ready(self) -> bool:
        """是否准备好进行规则检查"""
        return len(self._data) >= self.min_samples or self._control_limits is not None

    def add_point(
        self,
        value: float,
        timestamp: Optional[datetime] = None,
        group_id: Optional[str] = None,
        quality: str = "normal",
    ) -> ChartPoint:
        """添加数据点

        Args:
            value: 数据值
            timestamp: 时间戳
            group_id: 组ID
            quality: 数据质量

        Returns:
            创建的ChartPoint对象
        """
        timestamp = timestamp or datetime.now()
        point = ChartPoint(
            index=len(self._data),
            value=value,
            timestamp=timestamp,
            group_id=group_id,
            quality=quality,
        )
        self._data.append(point)
        return point

    def update_limits(self) -> Optional[ControlLimits]:
        """更新控制限

        Returns:
            新的控制限，如果数据不足则返回None
        """
        if len(self._data) < self.min_samples:
            return None

        data_array = np.array(self.data)
        self._control_limits = _calculate_limits(
            self.chart_type,
            data_array.reshape(-1, 1) if self.chart_type.requires_group_size else data_array,
        )
        self._update_count += 1
        return self._control_limits

    def check_rules(
        self,
        rules: Optional[List[SPCRule]] = None,
    ) -> List[SPCViolation]:
        """检查SPC规则

        Args:
            rules: 要检查的规则列表

        Returns:
            违规列表
        """
        if self._control_limits is None:
            return []

        if rules is None:
            rules = list(SPCRule)

        violations = check_spc_rules(self.data, self._control_limits, rules)

        # 更新数据点的违规标记
        violation_map: Dict[int, List[str]] = {}
        for v in violations:
            if v.data_index not in violation_map:
                violation_map[v.data_index] = []
            violation_map[v.data_index].append(v.rule.value)

        for point in self._data:
            point.is_violation = point.index in violation_map
            point.violations = violation_map.get(point.index, [])
            point.in_control = self._control_limits.is_within_limits(point.value)

        return violations

    def reset(self) -> None:
        """重置控制图，清除所有数据"""
        self._data.clear()
        self._control_limits = None
        self._update_count = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "chart_id": self.chart_id,
            "chart_type": self.chart_type.value,
            "name": self.name,
            "control_limits": self._control_limits.to_dict() if self._control_limits else None,
            "data": [p.to_dict() for p in self._data],
            "statistics": self.statistics.to_dict() if self.statistics else None,
            "auto_update_limits": self.auto_update_limits,
            "is_ready": self.is_ready,
        }

    def __repr__(self) -> str:
        return (
            f"ControlChart(id={self.chart_id}, type={self.chart_type.value}, "
            f"points={len(self._data)})"
        )
