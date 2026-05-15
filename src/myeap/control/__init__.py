"""自适应控制 (Adaptive Control) 模块

半导体制造过程的自适应过程控制引擎，提供PID控制、自适应参数整定、
前馈补偿和完整的过程控制回路的综合控制能力。

主要功能：
- PID控制器 (含抗积分饱和、低通滤波微分项)
- 自适应控制器 (基于系统响应的自动参数整定)
- 前馈控制器 (针对已知扰动的补偿)
- 过程控制引擎 (组合多种控制策略的完整控制回路)

控制策略：
- PID: 比例-积分-微分控制，经典反馈控制
- Adaptive: 自适应调谐，根据性能指标自动优化PID参数
- Feedforward: 前馈补偿，针对已知扰动的开环补偿
- Cascade: 级联控制，通过控制引擎组合多种策略

Example:
    >>> from myeap.control import PIDController, PIDConfig
    >>> config = PIDConfig(kp=2.0, ki=0.5, kd=0.1, setpoint=100.0)
    >>> pid = PIDController(config)
    >>> output = pid.compute(95.0)  # measurement below setpoint
"""

from myeap.control.models import (
    ControlMode,
    ControlLoopConfig,
    ControlAction,
    ControlLoopState,
    ControlLoopStats,
    TuningMethod,
)
from myeap.control.pid import (
    PIDConfig,
    PIDController,
    CascadePIDController,
)
from myeap.control.feedforward import (
    FeedforwardController,
    FeedforwardModel,
    AdaptiveFeedforwardController,
)
from myeap.control.adaptive import (
    AdaptiveConfig,
    AdaptiveController,
    TuningResult,
)
from myeap.control.engine import (
    ProcessControlEngine,
    ControlLoop,
)

__all__ = [
    # Models
    "ControlMode",
    "ControlLoopConfig",
    "ControlAction",
    "ControlLoopState",
    "ControlLoopStats",
    "TuningMethod",
    # PID
    "PIDConfig",
    "PIDController",
    "CascadePIDController",
    # Feedforward
    "FeedforwardController",
    "FeedforwardModel",
    "AdaptiveFeedforwardController",
    # Adaptive
    "AdaptiveConfig",
    "AdaptiveController",
    "TuningResult",
    # Engine
    "ProcessControlEngine",
    "ControlLoop",
]

__version__ = "1.0.0"
