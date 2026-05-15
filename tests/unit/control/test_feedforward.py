"""前馈控制器测试

测试FeedforwardController、FeedforwardModel和AdaptiveFeedforwardController。
"""

import unittest
from myeap.control.feedforward import (
    FeedforwardModel,
    FeedforwardController,
    AdaptiveFeedforwardController,
)


class TestFeedforwardModel(unittest.TestCase):
    """测试前馈模型"""

    def test_create_static_model(self):
        """测试创建静态模型"""
        model = FeedforwardModel(name="pressure", gain=0.5)
        self.assertEqual(model.name, "pressure")
        self.assertEqual(model.gain, 0.5)
        self.assertEqual(model.time_constant, 0.0)
        self.assertEqual(model.dead_time, 0.0)
        self.assertTrue(model.enabled)

    def test_create_dynamic_model(self):
        """测试创建动态模型"""
        model = FeedforwardModel(
            name="temperature", gain=-0.3, time_constant=2.0, dead_time=0.5,
        )
        self.assertEqual(model.name, "temperature")
        self.assertEqual(model.gain, -0.3)
        self.assertEqual(model.time_constant, 2.0)
        self.assertEqual(model.dead_time, 0.5)

    def test_is_static(self):
        """测试静态模型判断"""
        static = FeedforwardModel(name="p1", gain=1.0)
        dynamic = FeedforwardModel(
            name="p2", gain=1.0, time_constant=1.0,
        )
        self.assertTrue(static.is_static)
        self.assertFalse(static.is_dynamic)
        self.assertFalse(dynamic.is_static)
        self.assertTrue(dynamic.is_dynamic)

    def test_invalid_time_constant(self):
        """测试无效时间常数"""
        with self.assertRaises(ValueError):
            FeedforwardModel(
                name="bad", gain=1.0, time_constant=-1.0,
            )

    def test_invalid_dead_time(self):
        """测试无效滞后时间"""
        with self.assertRaises(ValueError):
            FeedforwardModel(name="bad", gain=1.0, dead_time=-0.5)

    def test_default_values(self):
        """测试默认值"""
        model = FeedforwardModel(name="test")
        self.assertEqual(model.gain, 1.0)
        self.assertEqual(model.time_constant, 0.0)
        self.assertEqual(model.dead_time, 0.0)
        self.assertTrue(model.enabled)


class TestFeedforwardController(unittest.TestCase):
    """测试前馈控制器"""

    def setUp(self):
        self.ff = FeedforwardController()

    def test_add_static_model(self):
        """测试添加静态模型"""
        model = self.ff.add_model("pressure", gain=0.5)
        self.assertEqual(model.name, "pressure")
        self.assertEqual(model.gain, 0.5)
        self.assertTrue(model.is_static)

    def test_add_dynamic_model(self):
        """测试添加动态模型"""
        model = self.ff.add_model(
            "temperature", gain=-0.3, time_constant=2.0,
        )
        self.assertFalse(model.is_static)
        self.assertEqual(model.time_constant, 2.0)

    def test_add_custom_model(self):
        """测试添加自定义模型"""
        def custom_func(x):
            return x ** 2

        self.ff.add_custom_model("nonlinear", custom_func)
        self.assertEqual(len(self.ff.list_models()), 1)

    def test_remove_model(self):
        """测试移除模型"""
        self.ff.add_model("pressure", gain=0.5)
        self.assertTrue(self.ff.remove_model("pressure"))
        self.assertFalse(self.ff.remove_model("nonexistent"))
        self.assertEqual(len(self.ff.list_models()), 0)

    def test_remove_custom_model(self):
        """测试移除自定义模型"""
        self.ff.add_custom_model("nonlinear", lambda x: x)
        self.assertTrue(self.ff.remove_model("nonlinear"))

    def test_enable_disable_model(self):
        """测试启用和禁用模型"""
        self.ff.add_model("pressure", gain=0.5)
        self.assertTrue(self.ff.enable_model("pressure", False))
        self.assertFalse(self.ff.enable_model("nonexistent", True))

    def test_static_feedforward(self):
        """测试静态前馈计算"""
        self.ff.add_model("pressure", gain=0.5)
        self.ff.add_model("temp", gain=-0.2)
        correction = self.ff.compute({"pressure": 10.0, "temp": 5.0})
        # pressure: 0.5 * 10 = 5.0
        # temp: -0.2 * 5 = -1.0
        # total: 4.0
        self.assertAlmostEqual(correction, 4.0, places=5)

    def test_feedforward_zero_disturbance(self):
        """测试零扰动"""
        self.ff.add_model("pressure", gain=0.5)
        correction = self.ff.compute({"pressure": 0.0})
        self.assertEqual(correction, 0.0)

    def test_feedforward_unknown_parameter(self):
        """测试未知扰动参数"""
        self.ff.add_model("pressure", gain=0.5)
        correction = self.ff.compute({"unknown_param": 100.0})
        self.assertEqual(correction, 0.0)

    def test_feedforward_no_models(self):
        """测试无模型时的前馈"""
        correction = self.ff.compute({"pressure": 10.0})
        self.assertEqual(correction, 0.0)

    def test_disabled_model_ignored(self):
        """测试禁用的模型被忽略"""
        self.ff.add_model("pressure", gain=0.5)
        self.ff.enable_model("pressure", False)
        correction = self.ff.compute({"pressure": 10.0})
        self.assertEqual(correction, 0.0)

    def test_dynamic_feedforward(self):
        """测试动态前馈计算"""
        self.ff.add_model("temp", gain=1.0, time_constant=0.5)
        correction = self.ff.compute({"temp": 10.0})
        # 首次调用，dt默认0.01, alpha=exp(-0.01/0.5)=0.9802
        # correction = 0.9802*10 + 0.0198*1.0*10 ≈ 10.0
        self.assertAlmostEqual(correction, 10.0, places=1)

    def test_multiple_dynamic_models(self):
        """测试多个模型混合"""
        self.ff.add_model("p1", gain=0.5)  # static
        self.ff.add_model("p2", gain=1.0, time_constant=1.0)  # dynamic
        correction = self.ff.compute({"p1": 10.0, "p2": 10.0})
        # p1: 5.0, p2: ~10.0 -> total ~15.0
        self.assertGreater(correction, 10.0)
        self.assertLess(correction, 20.0)

    def test_reset(self):
        """测试重置"""
        self.ff.add_model("pressure", gain=1.0, time_constant=0.5)
        self.ff.compute({"pressure": 10.0})
        self.ff.reset()
        # 重置后重新计算应与首次相同
        correction = self.ff.compute({"pressure": 10.0})
        self.assertAlmostEqual(correction, 10.0, places=1)

    def test_list_models(self):
        """测试列出模型"""
        self.ff.add_model("p1", gain=0.5)
        self.ff.add_model("p2", gain=-0.3)
        self.ff.add_custom_model("p3", lambda x: x)
        models = self.ff.list_models()
        self.assertEqual(len(models), 3)

    def test_get_correction_breakdown(self):
        """测试获取补偿明细"""
        self.ff.add_model("p1", gain=0.5)
        self.ff.add_model("p2", gain=1.0)
        breakdown = self.ff.get_correction_breakdown({"p1": 10.0, "p2": 5.0})
        self.assertIn("p1", breakdown)
        self.assertIn("p2", breakdown)
        self.assertIn("total", breakdown)
        self.assertAlmostEqual(breakdown["total"], 10.0, places=5)

    def test_custom_model_in_compute(self):
        """测试自定义模型在计算中的应用"""
        def double(x):
            return x * 2

        self.ff.add_model("p1", gain=0.5)
        self.ff.add_custom_model("p2", double)
        correction = self.ff.compute({"p1": 10.0, "p2": 5.0})
        # p1: 0.5*10 = 5.0, p2: double(5) = 10.0 => total 15.0
        self.assertAlmostEqual(correction, 15.0, places=5)

    def test_custom_model_in_breakdown(self):
        """测试自定义模型在明细中"""
        self.ff.add_custom_model("nonlinear", lambda x: x ** 2)
        breakdown = self.ff.get_correction_breakdown({"nonlinear": 3.0})
        self.assertIn("nonlinear_custom", breakdown)
        self.assertAlmostEqual(breakdown["total"], 9.0, places=5)


class TestAdaptiveFeedforwardController(unittest.TestCase):
    """测试自适应前馈控制器"""

    def setUp(self):
        self.aff = AdaptiveFeedforwardController(learning_rate=0.01)

    def test_adapt_gain(self):
        """测试自适应调整增益"""
        self.aff.add_model("pressure", gain=0.5)
        # 残差正 -> 应增加增益
        new_gain = self.aff.adapt("pressure", disturbance_value=10.0, residual_error=0.5)
        # delta = 0.01 * 0.5 * 10.0 = 0.05
        # new_gain = 0.5 + 0.05 = 0.55
        self.assertAlmostEqual(new_gain, 0.55, places=5)

    def test_adapt_gain_negative_error(self):
        """测试负残差的自适应"""
        self.aff.add_model("pressure", gain=0.5)
        new_gain = self.aff.adapt("pressure", disturbance_value=10.0, residual_error=-0.5)
        self.assertAlmostEqual(new_gain, 0.45, places=5)

    def test_adapt_unknown_parameter(self):
        """测试对未知参数的自适应"""
        result = self.aff.adapt("unknown", disturbance_value=10.0, residual_error=0.5)
        self.assertEqual(result, 0.0)

    def test_compute_and_adapt(self):
        """测试计算并自适应"""
        self.aff.add_model("pressure", gain=0.5)
        self.aff.add_model("temp", gain=0.3)
        correction = self.aff.compute_and_adapt(
            {"pressure": 10.0, "temp": 5.0},
            residual_error=1.0,
        )
        # pressure: 0.5*10=5.0, temp: 0.3*5=1.5, total=6.5
        self.assertAlmostEqual(correction, 6.5, places=5)
        # 增益应该被调整了
        self.assertNotEqual(
            self.aff._models["pressure"].gain, 0.5
        )

    def test_get_gain_history(self):
        """测试获取增益历史"""
        self.aff.add_model("pressure", gain=0.5)
        self.aff.adapt("pressure", 10.0, 0.5)
        self.aff.adapt("pressure", 10.0, 0.3)
        history = self.aff.get_gain_history("pressure")
        self.assertEqual(len(history), 2)

    def test_empty_gain_history(self):
        """测试空增益历史"""
        history = self.aff.get_gain_history("nonexistent")
        self.assertEqual(history, [])

    def test_reset_clears_history(self):
        """测试重置清除历史"""
        self.aff.add_model("pressure", gain=0.5)
        self.aff.adapt("pressure", 10.0, 0.5)
        self.aff.reset()
        history = self.aff.get_gain_history("pressure")
        self.assertEqual(history, [])

    def test_inherits_feedforward(self):
        """测试继承关系"""
        self.assertTrue(issubclass(AdaptiveFeedforwardController, FeedforwardController))

    def test_adapt_with_zero_disturbance(self):
        """测试零扰动下的自适应"""
        self.aff.add_model("pressure", gain=0.5)
        new_gain = self.aff.adapt("pressure", disturbance_value=0.0, residual_error=1.0)
        # delta = 0.01 * 1.0 * 0.0 = 0.0
        self.assertAlmostEqual(new_gain, 0.5, places=5)

    def test_adapt_with_zero_error(self):
        """测试零误差下的自适应"""
        self.aff.add_model("pressure", gain=0.5)
        new_gain = self.aff.adapt("pressure", disturbance_value=10.0, residual_error=0.0)
        # delta = 0.01 * 0.0 * 10.0 = 0.0
        self.assertAlmostEqual(new_gain, 0.5, places=5)

    def test_list_models_includes_inherited(self):
        """测试列出模型包含继承的模型"""
        self.aff.add_model("p1", gain=0.5)
        self.aff.add_custom_model("p2", lambda x: x)
        models = self.aff.list_models()
        self.assertEqual(len(models), 2)


if __name__ == "__main__":
    unittest.main()
