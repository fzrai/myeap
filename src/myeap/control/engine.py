"""过程控制引擎

综合控制引擎，将PID、自适应、前馈等多种控制策略组合为
完整的控制回路管理系统。

支持：
- 多回路并发管理
- 控制模式切换
- 控制性能监控
- 安全保护（输出限幅、故障检测）
- 控制回路生命周期管理
"""

import asyncio
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from myeap.control.adaptive import AdaptiveConfig, AdaptiveController
from myeap.control.feedforward import FeedforwardController
from myeap.control.models import (
    ControlAction,
    ControlLoopConfig,
    ControlLoopState,
    ControlLoopStats,
    ControlMode,
)
from myeap.control.pid import PIDConfig, PIDController


class ControlLoop:
    """控制回路

    表示一个运行中的控制回路，包含控制器、统计信息和任务引用。
    """

    def __init__(
        self,
        config: ControlLoopConfig,
        controller: object,
        feedforward: Optional[FeedforwardController] = None,
    ):
        self.config = config
        self.controller = controller
        self.feedforward = feedforward
        self.state: ControlLoopState = ControlLoopState.CREATED
        self.stats = ControlLoopStats(loop_id=config.loop_id)
        self._task: Optional[asyncio.Task] = None
        self._created_at: float = time.monotonic()
        self._error: Optional[str] = None

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self.state == ControlLoopState.RUNNING

    @property
    def task(self) -> Optional[asyncio.Task]:
        """获取控制回路的异步任务"""
        return self._task

    def update_stats(self, action: ControlAction) -> None:
        """更新回路统计信息

        Args:
            action: 控制动作
        """
        self.stats.total_actions += 1
        self.stats.last_action_time = action.timestamp

        # 更新误差统计
        abs_error = abs(action.error)
        n = self.stats.total_actions

        # 在线更新均值和标准差 (Welford's method)
        old_mean = self.stats.mean_error
        self.stats.mean_error = old_mean + (action.error - old_mean) / n
        self.stats.std_error = None  # Reset, compute on demand

        if abs_error > self.stats.max_abs_error:
            self.stats.max_abs_error = abs_error
        if abs_error < self.stats.min_abs_error:
            self.stats.min_abs_error = abs_error

        if action.saturated:
            self.stats.saturation_count += 1

        # 更新积分项累计
        self.stats.i_term_accumulated += action.i_term

        # 更新平均输出
        self.stats.avg_output = (
            self.stats.avg_output * (n - 1) + action.output
        ) / n

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "loop_id": self.config.loop_id,
            "equipment_id": self.config.equipment_id,
            "parameter": self.config.parameter,
            "state": self.state.value,
            "control_mode": self.config.control_mode.value,
            "setpoint": self.config.setpoint,
            "stats": self.stats.to_dict(),
            "created_at": self._created_at,
            "error": self._error,
        }


class ProcessControlEngine:
    """过程控制引擎

    综合控制引擎，管理所有控制回路，组合多种控制策略。

    特性：
    - 多回路管理：同时运行多个独立控制回路
    - 策略组合：PID + 自适应 + 前馈的灵活组合
    - 安全保护：输出限幅、故障检测、异常处理
    - 性能监控：实时统计控制性能指标

    Example:
        >>> engine = ProcessControlEngine()
        >>> config = ControlLoopConfig(
        ...     loop_id="temp_loop_1",
        ...     equipment_id="eq-001",
        ...     parameter="temperature",
        ...     setpoint=300.0,
        ...     kp=2.0, ki=0.5, kd=0.1,
        ... )
        >>> engine.create_control_loop(config)
        >>> engine.start_loop("eq-001", "temperature", reader_func, writer_func)
    """

    def __init__(self):
        # (equipment_id, parameter) -> ControlLoop
        self._loops: Dict[Tuple[str, str], ControlLoop] = {}
        # 回路活跃任务
        self._running_tasks: Dict[Tuple[str, str], asyncio.Task] = {}
        # 动作历史（最近N条）
        self._action_history: List[ControlAction] = []
        self._max_action_history: int = 10000

    def create_control_loop(self, config: ControlLoopConfig) -> ControlLoop:
        """创建控制回路

        Args:
            config: 回路配置

        Returns:
            创建的ControlLoop实例

        Raises:
            ValueError: 相同设备:参数的回回路已存在
        """
        key = (config.equipment_id, config.parameter)
        if key in self._loops:
            raise ValueError(
                f"Control loop for {config.equipment_id}:{config.parameter} "
                f"already exists"
            )

        # 创建控制器
        controller = self._create_controller(config)

        # 创建前馈控制器
        feedforward = None
        if config.control_mode in (
            ControlMode.FEEDFORWARD,
            ControlMode.CASCADE,
        ):
            feedforward = FeedforwardController()
            for ff_param in config.feedforward_params:
                feedforward.add_model(
                    parameter=ff_param.get("name", ff_param.get("parameter", "")),
                    gain=ff_param.get("gain", 1.0),
                    time_constant=ff_param.get("time_constant", 0.0),
                    dead_time=ff_param.get("dead_time", 0.0),
                )

        loop = ControlLoop(
            config=config,
            controller=controller,
            feedforward=feedforward,
        )
        self._loops[key] = loop
        return loop

    def _create_controller(self, config: ControlLoopConfig) -> object:
        """根据配置创建对应的控制器

        根据控制模式自动选择控制器类型。
        """
        pid_config = config.to_pid_config()

        if config.control_mode == ControlMode.ADAPTIVE:
            adapt_config = AdaptiveConfig(
                base_config=pid_config,
                tuning_enabled=config.auto_tune_enabled,
                tuning_interval=config.auto_tune_interval,
            )
            return AdaptiveController(adapt_config)
        else:
            return PIDController(pid_config)

    def remove_control_loop(self, equipment_id: str, parameter: str) -> bool:
        """移除控制回路

        Args:
            equipment_id: 设备ID
            parameter: 参数名称

        Returns:
            是否成功移除
        """
        key = (equipment_id, parameter)
        loop = self._loops.pop(key, None)
        if loop and key in self._running_tasks:
            task = self._running_tasks.pop(key)
            task.cancel()
        return loop is not None

    def get_loop(
        self, equipment_id: str, parameter: str
    ) -> Optional[ControlLoop]:
        """获取控制回路

        Args:
            equipment_id: 设备ID
            parameter: 参数名称

        Returns:
            ControlLoop实例或None
        """
        return self._loops.get((equipment_id, parameter))

    def list_loops(self) -> List[ControlLoop]:
        """列出所有控制回路"""
        return list(self._loops.values())

    def list_active_loops(self) -> List[ControlLoop]:
        """列出所有活跃的控制回路"""
        return [
            loop
            for loop in self._loops.values()
            if loop.state.is_active
        ]

    def start_loop(
        self,
        equipment_id: str,
        parameter: str,
        reader: Callable[[str, str], Any],
        writer: Callable[[str, str, float], Any],
        interval: float = 0.1,
    ) -> asyncio.Task:
        """启动控制回路

        启动后会持续执行：读取 -> 计算 -> 写入 的循环。

        Args:
            equipment_id: 设备ID
            parameter: 参数名称
            reader: 异步读取函数，签名为 async def(equipment_id, parameter) -> float
            writer: 异步写入函数，签名为 async def(equipment_id, parameter, value) -> None
            interval: 控制循环间隔（秒）

        Returns:
            控制回路的异步Task

        Raises:
            ValueError: 回路不存在
        """
        loop = self.get_loop(equipment_id, parameter)
        if not loop:
            raise ValueError(
                f"No control loop found for {equipment_id}:{parameter}"
            )

        key = (equipment_id, parameter)

        # 取消已有任务
        if key in self._running_tasks:
            existing = self._running_tasks[key]
            if not existing.done():
                existing.cancel()

        async def _control_loop():
            loop.state = ControlLoopState.RUNNING
            loop._error = None

            while loop.state.is_active:
                try:
                    # 读取当前测量值
                    value = await reader(equipment_id, parameter)

                    # 获取前馈补偿
                    ff_correction = 0.0
                    if loop.feedforward and loop.config.feedforward_params:
                        disturbance_data = {}
                        for ff_param in loop.config.feedforward_params:
                            param_name = ff_param.get(
                                "name", ff_param.get("parameter", "")
                            )
                            if param_name:
                                try:
                                    dist_value = await reader(
                                        equipment_id, param_name
                                    )
                                except Exception:
                                    dist_value = 0.0
                                disturbance_data[param_name] = dist_value
                        ff_correction = loop.feedforward.compute(disturbance_data)

                    # 计算控制输出
                    if isinstance(loop.controller, AdaptiveController):
                        raw_output = loop.controller.compute(
                            value - ff_correction
                        )
                    else:
                        raw_output = loop.controller.compute(value)

                    # 加上前馈补偿
                    total_output = raw_output + ff_correction

                    # 应用输出限幅
                    if loop.config.output_min is not None:
                        total_output = max(total_output, loop.config.output_min)
                    if loop.config.output_max is not None:
                        total_output = min(total_output, loop.config.output_max)

                    # 记录控制动作
                    error = loop.config.setpoint - value
                    action_id = str(uuid.uuid4())[:8]

                    # 提取PID各分量
                    if isinstance(loop.controller, AdaptiveController):
                        pid = loop.controller.pid
                    else:
                        pid = loop.controller

                    p_term = pid.config.kp * error if hasattr(pid, 'config') else 0.0
                    i_term = getattr(pid, '_integral', 0.0) * pid.config.ki if hasattr(pid, 'config') else 0.0
                    d_term = total_output - raw_output - ff_correction - p_term - i_term

                    action = ControlAction(
                        action_id=action_id,
                        loop_id=loop.config.loop_id,
                        setpoint=loop.config.setpoint,
                        measurement=value,
                        error=error,
                        output=total_output,
                        p_term=p_term if abs(p_term) > 1e-10 else 0.0,
                        i_term=i_term if abs(i_term) > 1e-10 else 0.0,
                        d_term=0.0,
                        ff_term=ff_correction,
                        control_mode=loop.config.control_mode,
                        saturated=_is_saturated(pid),
                    )

                    # 更新统计
                    loop.update_stats(action)

                    # 记录历史
                    self._action_history.append(action)
                    while len(self._action_history) > self._max_action_history:
                        self._action_history.pop(0)

                    # 应用控制输出
                    test_value = value + total_output  # 反馈校正后的目标值
                    await writer(equipment_id, parameter, test_value)

                    # 等待下次采样
                    await asyncio.sleep(interval)

                except asyncio.CancelledError:
                    loop.state = ControlLoopState.STOPPED
                    break
                except Exception as e:
                    loop._error = str(e)
                    loop.state = ControlLoopState.FAULT
                    # 继续尝试恢复
                    await asyncio.sleep(interval)

        task = asyncio.create_task(_control_loop())
        loop._task = task
        self._running_tasks[key] = task
        return task

    async def stop_loop(self, equipment_id: str, parameter: str) -> bool:
        """停止控制回路

        Args:
            equipment_id: 设备ID
            parameter: 参数名称

        Returns:
            是否成功停止
        """
        key = (equipment_id, parameter)
        loop = self._loops.get(key)
        task = self._running_tasks.pop(key, None)

        if loop:
            loop.state = ControlLoopState.STOPPED

        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        return loop is not None or task is not None

    async def stop_all(self):
        """停止所有控制回路"""
        keys = list(self._running_tasks.keys())
        for key in keys:
            equipment_id, parameter = key
            await self.stop_loop(equipment_id, parameter)

    def pause_loop(self, equipment_id: str, parameter: str) -> bool:
        """暂停控制回路

        Args:
            equipment_id: 设备ID
            parameter: 参数名称

        Returns:
            是否成功暂停
        """
        loop = self.get_loop(equipment_id, parameter)
        if loop and loop.state == ControlLoopState.RUNNING:
            loop.state = ControlLoopState.PAUSED
            return True
        return False

    def resume_loop(self, equipment_id: str, parameter: str) -> bool:
        """恢复控制回路

        注意：只恢复状态，不重新启动任务。需要调用start_loop重启。

        Args:
            equipment_id: 设备ID
            parameter: 参数名称

        Returns:
            是否成功恢复
        """
        loop = self.get_loop(equipment_id, parameter)
        if loop and loop.state == ControlLoopState.PAUSED:
            loop.state = ControlLoopState.RUNNING
            return True
        return False

    def update_setpoint(
        self, equipment_id: str, parameter: str, setpoint: float
    ) -> bool:
        """更新回路设定点

        Args:
            equipment_id: 设备ID
            parameter: 参数名称
            setpoint: 新的设定点

        Returns:
            是否成功更新
        """
        loop = self.get_loop(equipment_id, parameter)
        if loop:
            loop.config.setpoint = setpoint
            if isinstance(loop.controller, AdaptiveController):
                loop.controller.update_setpoint(setpoint)
            elif isinstance(loop.controller, PIDController):
                loop.controller.update_setpoint(setpoint)
            loop.stats.setpoint_changes += 1
            return True
        return False

    def get_stats(
        self, equipment_id: str, parameter: str
    ) -> Optional[ControlLoopStats]:
        """获取回路统计信息

        Args:
            equipment_id: 设备ID
            parameter: 参数名称

        Returns:
            ControlLoopStats 或 None
        """
        loop = self.get_loop(equipment_id, parameter)
        return loop.stats if loop else None

    def get_recent_actions(self, n: int = 100) -> List[ControlAction]:
        """获取最近的控制动作

        Args:
            n: 返回动作数量

        Returns:
            控制动作列表
        """
        return self._action_history[-n:]

    def get_actions_by_loop(
        self, loop_id: str, n: int = 100
    ) -> List[ControlAction]:
        """获取指定回路的控制动作

        Args:
            loop_id: 回路ID
            n: 返回动作数量

        Returns:
            控制动作列表
        """
        matching = [a for a in self._action_history if a.loop_id == loop_id]
        return matching[-n:]

    def get_state(self) -> Dict[str, Any]:
        """获取引擎状态概要

        Returns:
            状态字典
        """
        total_loops = len(self._loops)
        active_loops = sum(
            1 for l in self._loops.values() if l.state.is_active
        )
        fault_loops = sum(
            1 for l in self._loops.values() if l.state == ControlLoopState.FAULT
        )

        return {
            "total_loops": total_loops,
            "active_loops": active_loops,
            "fault_loops": fault_loops,
            "paused_loops": sum(
                1
                for l in self._loops.values()
                if l.state == ControlLoopState.PAUSED
            ),
            "actions_recorded": len(self._action_history),
            "loops": [loop.to_dict() for loop in self._loops.values()],
        }


def _is_saturated(pid: PIDController) -> bool:
    """检查PID控制器是否处于饱和状态"""
    if hasattr(pid, "_saturated"):
        return pid._saturated
    return False
