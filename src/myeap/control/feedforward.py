"""前馈控制器

实现前馈开环补偿控制，用于抵消已知扰动对过程的影响。
支持静态前馈模型、一阶动态前馈模型和自适应前馈模型。

前馈控制通过与反馈控制结合（级联），可以显著提高控制系统
对可测量扰动的响应速度和抗扰能力。
"""

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class FeedforwardModel:
    """前馈模型定义

    Attributes:
        name: 模型名称（通常为扰动参数名）
        gain: 静态增益 (steady-state gain, 输出变化 / 扰动变化)
        time_constant: 时间常数（秒），用于一阶动态补偿
        dead_time: 滞后时间（秒），扰动到输出的延迟
        enabled: 是否启用该前馈模型
    """

    name: str
    gain: float = 1.0
    time_constant: float = 0.0
    dead_time: float = 0.0
    enabled: bool = True

    def __post_init__(self):
        """验证模型参数"""
        if self.time_constant < 0:
            raise ValueError("time_constant must be non-negative")
        if self.dead_time < 0:
            raise ValueError("dead_time must be non-negative")

    @property
    def is_static(self) -> bool:
        """是否为静态前馈模型"""
        return self.time_constant == 0.0 and self.dead_time == 0.0

    @property
    def is_dynamic(self) -> bool:
        """是否为动态前馈模型"""
        return not self.is_static


class FeedforwardController:
    """前馈控制器

    根据可测量的扰动变量，计算前馈补偿量，前馈到控制输出上。

    支持：
    - 多扰动源的前馈补偿
    - 一阶动态前馈模型
    - 可插入的自定义前馈补偿函数

    Example:
        >>> ff = FeedforwardController()
        >>> ff.add_model("chamber_pressure", gain=-0.5, time_constant=2.0)
        >>> correction = ff.compute({"chamber_pressure": 1.2})
    """

    def __init__(self):
        self._models: Dict[str, FeedforwardModel] = {}
        self._custom_models: Dict[str, Callable[[float], float]] = {}
        self._prev_disturbance: Dict[str, float] = {}
        self._prev_correction: Dict[str, float] = {}
        self._prev_time: Optional[float] = None

    def add_model(
        self,
        parameter: str,
        gain: float,
        time_constant: float = 0.0,
        dead_time: float = 0.0,
    ) -> FeedforwardModel:
        """添加前馈模型

        Args:
            parameter: 扰动参数名称
            gain: 静态增益
            time_constant: 一阶时间常数（秒）
            dead_time: 滞后时间（秒）

        Returns:
            创建的FeedforwardModel实例
        """
        model = FeedforwardModel(
            name=parameter,
            gain=gain,
            time_constant=time_constant,
            dead_time=dead_time,
        )
        self._models[parameter] = model
        return model

    def add_custom_model(
        self, parameter: str, func: Callable[[float], float]
    ) -> None:
        """添加自定义前馈补偿函数

        用于需要复杂非线性前馈补偿的场景。

        Args:
            parameter: 扰动参数名称
            func: 自定义补偿函数，接收扰动值，返回补偿输出
        """
        self._custom_models[parameter] = func

    def remove_model(self, parameter: str) -> bool:
        """移除前馈模型

        Args:
            parameter: 扰动参数名称

        Returns:
            是否成功移除
        """
        removed = False
        if parameter in self._models:
            del self._models[parameter]
            removed = True
        if parameter in self._custom_models:
            del self._custom_models[parameter]
            removed = True
        return removed

    def enable_model(self, parameter: str, enabled: bool = True) -> bool:
        """启用或禁用一个前馈模型

        Args:
            parameter: 扰动参数名称
            enabled: 是否启用

        Returns:
            操作是否成功（模型存在）
        """
        model = self._models.get(parameter)
        if model:
            model.enabled = enabled
            return True
        return False

    def compute(
        self,
        disturbance: Dict[str, float],
        current_time: Optional[float] = None,
    ) -> float:
        """计算前馈补偿量

        根据当前的扰动测量值，计算总的前馈补偿输出。

        对于动态模型，使用一阶前向差分近似：
            G_ff(s) = gain / (tau*s + 1) -> y_k = alpha*y_{k-1} + (1-alpha)*gain*u_k
            其中 alpha = exp(-dt/tau)

        Args:
            disturbance: 扰动测量值字典 {参数名: 测量值}
            current_time: 当前时间戳

        Returns:
            总前馈补偿量
        """
        if current_time is None:
            current_time = time.monotonic()

        # 计算时间步长
        if self._prev_time is None:
            dt = 0.01
        else:
            dt = current_time - self._prev_time
            if dt <= 0:
                dt = 0.01
            elif dt > 1.0:
                dt = 1.0

        total_correction = 0.0

        for param, value in disturbance.items():
            # 标准模型
            model = self._models.get(param)
            if model and model.enabled:
                correction = self._compute_model(model, value, dt)
                total_correction += correction

            # 自定义模型
            custom_func = self._custom_models.get(param)
            if custom_func:
                total_correction += custom_func(value)

        self._prev_time = current_time
        return total_correction

    def _compute_model(
        self, model: FeedforwardModel, value: float, dt: float
    ) -> float:
        """计算单个前馈模型的输出

        Args:
            model: 前馈模型
            value: 当前扰动值
            dt: 时间步长

        Returns:
            补偿量
        """
        if model.is_static:
            # 静态前馈：直接比例
            return model.gain * value
        else:
            # 一阶动态前馈：y_k = alpha * y_{k-1} + (1-alpha) * gain * u_k
            if model.time_constant > 0:
                alpha = self._calc_alpha(dt, model.time_constant)
            else:
                alpha = 0.0

            prev_correction = self._prev_correction.get(model.name, value * model.gain)
            correction = alpha * prev_correction + (1 - alpha) * model.gain * value

            self._prev_correction[model.name] = correction
            return correction

    @staticmethod
    def _calc_alpha(dt: float, tau: float) -> float:
        """计算一阶滤波系数 alpha = exp(-dt/tau)

        Args:
            dt: 时间步长
            tau: 时间常数

        Returns:
            滤波系数 (0~1 之间)
        """
        import math

        if tau <= 0:
            return 0.0
        ratio = -dt / tau
        # 防止溢出
        if ratio < -50:
            return 0.0
        return math.exp(ratio)

    def get_correction_breakdown(
        self,
        disturbance: Dict[str, float],
        current_time: Optional[float] = None,
    ) -> Dict[str, float]:
        """获取各项前馈补偿的明细

        Args:
            disturbance: 扰动测量值字典
            current_time: 当前时间戳

        Returns:
            {参数名: 补偿量} 字典，包含 "total" 键
        """
        if current_time is None:
            current_time = time.monotonic()

        if self._prev_time is None:
            dt = 0.01
        else:
            dt = current_time - self._prev_time
            if dt <= 0:
                dt = 0.01
            elif dt > 1.0:
                dt = 1.0

        breakdown: Dict[str, float] = {}
        total = 0.0

        for param, value in disturbance.items():
            model = self._models.get(param)
            if model and model.enabled:
                correction = self._compute_model(model, value, dt)
                breakdown[param] = correction
                total += correction

            custom_func = self._custom_models.get(param)
            if custom_func:
                c = custom_func(value)
                breakdown[f"{param}_custom"] = c
                total += c

        breakdown["total"] = total
        self._prev_time = current_time
        return breakdown

    def reset(self):
        """重置前馈控制器的内部状态"""
        self._prev_disturbance.clear()
        self._prev_correction.clear()
        self._prev_time = None

    def list_models(self) -> List[Dict[str, Any]]:
        """列出所有注册的前馈模型"""
        result = []
        for param, model in self._models.items():
            result.append(
                {
                    "parameter": param,
                    "gain": model.gain,
                    "time_constant": model.time_constant,
                    "dead_time": model.dead_time,
                    "enabled": model.enabled,
                    "is_static": model.is_static,
                }
            )
        for param in self._custom_models:
            result.append(
                {
                    "parameter": param,
                    "gain": None,
                    "time_constant": None,
                    "dead_time": None,
                    "enabled": True,
                    "is_static": False,
                    "custom": True,
                }
            )
        return result


class AdaptiveFeedforwardController(FeedforwardController):
    """自适应前馈控制器

    在标准前馈控制器的基础上，增加对前馈增益的在线自适应调整能力。
    根据观测到的残余误差，自动调整前馈模型的增益参数。
    """

    def __init__(self, learning_rate: float = 0.01):
        """初始化自适应前馈控制器

        Args:
            learning_rate: 增益自适应学习率
        """
        super().__init__()
        self.learning_rate = learning_rate
        self._gain_history: Dict[str, List[float]] = {}

    def adapt(
        self, parameter: str, disturbance_value: float, residual_error: float
    ) -> float:
        """自适应调整前馈增益

        使用梯度下降法调整增益：
            gain_new = gain_old - lr * residual_error * disturbance_value

        Args:
            parameter: 扰动参数名称
            disturbance_value: 当前扰动值
            residual_error: 残余误差 (前馈补偿后的剩余误差)

        Returns:
            更新后的增益值
        """
        model = self._models.get(parameter)
        if model is None:
            return 0.0

        # 梯度下降: d(error^2)/d(gain) = -2 * error * disturbance_value
        # gain_new = gain_old + lr * error * disturbance_value
        delta = self.learning_rate * residual_error * disturbance_value
        model.gain += delta

        # 记录历史
        if parameter not in self._gain_history:
            self._gain_history[parameter] = []
        self._gain_history[parameter].append(model.gain)

        return model.gain

    def compute_and_adapt(
        self,
        disturbance: Dict[str, float],
        residual_error: float,
        current_time: Optional[float] = None,
    ) -> float:
        """计算前馈补偿并自适应调整增益

        先计算前馈补偿，然后根据残余误差调整各模型增益。

        Args:
            disturbance: 扰动测量值字典
            residual_error: 残余误差
            current_time: 当前时间戳

        Returns:
            总前馈补偿量
        """
        correction = self.compute(disturbance, current_time)

        # 分布式自适应：按各扰动的贡献比例分配误差
        for param, value in disturbance.items():
            model = self._models.get(param)
            if model and model.enabled:
                model_contrib = abs(model.gain * value)
                total_contrib = sum(
                    abs(m.gain * disturbance.get(m.name, 0))
                    for m in self._models.values()
                    if m.enabled
                )
                if total_contrib > 0:
                    weighted_error = residual_error * (model_contrib / total_contrib)
                else:
                    weighted_error = residual_error
                self.adapt(param, value, weighted_error)

        return correction

    def get_gain_history(self, parameter: str) -> List[float]:
        """获取指定参数的前馈增益历史

        Args:
            parameter: 扰动参数名称

        Returns:
            增益变化历史列表
        """
        return self._gain_history.get(parameter, [])

    def reset(self):
        """重置控制器状态（包括增益历史）"""
        super().reset()
        self._gain_history.clear()
