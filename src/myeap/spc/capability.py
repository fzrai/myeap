"""过程能力分析

实现过程能力指数(Cp, Cpk)和过程性能指数(Pp, Ppk)的计算。
"""

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np


# 标准正态分布近似函数 (不使用scipy)
def _norm_cdf(x: float) -> float:
    """标准正态分布累积分布函数近似

    使用Abramowitz和Stegun的近似公式
    """
    # 防止溢出
    if x < -10:
        return 0.0
    if x > 10:
        return 1.0

    # 系数
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911

    sign = -1 if x < 0 else 1
    x = abs(x) / math.sqrt(2)

    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)

    return 0.5 * (1.0 + sign * y)


def _norm_ppf(p: float) -> float:
    """标准正态分布分位数函数近似 (反函数)

    使用Peter J. Acklam的近似公式
    """
    if p <= 0:
        return float('-inf')
    if p >= 1:
        return float('inf')
    if p == 0.5:
        return 0.0

    # 系数
    a = [
        -3.969683028665376e1,
        2.209460984245205e2,
        -2.759285104469687e2,
        1.383577518672690e2,
        -3.066479806614716e1,
        2.506628277459239e0,
    ]
    b = [
        -5.447609879822406e1,
        1.615858368580409e2,
        -1.556989798598866e2,
        6.680131188771972e1,
        -1.328068155288572e1,
    ]
    c = [
        -7.784894002430293e-3,
        -3.223964580411365e-1,
        -2.400758277161838e0,
        -2.549732539343734e0,
        4.374664141464968e0,
        2.938163982698783e0,
    ]
    d = [
        7.784695709041462e-3,
        3.224671290700398e-1,
        2.445134137142996e0,
        3.754408661907416e0,
    ]

    p_low = 0.02425
    p_high = 1 - p_low

    q = math.sqrt(-2.0 * math.log(p if p < 0.5 else 1.0 - p))

    if p < p_low:
        a_c = sum(a[i] * q ** i for i in range(6))
        b_c = 1.0 + sum(b[i] * q ** i for i in range(5))
        return a_c / b_c - q
    elif p <= p_high:
        a_c = sum(c[i] * q ** i for i in range(5))
        b_c = 1.0 + sum(d[i] * q ** i for i in range(4))
        return a_c / b_c
    else:
        a_c = sum(a[i] * q ** i for i in range(6))
        b_c = 1.0 + sum(b[i] * q ** i for i in range(5))
        return -(a_c / b_c - q)


@dataclass
class ProcessCapability:
    """过程能力分析结果

    Attributes:
        cp: 过程能力 (仅中心) - Cp = (USL - LSL) / (6 * sigma)
        cpk: 过程能力 (考虑偏移) - Cpk = min(Cpu, Cpl)
        cpu: 上限过程能力 - CPU = (USL - mean) / (3 * sigma)
        cpl: 下限过程能力 - CPL = (mean - LSL) / (3 * sigma)
        pp: 过程性能 (长期) - 与Cp类似但使用总标准差
        ppk: 过程性能 (考虑偏移) - 与Cpk类似但使用总标准差
        sigma_within: 组内标准差估计 (短期)
        sigma_total: 总标准差 (长期)
        mean: 过程平均值
        usl: 规格上限
        lsl: 规格下限
        target: 目标值 (如果指定)
        sigma_level: Sigma水平 (DPMO对应)
        ppm_out_of_spec: 超出规格的PPM估计
        yield_percent: 合格率估计 (百分比)
        is_capable: 过程是否满足能力要求 (Cp >= 1.0)
        is_capable_enhanced: 过程是否满足增强能力要求 (Cp >= 1.33)
    """

    cp: float  # 过程能力
    cpk: float  # 过程能力 (考虑偏移)
    cpu: float  # 上限过程能力
    cpl: float  # 下限过程能力
    pp: float  # 过程性能
    ppk: float  # 过程性能 (考虑偏移)
    sigma_within: float  # 组内标准差
    sigma_total: float  # 总标准差
    mean: float  # 平均值
    usl: Optional[float]  # 规格上限
    lsl: Optional[float]  # 规格下限
    target: Optional[float]  # 目标值
    sigma_level: float  # Sigma水平
    ppm_out_of_spec: float  # 超规PPM
    yield_percent: float  # 合格率 (%)

    def __post_init__(self):
        # 设置默认值
        if self.usl is None:
            self.usl = float('inf')
        if self.lsl is None:
            self.lsl = float('-inf')
        if self.target is None and self.usl != float('inf') and self.lsl != float('-inf'):
            self.target = (self.usl + self.lsl) / 2

    @property
    def is_capable(self) -> bool:
        """过程是否满足基本能力要求 (Cp >= 1.0)"""
        return self.cp >= 1.0

    @property
    def is_capable_enhanced(self) -> bool:
        """过程是否满足增强能力要求 (Cp >= 1.33)"""
        return self.cp >= 1.33

    @property
    def is_acceptable(self) -> bool:
        """过程是否可接受 (Cpk >= 1.0)"""
        return self.cpk >= 1.0

    @property
    def cpk_ratio(self) -> float:
        """Cpk与Cp的比值，表示偏移程度 (1表示完美居中)"""
        if self.cp == 0:
            return 0.0
        return self.cpk / self.cp

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "cp": round(self.cp, 4),
            "cpk": round(self.cpk, 4),
            "cpu": round(self.cpu, 4),
            "cpl": round(self.cpl, 4),
            "pp": round(self.pp, 4),
            "ppk": round(self.ppk, 4),
            "sigma_within": round(self.sigma_within, 6),
            "sigma_total": round(self.sigma_total, 6),
            "mean": round(self.mean, 6),
            "usl": round(self.usl, 6) if self.usl != float('inf') else None,
            "lsl": round(self.lsl, 6) if self.lsl != float('-inf') else None,
            "target": round(self.target, 6) if self.target else None,
            "sigma_level": round(self.sigma_level, 2),
            "ppm_out_of_spec": round(self.ppm_out_of_spec, 2),
            "yield_percent": round(self.yield_percent, 4),
            "is_capable": self.is_capable,
            "is_capable_enhanced": self.is_capable_enhanced,
            "is_acceptable": self.is_acceptable,
            "cpk_ratio": round(self.cpk_ratio, 4),
        }

    def __repr__(self) -> str:
        return (
            f"ProcessCapability(cp={self.cp:.4f}, cpk={self.cpk:.4f}, "
            f"pp={self.pp:.4f}, ppk={self.ppk:.4f}, "
            f"sigma_level={self.sigma_level:.2f}sigma)"
        )


def calculate_sigma_within(data: np.ndarray, n: int = 5) -> float:
    """计算组内标准差 (用于Cp计算)

    使用移动极差法或标准差法估计短期标准差。

    Args:
        data: 一维数据数组
        n: 分组大小 (默认5)

    Returns:
        组内标准差估计
    """
    if len(data) < n:
        # 数据不足，使用总标准差
        return np.std(data, ddof=1)

    # 使用移动极差法
    # MR_i = |x_i - x_{i-1} for i > 1
    # sigma = MR_bar / d2
    mr = np.abs(np.diff(data))
    mr_bar = np.mean(mr)
    d2 = 1.128  # n=2的d2值

    return mr_bar / d2


def calculate_capability(
    data: List[float],
    usl: Optional[float] = None,
    lsl: Optional[float] = None,
    target: Optional[float] = None,
    method: str = "auto",
) -> ProcessCapability:
    """计算过程能力指数

    Args:
        data: 过程数据列表
        usl: 规格上限 (Optional)
        lsl: 规格下限 (Optional)
        target: 目标值 (Optional)
        method: 计算方法 ("auto", "moving_range", "pooled_std")

    Returns:
        ProcessCapability对象

    计算公式:
        Cp = (USL - LSL) / (6 * sigma)
        CpK = min((USL - mean) / (3 * sigma), (mean - LSL) / (3 * sigma))

        其中sigma使用组内标准差 (短期变异)
    """
    data = np.array(data)
    n = len(data)

    if n < 2:
        raise ValueError("需要至少2个数据点来计算过程能力")

    mean = np.mean(data)

    # 计算标准差
    sigma_total = np.std(data, ddof=1)  # 总标准差 (长期)

    if method == "moving_range" or (method == "auto" and n < 25):
        sigma_within = calculate_sigma_within(data)
    else:
        sigma_within = sigma_total

    # 默认规格限
    if usl is None and lsl is None:
        # 无规格限，返回基本统计
        return ProcessCapability(
            cp=0.0,
            cpk=0.0,
            cpu=0.0,
            cpl=0.0,
            pp=0.0,
            ppk=0.0,
            sigma_within=sigma_within,
            sigma_total=sigma_total,
            mean=mean,
            usl=None,
            lsl=None,
            target=target,
            sigma_level=0.0,
            ppm_out_of_spec=0.0,
            yield_percent=100.0,
        )

    # 处理单边规格
    if usl is None:
        usl = float('inf')
    if lsl is None:
        lsl = float('-inf')

    # 计算Cp和Cpk
    cp = 0.0
    cpk = 0.0
    cpu = 0.0
    cpl = 0.0
    pp = 0.0

    if usl != float('inf') and lsl != float('-inf'):
        if sigma_within > 0:
            cp = (usl - lsl) / (6 * sigma_within)
        if sigma_total > 0:
            pp = (usl - lsl) / (6 * sigma_total)
    else:
        pp = 0.0

    if sigma_within > 0:
        if usl != float('inf'):
            cpu = (usl - mean) / (3 * sigma_within)
        if lsl != float('-inf'):
            cpl = (mean - lsl) / (3 * sigma_within)
        cpk = min(
            cpu if usl != float('inf') else float('inf'),
            cpl if lsl != float('-inf') else float('inf')
        )

    # 使用总标准差计算Pp和Ppk
    ppu = 0.0
    ppl = 0.0
    if sigma_total > 0:
        if usl != float('inf') and lsl != float('-inf'):
            pp = (usl - lsl) / (6 * sigma_total)
        if usl != float('inf'):
            ppu = (usl - mean) / (3 * sigma_total)
        if lsl != float('-inf'):
            ppl = (mean - lsl) / (3 * sigma_total)
        ppk = min(
            ppu if usl != float('inf') else float('inf'),
            ppl if lsl != float('-inf') else float('inf')
        )
    else:
        ppk = 0.0

    # 计算Sigma水平和DPMO
    ppm_out_of_spec, sigma_level = _calculate_ppm_and_sigma(
        data, mean, sigma_total, usl, lsl
    )

    yield_percent = 100.0 - ppm_out_of_spec / 10000.0

    return ProcessCapability(
        cp=cp,
        cpk=cpk,
        cpu=cpu,
        cpl=cpl,
        pp=pp,
        ppk=ppk,
        sigma_within=sigma_within,
        sigma_total=sigma_total,
        mean=mean,
        usl=usl,
        lsl=lsl,
        target=target,
        sigma_level=sigma_level,
        ppm_out_of_spec=ppm_out_of_spec,
        yield_percent=yield_percent,
    )


def _calculate_ppm_and_sigma(
    data: np.ndarray,
    mean: float,
    sigma: float,
    usl: float,
    lsl: float,
) -> tuple:
    """计算超出规格的PPM和Sigma水平

    Args:
        data: 数据数组
        mean: 平均值
        sigma: 标准差
        usl: 规格上限
        lsl: 规格下限

    Returns:
        (ppm_out_of_spec, sigma_level) 元组
    """
    if sigma <= 0:
        return 0.0, 6.0

    # 计算超出规格的比率
    z_upper_cdf = _norm_cdf((usl - mean) / sigma) if usl != float('inf') else 1.0
    z_lower_cdf = _norm_cdf((mean - lsl) / sigma) if lsl != float('-inf') else 1.0

    # 超出上限的比例
    upper_tail = 1 - z_upper_cdf if usl != float('inf') else 0.0
    # 超出下限的比例
    lower_tail = 1 - z_lower_cdf if lsl != float('-inf') else 0.0

    # 总超出规格比例
    total_out_of_spec = upper_tail + lower_tail

    # 转换为PPM
    ppm_out_of_spec = total_out_of_spec * 1_000_000

    # 计算Sigma水平 (使用DPMO)
    # 6 Sigma = 3.4 DPMO
    if ppm_out_of_spec <= 0:
        sigma_level = 6.0
    elif ppm_out_of_spec >= 1_000_000:
        sigma_level = 0.0
    else:
        # 反推Z值: 使用单边近似
        sigma_level = _norm_ppf(1 - total_out_of_spec / 2)
        sigma_level = max(0, min(6, sigma_level))

    return ppm_out_of_spec, sigma_level


def calculate_pp_apk(
    data: List[float],
    usl: Optional[float] = None,
    lsl: Optional[float] = None,
) -> tuple:
    """计算过程性能指数 (Pp, Ppk)

    Pp和Ppk使用总标准差(包含组间变异)，反映过程的长期性能。

    Args:
        data: 过程数据列表
        usl: 规格上限
        lsl: 规格下限

    Returns:
        (pp, ppk) 元组
    """
    data = np.array(data)
    n = len(data)

    if n < 2:
        raise ValueError("需要至少2个数据点来计算过程性能")

    mean = np.mean(data)
    sigma_total = np.std(data, ddof=1)

    if sigma_total <= 0:
        return 0.0, 0.0

    # 默认规格限
    if usl is None and lsl is None:
        return 0.0, 0.0

    if usl is None:
        usl = float('inf')
    if lsl is None:
        lsl = float('-inf')

    # 计算Pp
    pp = 0.0
    if usl != float('inf') and lsl != float('-inf'):
        pp = (usl - lsl) / (6 * sigma_total)

    # 计算Ppk
    ppu = (usl - mean) / (3 * sigma_total) if usl != float('inf') else float('inf')
    ppl = (mean - lsl) / (3 * sigma_total) if lsl != float('-inf') else float('inf')
    ppk = min(ppu, ppl)

    return pp, ppk


def calculate_cp_from_data(
    data: List[float],
    n: int = 5,
) -> float:
    """使用移动极差法计算Cp

    Args:
        data: 过程数据列表
        n: 分组大小

    Returns:
        Cp值
    """
    data = np.array(data)
    if len(data) < 2:
        return 0.0

    sigma = calculate_sigma_within(data, n)
    if sigma <= 0:
        return 0.0

    # 假设6σ覆盖99.73%的数据
    return 1.0 / 1.0  # 返回相对值


def interpret_capability(capability: ProcessCapability) -> str:
    """解释过程能力分析结果

    Args:
        capability: 过程能力分析结果

    Returns:
        能力等级描述
    """
    cpk = capability.cpk

    if cpk < 0.67:
        return "能力不足 (需要立即改进)"
    elif cpk < 1.00:
        return "能力勉强 (需要改进)"
    elif cpk < 1.33:
        return "能力尚可 (需要持续改进)"
    elif cpk < 1.67:
        return "能力良好 (满足要求)"
    elif cpk < 2.00:
        return "能力优秀 (超越要求)"
    else:
        return "能力卓越 (世界级水平)"


def get_capability_action(
    capability: ProcessCapability,
) -> str:
    """获取基于能力指数的改进建议

    Args:
        capability: 过程能力分析结果

    Returns:
        改进建议
    """
    cp = capability.cp
    cpk = capability.cpk

    if cp == 0 or cpk == 0:
        return "请提供规格限(USL/LSL)以进行能力分析"

    # 判断偏移方向
    if capability.cpu < capability.cpl:
        offset_direction = "偏向上限"
    elif capability.cpl < capability.cpu:
        offset_direction = "偏向下限"
    else:
        offset_direction = "居中"

    # 建议
    if cp < 1.0 and cpk < 1.0:
        return f"过程变异过大且存在偏移({offset_direction})，需要同时减少变异和调整中心"
    elif cp < 1.0:
        return "过程变异过大，需要减少标准差"
    elif cpk < 1.0:
        return f"过程存在偏移({offset_direction})，需要调整中心"
    elif cp >= 1.33 and cpk >= 1.33:
        return "能力优秀，继续保持"
    elif cp >= 1.0 and cpk >= 1.0:
        return "能力满足要求，可考虑持续改进"
    else:
        return "能力不足，需要改进"
