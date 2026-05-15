"""控制模型测试

测试ControlMode、ControlLoopConfig、ControlAction、ControlLoopState、
ControlLoopStats、TuningMethod等模型。
"""

import unittest
from datetime import datetime
from myeap.control.models import (
    ControlMode,
    ControlLoopConfig,
    ControlAction,
    ControlLoopState,
    ControlLoopStats,
    TuningMethod,
)


class TestControlMode(unittest.TestCase):
    """测试控制模式枚举"""

    def test_control_mode_values(self):
        """测试控制模式值"""
        self.assertEqual(ControlMode.PID.value, "pid")
        self.assertEqual(ControlMode.ADAPTIVE.value, "adaptive")
        self.assertEqual(ControlMode.FEEDFORWARD.value, "feedforward")
        self.assertEqual(ControlMode.CASCADE.value, "cascade")
        self.assertEqual(ControlMode.MANUAL.value, "manual")
        self.assertEqual(ControlMode.AUTO_TUNE.value, "auto_tune")

    def test_control_mode_is_automatic(self):
        """测试自动控制模式判断"""
        self.assertTrue(ControlMode.PID.is_automatic)
        self.assertTrue(ControlMode.ADAPTIVE.is_automatic)
        self.assertTrue(ControlMode.FEEDFORWARD.is_automatic)
        self.assertTrue(ControlMode.CASCADE.is_automatic)
        self.assertFalse(ControlMode.MANUAL.is_automatic)
        self.assertFalse(ControlMode.AUTO_TUNE.is_automatic)

    def test_control_mode_is_feedback(self):
        """测试反馈控制模式判断"""
        self.assertTrue(ControlMode.PID.is_feedback)
        self.assertTrue(ControlMode.ADAPTIVE.is_feedback)
        self.assertFalse(ControlMode.FEEDFORWARD.is_feedback)
        self.assertTrue(ControlMode.CASCADE.is_feedback)
        self.assertFalse(ControlMode.MANUAL.is_feedback)

    def test_control_mode_descriptions(self):
        """测试控制模式描述"""
        self.assertIn("PID", ControlMode.PID.description)
        self.assertIn("自适应", ControlMode.ADAPTIVE.description)
        self.assertIn("前馈", ControlMode.FEEDFORWARD.description)


class TestTuningMethod(unittest.TestCase):
    """测试参数整定方法枚举"""

    def test_tuning_method_values(self):
        """测试整定方法值"""
        self.assertEqual(TuningMethod.ZIEGLER_NICHOLS.value, "ziegler_nichols")
        self.assertEqual(TuningMethod.IMC.value, "imc")
        self.assertEqual(TuningMethod.COHEN_COON.value, "cohen_coon")
        self.assertEqual(TuningMethod.ADAPTIVE.value, "adaptive")
        self.assertEqual(TuningMethod.MANUAL.value, "manual")

    def test_tuning_method_descriptions(self):
        """测试整定方法描述"""
        self.assertIn("Ziegler", TuningMethod.ZIEGLER_NICHOLS.description)
        self.assertIn("内模", TuningMethod.IMC.description)
        self.assertIn("Cohen", TuningMethod.COHEN_COON.description)


class TestControlLoopState(unittest.TestCase):
    """测试控制回路状态"""

    def test_control_loop_state_values(self):
        """测试状态值"""
        self.assertEqual(ControlLoopState.CREATED.value, "created")
        self.assertEqual(ControlLoopState.RUNNING.value, "running")
        self.assertEqual(ControlLoopState.PAUSED.value, "paused")
        self.assertEqual(ControlLoopState.TUNING.value, "tuning")
        self.assertEqual(ControlLoopState.FAULT.value, "fault")
        self.assertEqual(ControlLoopState.STOPPED.value, "stopped")

    def test_is_active(self):
        """测试活跃状态判断"""
        self.assertTrue(ControlLoopState.RUNNING.is_active)
        self.assertTrue(ControlLoopState.TUNING.is_active)
        self.assertFalse(ControlLoopState.CREATED.is_active)
        self.assertFalse(ControlLoopState.PAUSED.is_active)
        self.assertFalse(ControlLoopState.STOPPED.is_active)

    def test_is_terminal(self):
        """测试终态判断"""
        self.assertTrue(ControlLoopState.STOPPED.is_terminal)
        self.assertFalse(ControlLoopState.RUNNING.is_terminal)
        self.assertFalse(ControlLoopState.FAULT.is_terminal)


class TestControlLoopConfig(unittest.TestCase):
    """测试控制回路配置"""

    def test_create_config(self):
        """测试创建配置"""
        config = ControlLoopConfig(
            loop_id="loop-001",
            equipment_id="eq-001",
            parameter="temperature",
            unit="degC",
            control_mode=ControlMode.PID,
            setpoint=300.0,
            kp=2.0,
            ki=0.5,
            kd=0.1,
        )
        self.assertEqual(config.loop_id, "loop-001")
        self.assertEqual(config.equipment_id, "eq-001")
        self.assertEqual(config.parameter, "temperature")
        self.assertEqual(config.setpoint, 300.0)
        self.assertEqual(config.kp, 2.0)

    def test_default_values(self):
        """测试默认值"""
        config = ControlLoopConfig(
            loop_id="loop-002",
            equipment_id="eq-002",
            parameter="pressure",
        )
        self.assertEqual(config.control_mode, ControlMode.PID)
        self.assertEqual(config.setpoint, 0.0)
        self.assertEqual(config.kp, 1.0)
        self.assertEqual(config.ki, 0.0)
        self.assertTrue(config.anti_windup)
        self.assertEqual(config.sampling_interval, 0.1)
        self.assertFalse(config.auto_tune_enabled)

    def test_to_pid_config(self):
        """测试转换为PIDConfig"""
        config = ControlLoopConfig(
            loop_id="loop-003",
            equipment_id="eq-003",
            parameter="flow",
            kp=3.0,
            ki=0.8,
            kd=0.2,
            setpoint=50.0,
            output_min=0.0,
            output_max=100.0,
            anti_windup=True,
            derivative_filter=0.15,
            deadband=0.5,
        )
        pid_config = config.to_pid_config()
        self.assertEqual(pid_config.kp, 3.0)
        self.assertEqual(pid_config.ki, 0.8)
        self.assertEqual(pid_config.kd, 0.2)
        self.assertEqual(pid_config.setpoint, 50.0)
        self.assertEqual(pid_config.output_min, 0.0)
        self.assertEqual(pid_config.output_max, 100.0)
        self.assertTrue(pid_config.anti_windup)
        self.assertEqual(pid_config.derivative_filter, 0.15)
        self.assertEqual(pid_config.deadband, 0.5)

    def test_to_dict(self):
        """测试转换为字典"""
        config = ControlLoopConfig(
            loop_id="loop-004",
            equipment_id="eq-004",
            parameter="power",
        )
        d = config.to_dict()
        self.assertEqual(d["loop_id"], "loop-004")
        self.assertEqual(d["equipment_id"], "eq-004")
        self.assertEqual(d["control_mode"], "pid")

    def test_feedforward_params(self):
        """测试前馈参数配置"""
        config = ControlLoopConfig(
            loop_id="loop-005",
            equipment_id="eq-005",
            parameter="thickness",
            feedforward_params=[
                {"name": "pressure", "gain": 0.3, "time_constant": 1.0},
                {"name": "temperature", "gain": -0.2, "time_constant": 0.5},
            ],
        )
        self.assertEqual(len(config.feedforward_params), 2)
        self.assertEqual(config.feedforward_params[0]["name"], "pressure")
        self.assertEqual(config.feedforward_params[1]["gain"], -0.2)

    def test_auto_tune_config(self):
        """测试自动整定配置"""
        config = ControlLoopConfig(
            loop_id="loop-006",
            equipment_id="eq-006",
            parameter="position",
            auto_tune_enabled=True,
            auto_tune_interval=50,
            tuning_method=TuningMethod.IMC,
        )
        self.assertTrue(config.auto_tune_enabled)
        self.assertEqual(config.auto_tune_interval, 50)
        self.assertEqual(config.tuning_method, TuningMethod.IMC)

    def test_invalid_kp(self):
        """测试无效Kp"""
        with self.assertRaises(Exception):
            ControlLoopConfig(
                loop_id="loop-007",
                equipment_id="eq-007",
                parameter="bad",
                kp=-1.0,
            )

    def test_invalid_sampling_interval(self):
        """测试无效采样间隔"""
        with self.assertRaises(Exception):
            ControlLoopConfig(
                loop_id="loop-008",
                equipment_id="eq-008",
                parameter="bad",
                sampling_interval=0,
            )


class TestControlAction(unittest.TestCase):
    """测试控制动作"""

    def test_create_action(self):
        """测试创建控制动作"""
        now = datetime.utcnow()
        action = ControlAction(
            action_id="act-001",
            loop_id="loop-001",
            timestamp=now,
            setpoint=100.0,
            measurement=95.0,
            error=5.0,
            output=12.5,
            p_term=10.0,
            i_term=2.0,
            d_term=0.5,
            ff_term=0.0,
            control_mode=ControlMode.PID,
        )
        self.assertEqual(action.action_id, "act-001")
        self.assertEqual(action.setpoint, 100.0)
        self.assertEqual(action.measurement, 95.0)
        self.assertEqual(action.error, 5.0)
        self.assertEqual(action.output, 12.5)

    def test_total_output(self):
        """测试总输出计算"""
        action = ControlAction(
            action_id="act-002",
            loop_id="loop-001",
            setpoint=100.0,
            measurement=95.0,
            error=5.0,
            p_term=10.0,
            i_term=3.0,
            d_term=1.0,
            ff_term=-2.0,
        )
        self.assertEqual(action.total_output, 12.0)

    def test_action_to_dict(self):
        """测试动作转字典"""
        action = ControlAction(
            action_id="act-003",
            loop_id="loop-002",
            setpoint=200.0,
            measurement=198.0,
            error=2.0,
            output=5.0,
            saturated=True,
        )
        d = action.to_dict()
        self.assertEqual(d["action_id"], "act-003")
        self.assertEqual(d["loop_id"], "loop-002")
        self.assertTrue(d["saturated"])

    def test_default_values(self):
        """测试默认值"""
        action = ControlAction(
            action_id="act-004",
            loop_id="loop-003",
            setpoint=50.0,
            measurement=50.0,
            error=0.0,
        )
        self.assertEqual(action.output, 0.0)
        self.assertEqual(action.p_term, 0.0)
        self.assertEqual(action.i_term, 0.0)
        self.assertFalse(action.saturated)

    def test_saturated_action(self):
        """测试饱和动作"""
        action = ControlAction(
            action_id="act-sat",
            loop_id="loop-001",
            setpoint=100.0,
            measurement=80.0,
            error=20.0,
            output=100.0,
            saturated=True,
        )
        self.assertTrue(action.saturated)
        self.assertEqual(action.output, 100.0)


class TestControlLoopStats(unittest.TestCase):
    """测试控制回路统计"""

    def test_create_stats(self):
        """测试创建统计"""
        stats = ControlLoopStats(loop_id="loop-001")
        self.assertEqual(stats.loop_id, "loop-001")
        self.assertEqual(stats.total_actions, 0)
        self.assertEqual(stats.mean_error, 0.0)
        self.assertEqual(stats.std_error, 0.0)
        self.assertEqual(stats.saturation_count, 0)
        self.assertIsNone(stats.last_action_time)

    def test_overshoot_index(self):
        """测试超调指标"""
        stats = ControlLoopStats(
            loop_id="loop-001",
            mean_error=0.5,
            std_error=0.1,
        )
        self.assertEqual(stats.overshoot_index, 0.2)

    def test_overshoot_index_zero_error(self):
        """测试零误差的超调指标"""
        stats = ControlLoopStats(
            loop_id="loop-001",
            mean_error=0.0,
            std_error=0.5,
        )
        self.assertEqual(stats.overshoot_index, 0.0)

    def test_stats_to_dict(self):
        """测试统计转字典"""
        now = datetime.utcnow()
        stats = ControlLoopStats(
            loop_id="loop-002",
            total_actions=100,
            mean_error=0.2,
            std_error=0.05,
            last_action_time=now,
            saturation_count=5,
            tuning_count=3,
        )
        d = stats.to_dict()
        self.assertEqual(d["loop_id"], "loop-002")
        self.assertEqual(d["total_actions"], 100)
        self.assertEqual(d["saturation_count"], 5)
        self.assertIsNotNone(d["last_action_time"])

    def test_default_min_abs_error(self):
        """测试默认最小绝对误差（应为inf）"""
        stats = ControlLoopStats(loop_id="loop-003")
        self.assertEqual(stats.min_abs_error, float("inf"))


if __name__ == "__main__":
    unittest.main()
