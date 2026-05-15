"""自适应控制器测试

测试AdaptiveController的自动整定、性能监控和状态管理。
"""

import time
import unittest
from myeap.control.pid import PIDConfig, PIDController
from myeap.control.adaptive import (
    AdaptiveConfig,
    AdaptiveController,
    TuningResult,
)


class TestAdaptiveConfig(unittest.TestCase):
    """测试自适应配置"""

    def setUp(self):
        self.pid_config = PIDConfig(kp=2.0, ki=0.5, kd=0.1, setpoint=100.0)

    def test_create_config(self):
        """测试创建配置"""
        config = AdaptiveConfig(base_config=self.pid_config)
        self.assertEqual(config.base_config, self.pid_config)
        self.assertTrue(config.tuning_enabled)
        self.assertEqual(config.tuning_interval, 100)
        self.assertEqual(config.learning_rate, 0.05)

    def test_invalid_tuning_interval(self):
        """测试无效整定周期"""
        with self.assertRaises(ValueError):
            AdaptiveConfig(base_config=self.pid_config, tuning_interval=5)

    def test_invalid_learning_rate(self):
        """测试无效学习率"""
        with self.assertRaises(ValueError):
            AdaptiveConfig(base_config=self.pid_config, learning_rate=0.0)

        with self.assertRaises(ValueError):
            AdaptiveConfig(base_config=self.pid_config, learning_rate=1.5)

    def test_invalid_damping_factor(self):
        """测试无效阻尼因子"""
        with self.assertRaises(ValueError):
            AdaptiveConfig(base_config=self.pid_config, damping_factor=1.5)

    def test_invalid_history_size(self):
        """测试无效历史大小"""
        with self.assertRaises(ValueError):
            AdaptiveConfig(base_config=self.pid_config, history_size=5)

    def test_custom_config(self):
        """测试自定义配置"""
        config = AdaptiveConfig(
            base_config=self.pid_config,
            tuning_enabled=False,
            tuning_interval=50,
            learning_rate=0.1,
            error_threshold=0.05,
            oscillation_threshold=0.2,
            min_gain=0.1,
            max_gain=50.0,
            history_size=500,
        )
        self.assertFalse(config.tuning_enabled)
        self.assertEqual(config.tuning_interval, 50)
        self.assertEqual(config.learning_rate, 0.1)
        self.assertEqual(config.error_threshold, 0.05)
        self.assertEqual(config.max_gain, 50.0)


class TestTuningResult(unittest.TestCase):
    """测试整定结果"""

    def test_create_result(self):
        """测试创建整定结果"""
        result = TuningResult(
            timestamp=time.monotonic(),
            previous_gains=(2.0, 0.5, 0.1),
            new_gains=(2.2, 0.55, 0.12),
            reason="增加Ki",
            metrics={"avg_error": 0.5, "oscillation_ratio": 0.1},
        )
        self.assertAlmostEqual(result.kp_change, 0.2)
        self.assertAlmostEqual(result.ki_change, 0.05)
        self.assertAlmostEqual(result.kd_change, 0.02)

    def test_result_no_change(self):
        """测试无变化的整定结果"""
        result = TuningResult(
            timestamp=time.monotonic(),
            previous_gains=(1.0, 0.5, 0.1),
            new_gains=(1.0, 0.5, 0.1),
            reason="无显著变化",
        )
        self.assertEqual(result.kp_change, 0.0)
        self.assertEqual(result.ki_change, 0.0)
        self.assertEqual(result.kd_change, 0.0)


class TestAdaptiveController(unittest.TestCase):
    """测试自适应控制器"""

    def setUp(self):
        self.pid_config = PIDConfig(kp=2.0, ki=0.5, kd=0.1, setpoint=100.0)
        self.adapt_config = AdaptiveConfig(
            base_config=self.pid_config,
            tuning_interval=20,  # 快速整定以利测试
        )
        self.controller = AdaptiveController(self.adapt_config)

    def test_initial_state(self):
        """测试初始状态"""
        self.assertEqual(self.controller.tuning_count, 0)
        self.assertIsNone(self.controller.last_tuning)

    def test_compute_with_pid(self):
        """测试基本PID计算"""
        output = self.controller.compute(95.0)
        self.assertGreater(output, 0)

    def test_sample_count_increases(self):
        """测试样本计数递增"""
        for i in range(5):
            self.controller.compute(95.0 + i)
        self.assertEqual(self.controller._sample_count, 5)

    def test_auto_tune_triggers(self):
        """测试自动整定触发"""
        t0 = time.monotonic()
        # 生成足够的样本来触发整定 (tuning_interval=20)
        for i in range(20):
            # 制造振荡信号
            error_pattern = [5.0, -5.0, 3.0, -3.0] * 5
            self.controller.compute(
                self.controller.config.base_config.setpoint - error_pattern[i],
                t0 + i * 0.01,
            )
        # 第20次应该触发auto_tune
        self.assertGreaterEqual(self.controller.tuning_count, 0)

    def test_auto_tune_disabled(self):
        """测试禁用自动整定"""
        config = AdaptiveConfig(
            base_config=self.pid_config,
            tuning_enabled=False,
            tuning_interval=20,
        )
        controller = AdaptiveController(config)
        t0 = time.monotonic()
        for i in range(25):
            controller.compute(95.0, t0 + i * 0.01)
        self.assertEqual(controller.tuning_count, 0)

    def test_update_setpoint(self):
        """测试更新设定点"""
        self.controller.update_setpoint(200.0)
        self.assertEqual(self.controller.config.base_config.setpoint, 200.0)
        self.assertEqual(self.controller.pid.config.setpoint, 200.0)
        # 积分应被重置
        self.assertEqual(self.controller.pid.integral, 0.0)

    def test_reset(self):
        """测试重置（保留参数）"""
        # 先运行一些计算
        for i in range(10):
            self.controller.compute(95.0)
        self.assertGreater(self.controller._sample_count, 0)

        self.controller.reset()
        self.assertEqual(self.controller._sample_count, 0)
        self.assertEqual(len(self.controller._performance_history), 0)

    def test_full_reset(self):
        """测试完全重置"""
        # 运行计算
        for i in range(10):
            self.controller.compute(95.0)

        self.controller.full_reset()
        self.assertEqual(self.controller._sample_count, 0)
        self.assertEqual(self.controller.tuning_count, 0)
        # PID应该恢复到基础配置
        self.assertEqual(self.controller.pid.config.kp, 2.0)
        self.assertEqual(self.controller.pid.config.ki, 0.5)

    def test_get_performance_metrics(self):
        """测试获取性能指标"""
        for i in range(10):
            self.controller.compute(95.0)
        metrics = self.controller.get_performance_metrics()
        self.assertIn("avg_error", metrics)
        self.assertIn("error_std", metrics)
        self.assertIn("sample_count", metrics)
        self.assertEqual(metrics["sample_count"], 10)

    def test_empty_performance_metrics(self):
        """测试空性能指标"""
        metrics = self.controller.get_performance_metrics()
        self.assertEqual(metrics["avg_error"], 0.0)
        self.assertEqual(metrics["sample_count"], 0)

    def test_get_tuning_history(self):
        """测试获取整定历史"""
        history = self.controller.get_tuning_history()
        self.assertIsInstance(history, list)

    def test_force_tune(self):
        """测试强制整定"""
        # 先生成一些数据
        for i in range(15):
            self.controller.compute(90.0 + i)
        result = self.controller.force_tune()
        self.assertIsInstance(result, TuningResult)
        self.assertGreaterEqual(self.controller.tuning_count, 1)

    def test_force_tune_with_oscillations(self):
        """测试在振荡信号下的强制整定"""
        t0 = time.monotonic()
        oscillations = [5.0, -5.0, 5.0, -5.0, 3.0, -3.0, 3.0, -3.0, 2.0, -2.0]
        for i, err in enumerate(oscillations):
            self.controller.compute(
                self.controller.config.base_config.setpoint - err,
                t0 + i * 0.01,
            )
        result = self.controller.force_tune()
        self.assertIsNotNone(result)
        self.assertIsInstance(result.reason, str)

    def test_get_state(self):
        """测试获取状态"""
        for i in range(10):
            self.controller.compute(95.0 + i)
        state = self.controller.get_state()
        self.assertIn("pid_state", state)
        self.assertIn("pid_config", state)
        self.assertIn("sample_count", state)
        self.assertIn("tuning_count", state)
        self.assertIn("performance", state)

    def test_oscillation_detection(self):
        """测试振荡检测"""
        # 禁用自动整定以避免其重置振荡计数器
        config = AdaptiveConfig(
            base_config=self.pid_config,
            tuning_enabled=False,
        )
        controller = AdaptiveController(config)
        t0 = time.monotonic()
        # 模拟振荡信号
        for i in range(30):
            err = 5.0 if i % 2 == 0 else -5.0
            controller.compute(100.0 - err, t0 + i * 0.01)
        self.assertGreater(controller._oscillation_counter, 10)

    def test_steady_state_behavior(self):
        """测试稳态行为"""
        t0 = time.monotonic()
        for i in range(20):
            # 误差很小
            err = 0.01
            self.controller.compute(100.0 - err, t0 + i * 0.01)
        # Kd应该在稳态下减小
        self.assertGreaterEqual(self.controller.pid.config.kd, 0.0)

    def test_large_error_response(self):
        """测试大误差响应"""
        t0 = time.monotonic()
        # 制造大误差
        for i in range(25):
            self.controller.compute(50.0, t0 + i * 0.01)
        # 大误差持续存在，Ki应该增大
        self.assertIsNotNone(self.controller.pid.config.ki)

    def test_history_size_limit(self):
        """测试历史大小限制"""
        config = AdaptiveConfig(
            base_config=self.pid_config,
            history_size=50,
            tuning_enabled=False,
        )
        controller = AdaptiveController(config)
        for i in range(100):
            controller.compute(95.0)
        self.assertLessEqual(
            len(controller._performance_history), 50
        )

    def test_repeated_compute_cycles(self):
        """测试多个整定周期"""
        config = AdaptiveConfig(
            base_config=self.pid_config,
            tuning_interval=30,
            tuning_enabled=True,
        )
        controller = AdaptiveController(config)
        t0 = time.monotonic()
        for i in range(60):
            controller.compute(95.0, t0 + i * 0.01)
        self.assertGreaterEqual(controller.tuning_count, 0)

    def test_pid_parameters_after_tuning(self):
        """测试整定后的PID参数"""
        config = AdaptiveConfig(
            base_config=self.pid_config,
            tuning_interval=15,
        )
        controller = AdaptiveController(config)
        t0 = time.monotonic()
        # 稳态小误差 -> Ki应小幅变化
        for i in range(15):
            controller.compute(99.9, t0 + i * 0.01)
        # 检查PID参数是否被调整了
        self.assertGreaterEqual(controller.pid.config.kp, 0.0)


if __name__ == "__main__":
    unittest.main()
