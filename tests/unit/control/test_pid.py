"""PID控制器测试

测试PID控制器的核心功能，包括P/I/D各项计算、抗积分饱和、
微分滤波、死区、级联控制等。
"""

import time
import unittest
from myeap.control.pid import (
    PIDConfig,
    PIDController,
    CascadePIDController,
)


class TestPIDConfig(unittest.TestCase):
    """测试PID配置"""

    def test_create_config(self):
        """测试创建配置"""
        config = PIDConfig(kp=2.0, ki=0.5, kd=0.1, setpoint=100.0)
        self.assertEqual(config.kp, 2.0)
        self.assertEqual(config.ki, 0.5)
        self.assertEqual(config.kd, 0.1)
        self.assertEqual(config.setpoint, 100.0)

    def test_default_values(self):
        """测试默认值"""
        config = PIDConfig(kp=1.0, ki=0.0, kd=0.0, setpoint=0.0)
        self.assertIsNone(config.output_min)
        self.assertIsNone(config.output_max)
        self.assertTrue(config.anti_windup)
        self.assertEqual(config.derivative_filter, 0.1)
        self.assertEqual(config.deadband, 0.0)

    def test_invalid_kp(self):
        """测试无效kp"""
        with self.assertRaises(ValueError):
            PIDConfig(kp=-1.0, ki=0.0, kd=0.0, setpoint=0.0)

    def test_invalid_derivative_filter(self):
        """测试无效微分滤波系数"""
        with self.assertRaises(ValueError):
            PIDConfig(kp=1.0, ki=0.0, kd=0.0, setpoint=0.0, derivative_filter=1.5)

    def test_invalid_deadband(self):
        """测试无效死区"""
        with self.assertRaises(ValueError):
            PIDConfig(kp=1.0, ki=0.0, kd=0.0, setpoint=0.0, deadband=-0.1)

    def test_invalid_output_limits(self):
        """测试无效输出限制"""
        with self.assertRaises(ValueError):
            PIDConfig(
                kp=1.0, ki=0.0, kd=0.0, setpoint=0.0,
                output_min=100.0, output_max=50.0,
            )

    def test_with_setpoint(self):
        """测试创建带新设定点的配置"""
        config = PIDConfig(kp=2.0, ki=0.5, kd=0.1, setpoint=100.0)
        new_config = config.with_setpoint(200.0)
        self.assertEqual(new_config.setpoint, 200.0)
        self.assertEqual(new_config.kp, 2.0)
        self.assertEqual(new_config.ki, 0.5)
        self.assertEqual(new_config.kd, 0.1)
        # 原配置不变
        self.assertEqual(config.setpoint, 100.0)


class TestPIDController(unittest.TestCase):
    """测试PID控制器"""

    def setUp(self):
        self.config = PIDConfig(
            kp=2.0, ki=0.5, kd=0.1, setpoint=100.0,
            output_min=-200.0, output_max=200.0,
        )
        self.pid = PIDController(self.config)

    def test_proportional_only(self):
        """测试纯比例控制"""
        config = PIDConfig(kp=2.0, ki=0.0, kd=0.0, setpoint=100.0)
        pid = PIDController(config)
        output = pid.compute(90.0)
        # P = kp * error = 2.0 * 10.0 = 20.0
        self.assertGreater(output, 18.0)
        self.assertLess(output, 22.0)

    def test_proportional_negative_error(self):
        """测试负误差（超调）的比例控制"""
        config = PIDConfig(kp=2.0, ki=0.0, kd=0.0, setpoint=100.0)
        pid = PIDController(config)
        output = pid.compute(110.0)
        # P = 2.0 * (-10.0) = -20.0
        self.assertLess(output, -18.0)
        self.assertGreater(output, -22.0)

    def test_integral_buildup(self):
        """测试积分累积"""
        config = PIDConfig(kp=0.0, ki=1.0, kd=0.0, setpoint=100.0)
        pid = PIDController(config)
        t0 = time.monotonic()
        # 第一次调用: integral = 10 * 0.01 = 0.1
        pid.compute(90.0, t0)
        self.assertAlmostEqual(pid.integral, 0.1, places=3)

    def test_derivative_term(self):
        """测试微分项"""
        config = PIDConfig(kp=0.0, ki=0.0, kd=1.0, setpoint=100.0)
        pid = PIDController(config)
        t0 = time.monotonic()
        pid.compute(100.0, t0)  # 初始化，error=0
        # 第二次: error从0变为10, derivative = 10/0.01 = 1000
        # filtered: 0.1*1000 + 0.9*0 = 100
        # d_term = 1.0 * 100 = 100
        output = pid.compute(90.0, t0 + 0.01)
        self.assertGreater(output, 80.0)

    def test_setpoint_update(self):
        """测试设定点更新"""
        pid = PIDController(self.config)
        pid.update_setpoint(150.0)
        self.assertEqual(pid.config.setpoint, 150.0)

    def test_reset(self):
        """测试控制器重置"""
        pid = PIDController(self.config)
        pid.compute(90.0)
        self.assertNotEqual(pid.integral, 0.0)
        pid.reset()
        self.assertEqual(pid.integral, 0.0)

    def test_anti_windup_upper(self):
        """测试抗积分饱和 - 上限"""
        config = PIDConfig(
            kp=1.0, ki=10.0, kd=0.0, setpoint=100.0,
            output_min=0.0, output_max=50.0, anti_windup=True,
        )
        pid = PIDController(config)
        t0 = time.monotonic()
        # 大误差导致输出远超上限
        for i in range(10):
            pid.compute(0.0, t0 + i * 0.01)
        # 输出应被钳位在50.0
        output = pid.compute(0.0, t0 + 0.1)
        self.assertAlmostEqual(output, 50.0, places=1)

    def test_anti_windup_lower(self):
        """测试抗积分饱和 - 下限"""
        config = PIDConfig(
            kp=1.0, ki=10.0, kd=0.0, setpoint=100.0,
            output_min=-30.0, output_max=100.0, anti_windup=True,
        )
        pid = PIDController(config)
        t0 = time.monotonic()
        # 大负向误差导致输出低于下限
        for i in range(10):
            pid.compute(200.0, t0 + i * 0.01)
        output = pid.compute(200.0, t0 + 0.1)
        self.assertAlmostEqual(output, -30.0, places=1)

    def test_no_anti_windup(self):
        """测试不启用抗积分饱和"""
        config = PIDConfig(
            kp=1.0, ki=10.0, kd=0.0, setpoint=100.0,
            output_min=0.0, output_max=50.0, anti_windup=False,
        )
        pid = PIDController(config)
        t0 = time.monotonic()
        for i in range(10):
            pid.compute(0.0, t0 + i * 0.01)
        output = pid.compute(0.0, t0 + 0.1)
        # 没有抗积分饱和，输出被钳位但积分继续累积
        self.assertAlmostEqual(output, 50.0, places=1)

    def test_deadband(self):
        """测试死区"""
        config = PIDConfig(
            kp=10.0, ki=0.0, kd=0.0, setpoint=100.0, deadband=1.0,
        )
        pid = PIDController(config)
        t0 = time.monotonic()
        # 首次调用建立基线
        pid.compute(100.0, t0)
        # 误差0.5 < deadband 1.0，应该返回上次输出
        output = pid.compute(99.5, t0 + 0.01)
        self.assertEqual(output, 0.0)  # 上次输出是0

    def test_output_clamping(self):
        """测试输出钳位"""
        config = PIDConfig(
            kp=100.0, ki=0.0, kd=0.0, setpoint=100.0,
            output_min=0.0, output_max=100.0,
        )
        pid = PIDController(config)
        output = pid.compute(0.0)  # error=100, P=-10000, clamped
        self.assertEqual(output, 100.0)

    def test_compute_with_terms(self):
        """测试带分量返回的计算"""
        config = PIDConfig(
            kp=2.0, ki=0.5, kd=0.1, setpoint=100.0,
        )
        pid = PIDController(config)
        t0 = time.monotonic()
        pid.compute(100.0, t0)
        output, p_term, i_term, d_term = pid.compute_with_terms(90.0, t0 + 0.01)
        self.assertGreater(p_term, 0)  # 正误差 -> 正比例项
        self.assertGreater(i_term, 0)  # 正误差积分 -> 正积分项

    def test_update_gains(self):
        """测试更新增益参数"""
        pid = PIDController(self.config)
        pid.update_gains(kp=5.0, ki=1.0)
        self.assertEqual(pid.config.kp, 5.0)
        self.assertEqual(pid.config.ki, 1.0)
        self.assertEqual(pid.config.kd, 0.1)  # 未更新，保持不变

    def test_update_gains_partial(self):
        """测试部分更新增益"""
        pid = PIDController(self.config)
        pid.update_gains(kd=0.5)
        self.assertEqual(pid.config.kd, 0.5)
        self.assertEqual(pid.config.kp, 2.0)

    def test_get_state(self):
        """测试获取状态"""
        pid = PIDController(self.config)
        pid.compute(95.0)
        state = pid.get_state()
        self.assertIn("integral", state)
        self.assertIn("prev_error", state)
        self.assertIn("prev_derivative", state)
        self.assertIn("prev_output", state)
        self.assertIn("saturated", state)

    def test_saturated_property(self):
        """测试饱和属性"""
        config = PIDConfig(
            kp=100.0, ki=0.0, kd=0.0, setpoint=100.0,
            output_max=50.0,
        )
        pid = PIDController(config)
        pid.compute(0.0)  # 远超上限
        self.assertTrue(pid.saturated)

    def test_not_saturated_property(self):
        """测试未饱和属性"""
        config = PIDConfig(
            kp=1.0, ki=0.0, kd=0.0, setpoint=100.0,
            output_min=-200.0, output_max=200.0,
        )
        pid = PIDController(config)
        pid.compute(90.0)
        self.assertFalse(pid.saturated)

    def test_zero_ki(self):
        """测试ki=0时不累加积分"""
        config = PIDConfig(kp=2.0, ki=0.0, kd=0.1, setpoint=100.0)
        pid = PIDController(config)
        pid.compute(90.0)
        self.assertEqual(pid.integral, 0.0)

    def test_zero_kd(self):
        """测试kd=0时不计算微分"""
        config = PIDConfig(kp=2.0, ki=0.5, kd=0.0, setpoint=100.0)
        pid = PIDController(config)
        output = pid.compute(90.0)
        # 应该只有P和I
        self.assertGreater(output, 0)

    def test_same_timestamp(self):
        """测试相同时间戳"""
        pid = PIDController(self.config)
        t = time.monotonic()
        output1 = pid.compute(90.0, t)
        output2 = pid.compute(88.0, t)  # 同时间戳，dt会使用默认值
        self.assertIsNotNone(output2)

    def test_large_time_gap(self):
        """测试大时间间隙"""
        pid = PIDController(self.config)
        t0 = time.monotonic()
        output1 = pid.compute(90.0, t0)
        output2 = pid.compute(88.0, t0 + 5.0)  # 5秒后，dt被限制为1.0
        self.assertIsNotNone(output2)

    def test_steady_state_convergence(self):
        """测试稳态收敛"""
        config = PIDConfig(
            kp=2.0, ki=0.5, kd=0.1, setpoint=100.0,
        )
        pid = PIDController(config)
        t0 = time.monotonic()
        # 模拟测量值逐步接近设定点
        values = [80.0, 85.0, 90.0, 95.0, 98.0, 99.0, 100.0]
        outputs = []
        for i, v in enumerate(values):
            outputs.append(pid.compute(v, t0 + i * 0.01))
        # 随着误差减小，输出应该减小
        self.assertLess(abs(outputs[-1]), abs(outputs[0]))


class TestCascadePIDController(unittest.TestCase):
    """测试级联PID控制器"""

    def setUp(self):
        self.primary_config = PIDConfig(
            kp=2.0, ki=0.5, kd=0.1, setpoint=300.0,
            output_min=0.0, output_max=500.0,
        )
        self.secondary_config = PIDConfig(
            kp=1.0, ki=0.2, kd=0.05, setpoint=150.0,
            output_min=0.0, output_max=100.0,
        )
        self.cascade = CascadePIDController(
            self.primary_config, self.secondary_config, ratio=1.0,
        )

    def test_cascade_compute(self):
        """测试级联计算"""
        t0 = time.monotonic()
        # 主回路测量值低于设定点 -> 输出增加从回路设定点
        output = self.cascade.compute(290.0, 140.0, t0)
        self.assertIsNotNone(output)

    def test_cascade_compute_same_value(self):
        """测试级联在设定点的输出"""
        t0 = time.monotonic()
        output = self.cascade.compute(300.0, 150.0, t0)
        # 在设定点附近输出应较小
        self.assertIsNotNone(output)

    def test_update_primary_setpoint(self):
        """测试更新主回路设定点"""
        self.cascade.update_primary_setpoint(350.0)
        self.assertEqual(self.cascade.primary.config.setpoint, 350.0)

    def test_cascade_reset(self):
        """测试级联重置"""
        t0 = time.monotonic()
        self.cascade.compute(290.0, 140.0, t0)
        self.cascade.reset()
        self.assertEqual(self.cascade.primary.integral, 0.0)
        self.assertEqual(self.cascade.secondary.integral, 0.0)

    def test_cascade_get_state(self):
        """测试获取级联状态"""
        t0 = time.monotonic()
        self.cascade.compute(290.0, 140.0, t0)
        state = self.cascade.get_state()
        self.assertIn("primary", state)
        self.assertIn("secondary", state)
        self.assertIn("ratio", state)

    def test_cascade_ratio(self):
        """测试缩放比例"""
        cascade = CascadePIDController(
            self.primary_config, self.secondary_config, ratio=0.5,
        )
        t0 = time.monotonic()
        output = cascade.compute(290.0, 140.0, t0)
        self.assertIsNotNone(output)
        self.assertEqual(cascade.ratio, 0.5)


if __name__ == "__main__":
    unittest.main()
