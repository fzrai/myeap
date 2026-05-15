"""PID控制器

实现完整的PID控制器，包含抗积分饱和(anti-windup)、
微分项低通滤波(low-pass filter)、死区(deadband)等工业级特性。

支持标准PID和级联(Cascade) PID控制。
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class PIDConfig:
    """PID控制器配置

    Attributes:
        kp: 比例增益 (Proportional gain)
        ki: 积分增益 (Integral gain)
        kd: 微分增益 (Derivative gain)
        setpoint: 目标设定点
        output_min: 输出下限，None表示无限制
        output_max: 输出上限，None表示无限制
        anti_windup: 是否启用抗积分饱和
        derivative_filter: 微分低通滤波系数 (0=完全滤波, 1=无滤波)
        deadband: 死区范围，|error| < deadband 时输出为0
    """

    kp: float
    ki: float
    kd: float
    setpoint: float
    output_min: Optional[float] = None
    output_max: Optional[float] = None
    anti_windup: bool = True
    derivative_filter: float = 0.1
    deadband: float = 0.0

    def __post_init__(self):
        """验证配置参数"""
        if self.kp < 0:
            raise ValueError("kp must be non-negative")
        if self.ki < 0:
            raise ValueError("ki must be non-negative")
        if self.kd < 0:
            raise ValueError("kd must be non-negative")
        if self.derivative_filter < 0 or self.derivative_filter > 1:
            raise ValueError("derivative_filter must be between 0 and 1")
        if self.deadband < 0:
            raise ValueError("deadband must be non-negative")
        if (
            self.output_min is not None
            and self.output_max is not None
            and self.output_min >= self.output_max
        ):
            raise ValueError("output_min must be less than output_max")

    def with_setpoint(self, setpoint: float) -> "PIDConfig":
        """返回更新设定点后的新配置"""
        return PIDConfig(
            kp=self.kp,
            ki=self.ki,
            kd=self.kd,
            setpoint=setpoint,
            output_min=self.output_min,
            output_max=self.output_max,
            anti_windup=self.anti_windup,
            derivative_filter=self.derivative_filter,
            deadband=self.deadband,
        )


class PIDController:
    """PID控制器

    实现带抗积分饱和和微分滤波的PID控制算法。

    特性：
    - 比例项：快速响应误差
    - 积分项：消除稳态误差，含抗积分饱和
    - 微分项：抑制超调和振荡，含低通滤波
    - 死区：避免因噪声导致的频繁调整
    - 输出钳位：确保输出在安全范围内

    Example:
        >>> config = PIDConfig(kp=2.0, ki=0.5, kd=0.1, setpoint=100.0,
        ...                    output_min=0.0, output_max=200.0)
        >>> pid = PIDController(config)
        >>> output = pid.compute(95.0)
        >>> pid.update_setpoint(105.0)
    """

    def __init__(self, config: PIDConfig):
        self.config = config
        self.reset()

    def reset(self):
        """重置控制器内部状态"""
        self._integral: float = 0.0
        self._prev_error: float = 0.0
        self._prev_derivative: float = 0.0
        self._prev_time: Optional[float] = None
        self._prev_output: float = 0.0
        self._saturated: bool = False

    @property
    def integral(self) -> float:
        """获取当前积分项累计值"""
        return self._integral

    @property
    def saturated(self) -> bool:
        """获取上一次计算是否发生饱和"""
        return self._saturated

    def compute(
        self, measurement: float, current_time: Optional[float] = None
    ) -> float:
        """计算PID控制输出

        Args:
            measurement: 当前测量值
            current_time: 当前时间戳（秒），None则自动获取

        Returns:
            控制输出值
        """
        if current_time is None:
            current_time = time.monotonic()

        # 计算误差
        error = self.config.setpoint - measurement

        # 死区检查
        if abs(error) <= self.config.deadband:
            return self._prev_output

        # 计算时间间隔
        if self._prev_time is None:
            dt = 0.01  # 首次调用默认10ms
        else:
            dt = current_time - self._prev_time
            if dt <= 0:
                dt = 0.01  # 防止零或负时间间隔
            elif dt > 1.0:
                dt = 1.0  # 限制最大时间间隔

        # --- 比例项 ---
        p_term = self.config.kp * error

        # --- 积分项（含抗积分饱和） ---
        if self.config.ki > 0:
            # 积分累加
            self._integral += error * dt

            # 计算积分项
            i_term = self.config.ki * self._integral

            # 抗积分饱和: 先钳位积分累积值
            if self.config.anti_windup:
                max_integral = float("inf")
                min_integral = float("-inf")
                if self.config.output_max is not None:
                    max_integral = self.config.output_max / self.config.ki
                if self.config.output_min is not None:
                    min_integral = self.config.output_min / self.config.ki

                if self._integral > max_integral:
                    self._integral = max_integral
                elif self._integral < min_integral:
                    self._integral = min_integral

                i_term = self.config.ki * self._integral
        else:
            i_term = 0.0

        # --- 微分项（含低通滤波） ---
        if self.config.kd > 0 and dt > 0:
            raw_derivative = (error - self._prev_error) / dt
            # 一阶低通滤波器
            alpha = self.config.derivative_filter
            filtered_derivative = alpha * raw_derivative + (
                1 - alpha
            ) * self._prev_derivative
            d_term = self.config.kd * filtered_derivative
            self._prev_derivative = filtered_derivative
        else:
            d_term = 0.0

        # --- 组合输出 ---
        output = p_term + i_term + d_term

        # --- 输出钳位和最终抗积分饱和 ---
        self._saturated = False
        if self.config.output_max is not None and output > self.config.output_max:
            over = output - self.config.output_max
            # 反算积分项：回溯减少积分累积
            if self.config.anti_windup and self.config.ki > 0:
                self._integral -= over / self.config.ki
            output = self.config.output_max
            self._saturated = True
        elif self.config.output_min is not None and output < self.config.output_min:
            under = self.config.output_min - output
            if self.config.anti_windup and self.config.ki > 0:
                self._integral += under / self.config.ki
            output = self.config.output_min
            self._saturated = True

        # --- 更新状态 ---
        self._prev_error = error
        self._prev_output = output
        self._prev_time = current_time

        return output

    def compute_with_terms(
        self, measurement: float, current_time: Optional[float] = None
    ) -> Tuple[float, float, float, float]:
        """计算控制输出并返回各项贡献

        Args:
            measurement: 当前测量值
            current_time: 当前时间戳（秒）

        Returns:
            (output, p_term, i_term, d_term) 元组
        """
        if current_time is None:
            current_time = time.monotonic()

        error = self.config.setpoint - measurement

        if abs(error) <= self.config.deadband:
            return self._prev_output, 0.0, 0.0, 0.0

        if self._prev_time is None:
            dt = 0.01
        else:
            dt = current_time - self._prev_time
            if dt <= 0:
                dt = 0.01
            elif dt > 1.0:
                dt = 1.0

        # 比例项
        p_term = self.config.kp * error

        # 积分项
        if self.config.ki > 0:
            self._integral += error * dt
            if self.config.anti_windup:
                max_integral = float("inf")
                min_integral = float("-inf")
                if self.config.output_max is not None:
                    max_integral = self.config.output_max / self.config.ki
                if self.config.output_min is not None:
                    min_integral = self.config.output_min / self.config.ki
                self._integral = max(
                    min_integral, min(max_integral, self._integral)
                )
            i_term = self.config.ki * self._integral
        else:
            i_term = 0.0

        # 微分项
        if self.config.kd > 0 and dt > 0:
            raw_derivative = (error - self._prev_error) / dt
            alpha = self.config.derivative_filter
            filtered_derivative = alpha * raw_derivative + (
                1 - alpha
            ) * self._prev_derivative
            d_term = self.config.kd * filtered_derivative
            self._prev_derivative = filtered_derivative
        else:
            d_term = 0.0

        output = p_term + i_term + d_term

        # 输出钳位
        self._saturated = False
        if self.config.output_max is not None and output > self.config.output_max:
            if self.config.anti_windup and self.config.ki > 0:
                self._integral -= (output - self.config.output_max) / self.config.ki
            output = self.config.output_max
            self._saturated = True
        elif self.config.output_min is not None and output < self.config.output_min:
            if self.config.anti_windup and self.config.ki > 0:
                self._integral += (self.config.output_min - output) / self.config.ki
            output = self.config.output_min
            self._saturated = True

        self._prev_error = error
        self._prev_output = output
        self._prev_time = current_time

        return output, p_term, i_term, d_term

    def update_setpoint(self, setpoint: float) -> None:
        """更新目标设定点

        Args:
            setpoint: 新的设定点值
        """
        self.config.setpoint = setpoint

    def update_gains(
        self,
        kp: Optional[float] = None,
        ki: Optional[float] = None,
        kd: Optional[float] = None,
    ) -> None:
        """更新PID增益参数

        只更新传入的非None参数。

        Args:
            kp: 新的比例增益
            ki: 新的积分增益
            kd: 新的微分增益
        """
        if kp is not None and kp >= 0:
            self.config.kp = kp
        if ki is not None and ki >= 0:
            self.config.ki = ki
        if kd is not None and kd >= 0:
            self.config.kd = kd

    def get_state(self) -> Dict:
        """获取控制器内部状态"""
        return {
            "integral": self._integral,
            "prev_error": self._prev_error,
            "prev_derivative": self._prev_derivative,
            "prev_output": self._prev_output,
            "saturated": self._saturated,
            "prev_time": self._prev_time,
        }


class CascadePIDController:
    """级联PID控制器

    实现主-从结构的级联PID控制，用于复杂工艺参数的精确控制。
    典型应用场景：
    - 温度控制：主回路控温，从回路控功率
    - 压力控制：主回路控压，从回路控阀门开度

    主回路输出作为从回路的设定点。
    """

    def __init__(
        self,
        primary_config: PIDConfig,
        secondary_config: PIDConfig,
        ratio: float = 1.0,
    ):
        """初始化级联PID控制器

        Args:
            primary_config: 主回路（外环）PID配置
            secondary_config: 从回路（内环）PID配置
            ratio: 主回路输出到从回路设定点的缩放比例
        """
        self.primary = PIDController(primary_config)
        self.secondary = PIDController(secondary_config)
        self.ratio = ratio

    def reset(self):
        """重置两个回路的内部状态"""
        self.primary.reset()
        self.secondary.reset()

    def compute(
        self,
        primary_measurement: float,
        secondary_measurement: float,
        current_time: Optional[float] = None,
    ) -> float:
        """计算级联控制输出

        主回路根据外部测量值计算输出，作为从回路的设定点；
        从回路根据内部测量值计算最终控制输出。

        Args:
            primary_measurement: 主回路测量值（如温度）
            secondary_measurement: 从回路测量值（如功率）
            current_time: 当前时间戳

        Returns:
            最终控制输出值
        """
        if current_time is None:
            current_time = time.monotonic()

        # 主回路计算
        primary_output = self.primary.compute(primary_measurement, current_time)

        # 缩放后作为从回路设定点
        secondary_setpoint = primary_output * self.ratio
        self.secondary.update_setpoint(secondary_setpoint)

        # 从回路计算最终输出
        final_output = self.secondary.compute(secondary_measurement, current_time)

        return final_output

    def update_primary_setpoint(self, setpoint: float) -> None:
        """更新主回路设定点"""
        self.primary.update_setpoint(setpoint)

    @property
    def primary_integral(self) -> float:
        """获取主回路积分项"""
        return self.primary.integral

    @property
    def secondary_integral(self) -> float:
        """获取从回路积分项"""
        return self.secondary.integral

    def get_state(self) -> Dict:
        """获取级联控制器状态"""
        return {
            "primary": self.primary.get_state(),
            "secondary": self.secondary.get_state(),
            "ratio": self.ratio,
        }
