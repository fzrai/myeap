"""自适应控制器

实现工业级的自适应PID控制算法，支持在线自动参数整定。
根据系统实时响应特性，动态调整PID参数以优化控制性能。

整定策略：
- 基于误差统计的自适应 (error-statistics based)
- 基于性能指标的自适应 (performance-index based)
- 增益调度 (gain scheduling)
- 振荡检测与抑制
"""

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from myeap.control.pid import PIDConfig, PIDController


@dataclass
class AdaptiveConfig:
    """自适应控制器配置

    Attributes:
        base_config: 基础PID配置
        tuning_enabled: 是否启用自动整定
        tuning_interval: 自动整定周期（样本数）
        learning_rate: 参数调整学习率
        damping_factor: 阻尼因子 (0~1)，用于平滑参数变化
        error_threshold: 误差阈值，低于此值认为是良好控制
        oscillation_threshold: 振荡检测阈值
        min_gain: PID参数最小值
        max_gain: PID参数最大值
        history_size: 性能历史缓冲区大小
    """

    base_config: PIDConfig
    tuning_enabled: bool = True
    tuning_interval: int = 100
    learning_rate: float = 0.05
    damping_factor: float = 0.8
    error_threshold: float = 0.1
    oscillation_threshold: float = 0.3
    min_gain: float = 0.0
    max_gain: float = 100.0
    history_size: int = 200

    def __post_init__(self):
        """验证配置参数"""
        if self.tuning_interval < 10:
            raise ValueError("tuning_interval must be at least 10")
        if self.learning_rate <= 0 or self.learning_rate > 1:
            raise ValueError("learning_rate must be in (0, 1]")
        if self.damping_factor < 0 or self.damping_factor > 1:
            raise ValueError("damping_factor must be in [0, 1]")
        if self.history_size < 10:
            raise ValueError("history_size must be at least 10")


@dataclass
class TuningResult:
    """整定结果

    Attributes:
        timestamp: 整定时间
        previous_gains: 整定前的PID参数 (kp, ki, kd)
        new_gains: 整定后的PID参数 (kp, ki, kd)
        reason: 整定原因
        metrics: 性能指标
    """

    timestamp: float
    previous_gains: Tuple[float, float, float]
    new_gains: Tuple[float, float, float]
    reason: str = ""
    metrics: Dict[str, float] = field(default_factory=dict)

    @property
    def kp_change(self) -> float:
        """Kp变化量"""
        return self.new_gains[0] - self.previous_gains[0]

    @property
    def ki_change(self) -> float:
        """Ki变化量"""
        return self.new_gains[1] - self.previous_gains[1]

    @property
    def kd_change(self) -> float:
        """Kd变化量"""
        return self.new_gains[2] - self.previous_gains[2]


class AdaptiveController:
    """自适应PID控制器

    在标准PID控制器基础上，增加在线自适应参数整定功能。
    通过持续监测系统响应性能，自动调整PID参数以维持最优控制。

    自适应策略：
    1. 稳态误差大 -> 增加Ki以消除稳态误差
    2. 稳态误差小 -> 微调Ki防止过积分
    3. 波动/振荡大 -> 增加Kd以增加阻尼
    4. 波动/振荡小 -> 减小Kd减少噪声敏感性
    5. 响应慢 -> 增加Kp以提高响应速度
    6. 超调大 -> 减小Kp并增加Kd

    Example:
        >>> base = PIDConfig(kp=2.0, ki=0.5, kd=0.1, setpoint=100.0)
        >>> adapt_config = AdaptiveConfig(base_config=base)
        >>> controller = AdaptiveController(adapt_config)
        >>> output = controller.compute(95.0)
    """

    def __init__(self, config: AdaptiveConfig):
        self.config = config
        self.pid = PIDController(config.base_config)
        self._performance_history: List[Dict[str, float]] = []
        self._tuning_history: List[TuningResult] = []
        self._sample_count: int = 0
        self._oscillation_counter: int = 0
        self._prev_error_sign: int = 0  # 1=正, -1=负, 0=零

    def reset(self):
        """重置控制器状态（保留已整定的PID参数）"""
        self.pid.reset()
        self._performance_history.clear()
        self._sample_count = 0
        self._oscillation_counter = 0
        self._prev_error_sign = 0

    def full_reset(self):
        """完全重置，恢复到基础配置"""
        self.pid = PIDController(self.config.base_config)
        self._performance_history.clear()
        self._tuning_history.clear()
        self._sample_count = 0
        self._oscillation_counter = 0
        self._prev_error_sign = 0

    @property
    def tuning_count(self) -> int:
        """获取自动整定次数"""
        return len(self._tuning_history)

    @property
    def last_tuning(self) -> Optional[TuningResult]:
        """获取最近一次整定结果"""
        return self._tuning_history[-1] if self._tuning_history else None

    def compute(
        self, measurement: float, timestamp: Optional[float] = None
    ) -> float:
        """计算控制输出（含自适应整定）

        Args:
            measurement: 当前测量值
            timestamp: 当前时间戳

        Returns:
            控制输出值
        """
        if timestamp is None:
            timestamp = time.monotonic()

        # 标准PID计算
        output = self.pid.compute(measurement, timestamp)

        # 计算误差
        error = self.config.base_config.setpoint - measurement

        # 检测振荡
        current_sign = 1 if error > 0 else (-1 if error < 0 else 0)
        if self._prev_error_sign != 0 and current_sign != 0:
            if current_sign != self._prev_error_sign:
                self._oscillation_counter += 1
        self._prev_error_sign = current_sign

        # 记录性能历史
        self._performance_history.append(
            {
                "error": error,
                "abs_error": abs(error),
                "output": output,
                "timestamp": timestamp,
            }
        )
        self._sample_count += 1

        # 限制历史大小
        while len(self._performance_history) > self.config.history_size:
            self._performance_history.pop(0)

        # 定期自动整定
        if (
            self.config.tuning_enabled
            and self._sample_count % self.config.tuning_interval == 0
            and len(self._performance_history) >= self.config.tuning_interval
        ):
            self._auto_tune()

        return output

    def _auto_tune(self) -> Optional[TuningResult]:
        """执行自动参数整定

        基于最近的性能数据，分析并调整PID参数。

        Returns:
            整定结果，如果未执行整定则返回None
        """
        # 提取最近 N 个样本
        history = self._performance_history[-self.config.tuning_interval :]
        if not history:
            return None

        errors = [h["abs_error"] for h in history]
        raw_errors = [h["error"] for h in history]

        # 计算性能指标
        n = len(errors)
        avg_error = sum(errors) / n
        error_std = math.sqrt(
            sum((e - avg_error) ** 2 for e in errors) / n
        )

        # 计算误差变化趋势
        first_half = errors[: n // 2]
        second_half = errors[n // 2 :]
        trend = (sum(second_half) / len(second_half)) - (
            sum(first_half) / len(first_half)
        )

        # 振荡检测：统计过零次数
        zero_crossings = sum(
            1
            for i in range(1, len(raw_errors))
            if raw_errors[i] * raw_errors[i - 1] < 0
        )
        oscillation_ratio = zero_crossings / n if n > 0 else 0

        prev_kp = self.pid.config.kp
        prev_ki = self.pid.config.ki
        prev_kd = self.pid.config.kd

        metrics: Dict[str, float] = {
            "avg_error": avg_error,
            "error_std": error_std,
            "trend": trend,
            "oscillation_ratio": oscillation_ratio,
            "zero_crossings": zero_crossings,
            "sample_count": n,
        }

        reason_parts: List[str] = []

        # --- 调整策略 ---

        # 1. 稳态误差控制 - 调整 Ki
        if avg_error > self.config.error_threshold * 10:
            # 稳态误差大 -> 增加Ki
            ki_delta = self.config.learning_rate * avg_error * 0.5
            self.pid.config.ki = self._clamp_gain(
                self.pid.config.ki + ki_delta
            )
            reason_parts.append(f"增加Ki: avg_error={avg_error:.4f}")
        elif avg_error < self.config.error_threshold:
            # 稳态误差小 -> 轻微减小Ki防过积分
            self.pid.config.ki = self._clamp_gain(
                self.pid.config.ki * (1 - self.config.learning_rate * 0.1)
            )
            reason_parts.append(f"微调Ki: avg_error={avg_error:.4f}")

        # 2. 振荡控制 - 调整 Kd 和 Kp
        if oscillation_ratio > self.config.oscillation_threshold:
            # 振荡 -> 增加Kd抑制振荡, 减小Kp
            self.pid.config.kd = self._clamp_gain(
                self.pid.config.kd * (1 + self.config.learning_rate)
            )
            self.pid.config.kp = self._clamp_gain(
                self.pid.config.kp * (1 - self.config.learning_rate * 0.3)
            )
            reason_parts.append(
                f"抑制振荡: oscillation_ratio={oscillation_ratio:.3f}"
            )
        elif oscillation_ratio < 0.05 and error_std < self.config.error_threshold:
            # 过于稳定 -> 减小Kd
            self.pid.config.kd = self._clamp_gain(
                self.pid.config.kd * (1 - self.config.learning_rate * 0.2)
            )

        # 3. 响应速度控制 - 调整 Kp
        if avg_error > self.config.error_threshold and oscillation_ratio < 0.1:
            # 响应不足 -> 增加Kp
            self.pid.config.kp = self._clamp_gain(
                self.pid.config.kp * (1 + self.config.learning_rate * 0.2)
            )
            if not reason_parts:
                reason_parts.append(f"提高响应: avg_error={avg_error:.4f}")

        # 4. 趋势响应
        if trend > self.config.error_threshold:
            # 误差增大趋势 -> 增加Kp
            self.pid.config.kp = self._clamp_gain(
                self.pid.config.kp * (1 + self.config.learning_rate * 0.3)
            )
            reason_parts.append(f"响应趋势恶化: trend={trend:.4f}")

        # 创建整定结果
        new_gains = (self.pid.config.kp, self.pid.config.ki, self.pid.config.kd)
        result = TuningResult(
            timestamp=time.monotonic(),
            previous_gains=(prev_kp, prev_ki, prev_kd),
            new_gains=new_gains,
            reason="; ".join(reason_parts) if reason_parts else "无显著变化",
            metrics=metrics,
        )
        self._tuning_history.append(result)

        # 重置振荡计数器
        self._oscillation_counter = 0

        return result

    def _clamp_gain(self, value: float) -> float:
        """将增益值限制在配置的范围内

        Args:
            value: 增益值

        Returns:
            钳位后的增益值
        """
        return max(self.config.min_gain, min(self.config.max_gain, value))

    def force_tune(self) -> TuningResult:
        """强制执行一次参数整定

        Returns:
            整定结果
        """
        return self._auto_tune()

    def update_setpoint(self, setpoint: float) -> None:
        """更新设定点

        更新设定点并重置积分项以避免设定点变更导致的过冲。

        Args:
            setpoint: 新的目标值
        """
        self.config.base_config.setpoint = setpoint
        self.pid.update_setpoint(setpoint)
        # 设定点大幅变更时重置积分，避免windup
        self.pid._integral = 0.0

    def get_performance_metrics(self) -> Dict[str, float]:
        """获取当前性能指标

        Returns:
            性能指标字典
        """
        if not self._performance_history:
            return {
                "avg_error": 0.0,
                "error_std": 0.0,
                "max_error": 0.0,
                "sample_count": 0,
            }

        errors = [h["abs_error"] for h in self._performance_history]
        n = len(errors)
        avg = sum(errors) / n
        std = math.sqrt(sum((e - avg) ** 2 for e in errors) / n) if n > 1 else 0.0

        return {
            "avg_error": avg,
            "error_std": std,
            "max_error": max(errors),
            "min_error": min(errors),
            "sample_count": n,
            "tuning_count": self.tuning_count,
            "oscillation_counter": self._oscillation_counter,
        }

    def get_tuning_history(self) -> List[Dict[str, Any]]:
        """获取自动整定历史

        Returns:
            整定历史记录列表
        """
        return [
            {
                "timestamp": r.timestamp,
                "previous_kp": r.previous_gains[0],
                "previous_ki": r.previous_gains[1],
                "previous_kd": r.previous_gains[2],
                "new_kp": r.new_gains[0],
                "new_ki": r.new_gains[1],
                "new_kd": r.new_gains[2],
                "reason": r.reason,
                "metrics": r.metrics,
            }
            for r in self._tuning_history
        ]

    def get_state(self) -> Dict:
        """获取控制器完整状态"""
        return {
            "pid_state": self.pid.get_state(),
            "pid_config": {
                "kp": self.pid.config.kp,
                "ki": self.pid.config.ki,
                "kd": self.pid.config.kd,
                "setpoint": self.pid.config.setpoint,
            },
            "sample_count": self._sample_count,
            "tuning_count": self.tuning_count,
            "oscillation_counter": self._oscillation_counter,
            "history_size": len(self._performance_history),
            "performance": self.get_performance_metrics(),
        }
