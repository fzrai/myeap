"""自适应控制数据模型

定义控制模块使用的所有数据结构，包括控制模式、控制回路配置、
控制动作、控制回路状态和统计信息。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ControlMode(str, Enum):
    """控制模式枚举

    支持的控制策略类型：
    - PID: 经典PID反馈控制
    - ADAPTIVE: 自适应参数调谐控制
    - FEEDFORWARD: 前馈开环补偿控制
    - CASCADE: 级联控制 (PID + 前馈)
    - MANUAL: 手动控制模式
    - AUTO_TUNE: 自动整定模式
    """

    PID = "pid"
    ADAPTIVE = "adaptive"
    FEEDFORWARD = "feedforward"
    CASCADE = "cascade"
    MANUAL = "manual"
    AUTO_TUNE = "auto_tune"

    @property
    def description(self) -> str:
        """获取控制模式描述"""
        descriptions = {
            ControlMode.PID: "PID反馈控制",
            ControlMode.ADAPTIVE: "自适应参数调谐控制",
            ControlMode.FEEDFORWARD: "前馈开环补偿控制",
            ControlMode.CASCADE: "级联控制 (PID + 前馈)",
            ControlMode.MANUAL: "手动控制模式",
            ControlMode.AUTO_TUNE: "自动整定模式",
        }
        return descriptions.get(self, self.value)

    @property
    def is_automatic(self) -> bool:
        """是否为自动控制模式"""
        return self in (
            ControlMode.PID,
            ControlMode.ADAPTIVE,
            ControlMode.FEEDFORWARD,
            ControlMode.CASCADE,
        )

    @property
    def is_feedback(self) -> bool:
        """是否包含反馈控制"""
        return self in (
            ControlMode.PID,
            ControlMode.ADAPTIVE,
            ControlMode.CASCADE,
        )


class TuningMethod(str, Enum):
    """参数整定方法枚举

    支持的整定方法：
    - ZIEGLER_NICHOLS: Ziegler-Nichols临界比例法
    - IMC: 内模控制整定法
    - COHEN_COON: Cohen-Coon整定法
    - ADAPTIVE: 在线自适应整定
    - MANUAL: 手动设定参数
    """

    ZIEGLER_NICHOLS = "ziegler_nichols"
    IMC = "imc"
    COHEN_COON = "cohen_coon"
    ADAPTIVE = "adaptive"
    MANUAL = "manual"

    @property
    def description(self) -> str:
        """获取整定方法描述"""
        descriptions = {
            TuningMethod.ZIEGLER_NICHOLS: "Ziegler-Nichols临界比例法",
            TuningMethod.IMC: "内模控制整定法",
            TuningMethod.COHEN_COON: "Cohen-Coon整定法",
            TuningMethod.ADAPTIVE: "在线自适应整定",
            TuningMethod.MANUAL: "手动设定参数",
        }
        return descriptions.get(self, self.value)


class ControlLoopState(str, Enum):
    """控制回路状态"""

    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    TUNING = "tuning"
    FAULT = "fault"
    STOPPED = "stopped"

    @property
    def is_active(self) -> bool:
        """是否为活跃状态"""
        return self in (ControlLoopState.RUNNING, ControlLoopState.TUNING)

    @property
    def is_terminal(self) -> bool:
        """是否为终态"""
        return self == ControlLoopState.STOPPED


class ControlLoopConfig(BaseModel):
    """控制回路配置

    定义单个控制回路的所有配置参数。

    Attributes:
        loop_id: 回路唯一标识
        equipment_id: 设备ID
        parameter: 被控参数名称
        unit: 参数单位
        control_mode: 控制模式
        setpoint: 目标值（设定点）
        kp: 比例增益
        ki: 积分增益
        kd: 微分增益
        output_min: 输出下限
        output_max: 输出上限
        anti_windup: 是否启用抗积分饱和
        derivative_filter: 微分低通滤波系数 (0-1)
        sampling_interval: 采样间隔（秒）
        deadband: 死区范围（避免频繁调节）
        feedforward_params: 前馈参数列表
        tuning_method: 整定方法
        auto_tune_enabled: 是否启用自动整定
        auto_tune_interval: 自动整定周期（样本数）
        metadata: 附加元数据
    """

    loop_id: str = Field(description="回路唯一标识")
    equipment_id: str = Field(description="设备ID")
    parameter: str = Field(description="被控参数名称")
    unit: str = Field(default="", description="参数单位")

    # 控制参数
    control_mode: ControlMode = Field(
        default=ControlMode.PID, description="控制模式"
    )
    setpoint: float = Field(default=0.0, description="目标设定点")

    # PID参数
    kp: float = Field(default=1.0, ge=0.0, description="比例增益")
    ki: float = Field(default=0.0, ge=0.0, description="积分增益")
    kd: float = Field(default=0.0, ge=0.0, description="微分增益")

    # 输出约束
    output_min: Optional[float] = Field(default=None, description="输出下限")
    output_max: Optional[float] = Field(default=None, description="输出上限")
    anti_windup: bool = Field(default=True, description="是否启用抗积分饱和")
    derivative_filter: float = Field(
        default=0.1, ge=0.0, le=1.0, description="微分滤波器系数"
    )

    # 采样与控制
    sampling_interval: float = Field(
        default=0.1, gt=0.0, description="采样间隔（秒）"
    )
    deadband: float = Field(default=0.0, ge=0.0, description="死区范围")

    # 前馈参数
    feedforward_params: List[Dict[str, Any]] = Field(
        default_factory=list, description="前馈参数列表"
    )

    # 整定配置
    tuning_method: TuningMethod = Field(
        default=TuningMethod.ADAPTIVE, description="整定方法"
    )
    auto_tune_enabled: bool = Field(
        default=False, description="是否启用自动整定"
    )
    auto_tune_interval: int = Field(
        default=100, ge=10, description="自动整定周期（样本数）"
    )

    # 附加信息
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="附加元数据"
    )

    def to_pid_config(self) -> "PIDConfig":
        """转换为PIDConfig"""
        from myeap.control.pid import PIDConfig

        return PIDConfig(
            kp=self.kp,
            ki=self.ki,
            kd=self.kd,
            setpoint=self.setpoint,
            output_min=self.output_min,
            output_max=self.output_max,
            anti_windup=self.anti_windup,
            derivative_filter=self.derivative_filter,
            deadband=self.deadband,
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "loop_id": self.loop_id,
            "equipment_id": self.equipment_id,
            "parameter": self.parameter,
            "unit": self.unit,
            "control_mode": self.control_mode.value,
            "setpoint": self.setpoint,
            "kp": self.kp,
            "ki": self.ki,
            "kd": self.kd,
            "output_min": self.output_min,
            "output_max": self.output_max,
            "anti_windup": self.anti_windup,
            "derivative_filter": self.derivative_filter,
            "sampling_interval": self.sampling_interval,
            "deadband": self.deadband,
            "feedforward_params": self.feedforward_params,
            "tuning_method": self.tuning_method.value,
            "auto_tune_enabled": self.auto_tune_enabled,
            "auto_tune_interval": self.auto_tune_interval,
            "metadata": self.metadata,
        }


class ControlAction(BaseModel):
    """控制动作

    表示控制器计算出的一个控制动作。

    Attributes:
        action_id: 动作唯一标识
        loop_id: 所属回路ID
        timestamp: 动作时间
        setpoint: 当前设定点
        measurement: 当前测量值
        error: 当前误差
        output: 控制输出值
        p_term: 比例项贡献
        i_term: 积分项贡献
        d_term: 微分项贡献
        ff_term: 前馈项贡献
        control_mode: 当前控制模式
        saturated: 是否发生输出饱和
        metadata: 附加数据
    """

    action_id: str = Field(description="动作唯一标识")
    loop_id: str = Field(description="所属回路ID")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="动作时间"
    )

    setpoint: float = Field(description="设定点")
    measurement: float = Field(description="测量值")
    error: float = Field(description="误差值")
    output: float = Field(default=0.0, description="控制输出值")

    p_term: float = Field(default=0.0, description="比例项")
    i_term: float = Field(default=0.0, description="积分项")
    d_term: float = Field(default=0.0, description="微分项")
    ff_term: float = Field(default=0.0, description="前馈项")

    control_mode: ControlMode = Field(
        default=ControlMode.PID, description="控制模式"
    )
    saturated: bool = Field(default=False, description="是否发生输出饱和")

    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="附加数据"
    )

    @property
    def total_output(self) -> float:
        """总控制输出 (P + I + D + FF)"""
        return self.p_term + self.i_term + self.d_term + self.ff_term

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "action_id": self.action_id,
            "loop_id": self.loop_id,
            "timestamp": self.timestamp.isoformat(),
            "setpoint": self.setpoint,
            "measurement": self.measurement,
            "error": self.error,
            "output": self.output,
            "p_term": self.p_term,
            "i_term": self.i_term,
            "d_term": self.d_term,
            "ff_term": self.ff_term,
            "control_mode": self.control_mode.value,
            "saturated": self.saturated,
            "metadata": self.metadata,
        }


class ControlLoopStats(BaseModel):
    """控制回路统计信息

    记录控制回路的性能统计。

    Attributes:
        loop_id: 回路ID
        total_actions: 总控制动作数
        mean_error: 平均误差
        std_error: 误差标准差
        max_abs_error: 最大绝对误差
        min_abs_error: 最小绝对误差
        i_term_accumulated: 积分项累计
        saturation_count: 输出饱和次数
        tuning_count: 自动整定次数
        last_action_time: 最后一次动作时间
        avg_output: 平均输出值
        setpoint_changes: 设定点变更次数
    """

    loop_id: str = Field(description="回路ID")
    total_actions: int = Field(default=0, description="总控制动作数")
    mean_error: float = Field(default=0.0, description="平均误差")
    std_error: float = Field(default=0.0, description="误差标准差")
    max_abs_error: float = Field(default=0.0, description="最大绝对误差")
    min_abs_error: float = Field(
        default=float("inf"), description="最小绝对误差"
    )
    i_term_accumulated: float = Field(default=0.0, description="积分项累计")
    saturation_count: int = Field(default=0, description="输出饱和次数")
    tuning_count: int = Field(default=0, description="自动整定次数")
    last_action_time: Optional[datetime] = Field(
        default=None, description="最后一次动作时间"
    )
    avg_output: float = Field(default=0.0, description="平均输出值")
    setpoint_changes: int = Field(default=0, description="设定点变更次数")

    @property
    def overshoot_index(self) -> float:
        """超调指标 (误差标准差 / 平均误差，越小越好)"""
        if self.mean_error == 0:
            return 0.0
        return self.std_error / abs(self.mean_error) if self.mean_error != 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "loop_id": self.loop_id,
            "total_actions": self.total_actions,
            "mean_error": self.mean_error,
            "std_error": self.std_error,
            "max_abs_error": self.max_abs_error,
            "min_abs_error": self.min_abs_error,
            "i_term_accumulated": self.i_term_accumulated,
            "saturation_count": self.saturation_count,
            "tuning_count": self.tuning_count,
            "last_action_time": self.last_action_time.isoformat()
            if self.last_action_time
            else None,
            "avg_output": self.avg_output,
            "setpoint_changes": self.setpoint_changes,
            "overshoot_index": self.overshoot_index,
        }
