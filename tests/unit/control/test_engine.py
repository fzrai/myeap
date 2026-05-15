"""控制引擎测试

测试ProcessControlEngine的回回路管理、启停控制、模式切换和性能监控。
"""

import asyncio
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from myeap.control.engine import ProcessControlEngine, ControlLoop
from myeap.control.models import (
    ControlLoopConfig,
    ControlLoopState,
    ControlMode,
    ControlLoopStats,
)
from myeap.control.pid import PIDConfig, PIDController
from myeap.control.adaptive import AdaptiveController


class TestControlLoop(unittest.TestCase):
    """测试控制回路对象"""

    def test_create_loop(self):
        """测试创建回路"""
        config = ControlLoopConfig(
            loop_id="test-loop",
            equipment_id="eq-001",
            parameter="temperature",
            setpoint=100.0,
        )
        pid = PIDController(config.to_pid_config())
        loop = ControlLoop(config=config, controller=pid)
        self.assertEqual(loop.config.loop_id, "test-loop")
        self.assertEqual(loop.state, ControlLoopState.CREATED)
        self.assertFalse(loop.is_running)
        self.assertIsNone(loop.task)

    def test_loop_to_dict(self):
        """测试回路转字典"""
        config = ControlLoopConfig(
            loop_id="test-loop",
            equipment_id="eq-001",
            parameter="temperature",
            setpoint=100.0,
            control_mode=ControlMode.PID,
        )
        pid = PIDController(config.to_pid_config())
        loop = ControlLoop(config=config, controller=pid)
        d = loop.to_dict()
        self.assertEqual(d["loop_id"], "test-loop")
        self.assertEqual(d["equipment_id"], "eq-001")
        self.assertEqual(d["parameter"], "temperature")
        self.assertEqual(d["state"], "created")

    def test_loop_with_feedforward(self):
        """测试带前馈的回路"""
        from myeap.control.feedforward import FeedforwardController

        config = ControlLoopConfig(
            loop_id="test-loop",
            equipment_id="eq-001",
            parameter="temperature",
            setpoint=100.0,
            feedforward_params=[
                {"name": "pressure", "gain": 0.5},
            ],
        )
        pid = PIDController(config.to_pid_config())
        ff = FeedforwardController()
        loop = ControlLoop(config=config, controller=pid, feedforward=ff)
        self.assertIsNotNone(loop.feedforward)

    def test_update_stats(self):
        """测试更新统计"""
        from myeap.control.models import ControlAction
        from datetime import datetime

        config = ControlLoopConfig(
            loop_id="test-loop",
            equipment_id="eq-001",
            parameter="temperature",
            setpoint=100.0,
        )
        pid = PIDController(config.to_pid_config())
        loop = ControlLoop(config=config, controller=pid)
        self.assertEqual(loop.stats.total_actions, 0)

        action = ControlAction(
            action_id="act-001",
            loop_id="test-loop",
            setpoint=100.0,
            measurement=95.0,
            error=5.0,
            output=10.0,
            timestamp=datetime.utcnow(),
        )
        loop.update_stats(action)
        self.assertEqual(loop.stats.total_actions, 1)

    def test_update_stats_multiple(self):
        """测试多次更新统计"""
        from myeap.control.models import ControlAction
        from datetime import datetime

        config = ControlLoopConfig(
            loop_id="test-loop",
            equipment_id="eq-001",
            parameter="temperature",
            setpoint=100.0,
        )
        pid = PIDController(config.to_pid_config())
        loop = ControlLoop(config=config, controller=pid)

        for i in range(10):
            action = ControlAction(
                action_id=f"act-{i:03d}",
                loop_id="test-loop",
                setpoint=100.0,
                measurement=95.0 + i,
                error=5.0 - i,
                output=10.0,
                timestamp=datetime.utcnow(),
            )
            loop.update_stats(action)

        self.assertEqual(loop.stats.total_actions, 10)
        self.assertIsNotNone(loop.stats.last_action_time)

    def test_update_stats_with_saturation(self):
        """测试饱和状态的统计更新"""
        from myeap.control.models import ControlAction

        config = ControlLoopConfig(
            loop_id="test-loop",
            equipment_id="eq-001",
            parameter="temperature",
            setpoint=100.0,
        )
        pid = PIDController(config.to_pid_config())
        loop = ControlLoop(config=config, controller=pid)

        action = ControlAction(
            action_id="act-sat",
            loop_id="test-loop",
            setpoint=100.0,
            measurement=80.0,
            error=20.0,
            output=100.0,
            saturated=True,
        )
        loop.update_stats(action)
        self.assertEqual(loop.stats.saturation_count, 1)


class TestProcessControlEngine(unittest.TestCase):
    """测试过程控制引擎"""

    def setUp(self):
        self.engine = ProcessControlEngine()

    def test_create_loop(self):
        """测试创建控制回路"""
        config = ControlLoopConfig(
            loop_id="loop-1",
            equipment_id="eq-001",
            parameter="temperature",
            setpoint=300.0,
            kp=2.0, ki=0.5, kd=0.1,
        )
        loop = self.engine.create_control_loop(config)
        self.assertIsNotNone(loop)
        self.assertEqual(loop.config.loop_id, "loop-1")
        self.assertIsInstance(loop.controller, PIDController)

    def test_create_duplicate_loop(self):
        """测试创建重复回路"""
        config = ControlLoopConfig(
            loop_id="loop-1",
            equipment_id="eq-001",
            parameter="temperature",
        )
        self.engine.create_control_loop(config)
        with self.assertRaises(ValueError):
            self.engine.create_control_loop(config)

    def test_create_adaptive_loop(self):
        """测试创建自适应回路"""
        config = ControlLoopConfig(
            loop_id="loop-2",
            equipment_id="eq-001",
            parameter="pressure",
            control_mode=ControlMode.ADAPTIVE,
            auto_tune_enabled=True,
            auto_tune_interval=50,
        )
        loop = self.engine.create_control_loop(config)
        self.assertIsInstance(loop.controller, AdaptiveController)

    def test_create_feedforward_loop(self):
        """测试创建前馈回路"""
        config = ControlLoopConfig(
            loop_id="loop-3",
            equipment_id="eq-001",
            parameter="flow",
            control_mode=ControlMode.FEEDFORWARD,
            feedforward_params=[
                {"name": "pressure", "gain": 0.5},
            ],
        )
        loop = self.engine.create_control_loop(config)
        self.assertIsNotNone(loop.feedforward)

    def test_create_cascade_loop(self):
        """测试创建级联回路"""
        config = ControlLoopConfig(
            loop_id="loop-4",
            equipment_id="eq-001",
            parameter="power",
            control_mode=ControlMode.CASCADE,
            feedforward_params=[
                {"name": "temperature", "gain": 0.3, "time_constant": 1.0},
            ],
        )
        loop = self.engine.create_control_loop(config)
        self.assertIsNotNone(loop.feedforward)

    def test_remove_loop(self):
        """测试移除回路"""
        config = ControlLoopConfig(
            loop_id="loop-rm",
            equipment_id="eq-001",
            parameter="temp",
        )
        self.engine.create_control_loop(config)
        self.assertTrue(self.engine.remove_control_loop("eq-001", "temp"))
        self.assertIsNone(self.engine.get_loop("eq-001", "temp"))

    def test_remove_nonexistent_loop(self):
        """测试移除不存在的回路"""
        self.assertFalse(self.engine.remove_control_loop("eq-999", "nonexistent"))

    def test_get_loop(self):
        """测试获取回路"""
        config = ControlLoopConfig(
            loop_id="loop-get",
            equipment_id="eq-001",
            parameter="temp",
        )
        self.engine.create_control_loop(config)
        loop = self.engine.get_loop("eq-001", "temp")
        self.assertIsNotNone(loop)
        self.assertEqual(loop.config.loop_id, "loop-get")

    def test_get_nonexistent_loop(self):
        """测试获取不存在的回路"""
        self.assertIsNone(self.engine.get_loop("eq-999", "nonexistent"))

    def test_list_loops(self):
        """测试列出所有回路"""
        config1 = ControlLoopConfig(
            loop_id="l1", equipment_id="eq-001", parameter="p1",
        )
        config2 = ControlLoopConfig(
            loop_id="l2", equipment_id="eq-001", parameter="p2",
        )
        self.engine.create_control_loop(config1)
        self.engine.create_control_loop(config2)
        loops = self.engine.list_loops()
        self.assertEqual(len(loops), 2)

    def test_list_active_loops(self):
        """测试列出活跃回路"""
        config = ControlLoopConfig(
            loop_id="l-active",
            equipment_id="eq-001",
            parameter="p1",
        )
        self.engine.create_control_loop(config)
        loop = self.engine.get_loop("eq-001", "p1")
        loop.state = ControlLoopState.RUNNING
        active = self.engine.list_active_loops()
        self.assertEqual(len(active), 1)

    def test_update_setpoint(self):
        """测试更新设定点"""
        config = ControlLoopConfig(
            loop_id="loop-sp",
            equipment_id="eq-001",
            parameter="temp",
            setpoint=100.0,
        )
        self.engine.create_control_loop(config)
        self.assertTrue(self.engine.update_setpoint("eq-001", "temp", 200.0))
        loop = self.engine.get_loop("eq-001", "temp")
        self.assertEqual(loop.config.setpoint, 200.0)
        self.assertEqual(loop.stats.setpoint_changes, 1)

    def test_update_setpoint_nonexistent(self):
        """测试更新不存在的回路设定点"""
        self.assertFalse(self.engine.update_setpoint("eq-999", "p", 100.0))

    def test_update_setpoint_adaptive(self):
        """测试更新自适应回路的设定点"""
        config = ControlLoopConfig(
            loop_id="loop-asp",
            equipment_id="eq-001",
            parameter="temp",
            control_mode=ControlMode.ADAPTIVE,
            setpoint=100.0,
        )
        self.engine.create_control_loop(config)
        self.assertTrue(self.engine.update_setpoint("eq-001", "temp", 200.0))
        loop = self.engine.get_loop("eq-001", "temp")
        self.assertEqual(loop.config.setpoint, 200.0)

    def test_get_stats(self):
        """测试获取统计"""
        config = ControlLoopConfig(
            loop_id="loop-stats",
            equipment_id="eq-001",
            parameter="temp",
        )
        self.engine.create_control_loop(config)
        stats = self.engine.get_stats("eq-001", "temp")
        self.assertIsNotNone(stats)
        self.assertIsInstance(stats, ControlLoopStats)

    def test_get_stats_nonexistent(self):
        """测试获取不存在的回路统计"""
        self.assertIsNone(self.engine.get_stats("eq-999", "p"))

    def test_get_recent_actions(self):
        """测试获取最近动作"""
        actions = self.engine.get_recent_actions()
        self.assertEqual(len(actions), 0)

    def test_get_actions_by_loop(self):
        """测试按回路获取动作"""
        actions = self.engine.get_actions_by_loop("nonexistent")
        self.assertEqual(len(actions), 0)

    def test_get_state_summary(self):
        """测试获取状态摘要"""
        state = self.engine.get_state()
        self.assertEqual(state["total_loops"], 0)
        self.assertEqual(state["active_loops"], 0)
        self.assertEqual(state["fault_loops"], 0)

    def test_get_state_with_loops(self):
        """测试有回路时的状态摘要"""
        config1 = ControlLoopConfig(
            loop_id="l1", equipment_id="eq-001", parameter="p1",
        )
        config2 = ControlLoopConfig(
            loop_id="l2", equipment_id="eq-001", parameter="p2",
        )
        self.engine.create_control_loop(config1)
        self.engine.create_control_loop(config2)

        loop1 = self.engine.get_loop("eq-001", "p1")
        loop1.state = ControlLoopState.RUNNING

        state = self.engine.get_state()
        self.assertEqual(state["total_loops"], 2)
        self.assertEqual(state["active_loops"], 1)
        self.assertEqual(len(state["loops"]), 2)

    def test_pause_resume_loop(self):
        """测试暂停和恢复回路"""
        config = ControlLoopConfig(
            loop_id="loop-pr",
            equipment_id="eq-001",
            parameter="temp",
        )
        self.engine.create_control_loop(config)
        loop = self.engine.get_loop("eq-001", "temp")
        loop.state = ControlLoopState.RUNNING

        self.assertTrue(self.engine.pause_loop("eq-001", "temp"))
        self.assertEqual(loop.state, ControlLoopState.PAUSED)

        self.assertTrue(self.engine.resume_loop("eq-001", "temp"))
        self.assertEqual(loop.state, ControlLoopState.RUNNING)

    def test_pause_nonexistent_loop(self):
        """测试暂停不存在的回路"""
        self.assertFalse(self.engine.pause_loop("eq-999", "p"))

    def test_resume_non_paused_loop(self):
        """测试恢复未暂停的回路"""
        config = ControlLoopConfig(
            loop_id="loop-np",
            equipment_id="eq-001",
            parameter="temp",
        )
        self.engine.create_control_loop(config)
        # 回路是CREATED状态，不是PAUSED
        self.assertFalse(self.engine.resume_loop("eq-001", "temp"))


class TestProcessControlEngineAsync(unittest.TestCase):
    """测试过程控制引擎异步操作"""

    def setUp(self):
        self.engine = ProcessControlEngine()

    def test_start_loop_nonexistent(self):
        """测试启动不存在的回路"""
        with self.assertRaises(ValueError):
            async def run():
                await self.engine.start_loop(
                    "eq-999", "p",
                    AsyncMock(), AsyncMock(),
                )
            asyncio.run(run())

    def test_stop_loop(self):
        """测试停止回路"""
        async def run():
            config = ControlLoopConfig(
                loop_id="loop-stop",
                equipment_id="eq-stop",
                parameter="temp",
            )
            self.engine.create_control_loop(config)
            stopped = await self.engine.stop_loop("eq-stop", "temp")
            self.assertTrue(stopped)

        asyncio.run(run())

    def test_stop_nonexistent_loop(self):
        """测试停止不存在的回路"""
        async def run():
            stopped = await self.engine.stop_loop("eq-999", "nonexistent")
            self.assertFalse(stopped)

        asyncio.run(run())

    def test_stop_all(self):
        """测试停止所有回路"""
        async def run():
            config1 = ControlLoopConfig(
                loop_id="l1", equipment_id="eq-all", parameter="p1",
            )
            config2 = ControlLoopConfig(
                loop_id="l2", equipment_id="eq-all", parameter="p2",
            )
            self.engine.create_control_loop(config1)
            self.engine.create_control_loop(config2)
            await self.engine.stop_all()
            self.assertEqual(len(self.engine.list_loops()), 2)

        asyncio.run(run())

    def test_start_and_stop_control_loop(self):
        """测试启动和停止控制回路"""
        async def run():
            config = ControlLoopConfig(
                loop_id="loop-lifecycle",
                equipment_id="eq-life",
                parameter="temp",
                sampling_interval=0.01,
            )
            self.engine.create_control_loop(config)

            reader_called = 0
            writer_called = 0

            async def mock_reader(eq, param):
                nonlocal reader_called
                reader_called += 1
                if reader_called > 3:
                    # 模拟停止
                    await self.engine.stop_loop("eq-life", "temp")
                return 100.0

            async def mock_writer(eq, param, value):
                nonlocal writer_called
                writer_called += 1

            await self.engine.start_loop(
                "eq-life", "temp",
                mock_reader, mock_writer,
                interval=0.01,
            )

            # 等待loop运行一小段时间
            await asyncio.sleep(0.1)

            loop = self.engine.get_loop("eq-life", "temp")
            self.assertIsNotNone(loop)

        asyncio.run(run())

    def test_remove_running_loop(self):
        """测试移除运行中的回路"""
        async def run():
            config = ControlLoopConfig(
                loop_id="loop-rm-r",
                equipment_id="eq-rm",
                parameter="temp",
                sampling_interval=0.01,
            )
            self.engine.create_control_loop(config)

            async def mock_reader(eq, param):
                await asyncio.sleep(0.1)
                return 100.0

            async def mock_writer(eq, param, value):
                pass

            task = self.engine.start_loop(
                "eq-rm", "temp",
                mock_reader, mock_writer,
                interval=0.01,
            )

            # 给一点时间运行
            await asyncio.sleep(0.02)

            # 移除回路
            removed = self.engine.remove_control_loop("eq-rm", "temp")
            self.assertTrue(removed)
            self.assertIsNone(self.engine.get_loop("eq-rm", "temp"))

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
