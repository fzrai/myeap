"""工艺控制测试"""

import pytest
from datetime import datetime, timedelta

from myeap.device.process import (
    ProcessInstance,
    ProcessManager,
    ProcessState,
    ProcessStep,
)


class TestProcessState:
    """工艺状态测试"""

    def test_state_values(self):
        """测试状态值"""
        assert ProcessState.QUEUED.value == "QUEUED"
        assert ProcessState.RUNNING.value == "RUNNING"
        assert ProcessState.COMPLETED.value == "COMPLETED"


class TestProcessStep:
    """工艺步骤测试"""

    def test_creation(self):
        """测试创建步骤"""
        step = ProcessStep(
            step_id=0,
            name="Preheat",
            duration=60.0,
        )
        assert step.step_id == 0
        assert step.name == "Preheat"
        assert not step.is_completed

    def test_elapsed_time(self):
        """测试已用时间计算"""
        step = ProcessStep(
            step_id=0,
            name="Test",
            duration=60.0,
        )
        step.started_at = datetime.utcnow() - timedelta(seconds=30)
        assert step.elapsed_time == pytest.approx(30.0, rel=1)

    def test_progress(self):
        """测试进度计算"""
        step = ProcessStep(
            step_id=0,
            name="Test",
            duration=100.0,
        )

        # 未开始
        assert step.progress == 0.0

        # 进行中
        step.started_at = datetime.utcnow() - timedelta(seconds=50)
        assert step.progress == pytest.approx(0.5, rel=0.1)

        # 已完成
        step.completed_at = datetime.utcnow()
        assert step.progress == 1.0


class TestProcessInstance:
    """工艺实例测试"""

    def test_creation(self):
        """测试创建工艺实例"""
        process = ProcessInstance(
            process_id="proc-001",
            equipment_id="eq-001",
            chamber_id="ch-01",
            recipe_id="recipe-01",
            recipe_name="Clean Recipe",
        )
        assert process.process_id == "proc-001"
        assert process.state == ProcessState.QUEUED
        assert process.progress == 0.0

    def test_is_active(self):
        """测试活跃状态判断"""
        process = ProcessInstance(
            process_id="proc-001",
            equipment_id="eq-001",
            chamber_id="ch-01",
            recipe_id="recipe-01",
            recipe_name="Test",
        )

        assert not process.is_active  # QUEUED
        process.start()
        assert process.is_active
        process.pause()
        assert process.is_active
        process.complete()
        assert not process.is_active

    def test_is_terminal(self):
        """测试终态判断"""
        process = ProcessInstance(
            process_id="proc-001",
            equipment_id="eq-001",
            chamber_id="ch-01",
            recipe_id="recipe-01",
            recipe_name="Test",
        )

        assert not process.is_terminal
        process.complete()
        assert process.is_terminal

        process.abort()
        assert process.is_terminal

    def test_state_transitions(self):
        """测试状态转换"""
        process = ProcessInstance(
            process_id="proc-001",
            equipment_id="eq-001",
            chamber_id="ch-01",
            recipe_id="recipe-01",
            recipe_name="Test",
        )

        # QUEUED -> RUNNING
        process.start()
        assert process.state == ProcessState.RUNNING
        assert process.started_at is not None

        # RUNNING -> PAUSED
        process.pause()
        assert process.state == ProcessState.PAUSED
        assert process.paused_at is not None

        # PAUSED -> RUNNING
        process.resume()
        assert process.state == ProcessState.RUNNING

        # RUNNING -> COMPLETED
        process.complete({"yield": 99.5})
        assert process.state == ProcessState.COMPLETED
        assert process.completed_at is not None
        assert process.result["yield"] == 99.5

    def test_abort_and_fail(self):
        """测试中止和失败"""
        process = ProcessInstance(
            process_id="proc-001",
            equipment_id="eq-001",
            chamber_id="ch-01",
            recipe_id="recipe-01",
            recipe_name="Test",
        )
        process.start()

        process.abort()
        assert process.state == ProcessState.ABORTED

        process.start()  # 重新开始
        process.fail("Temperature exceeded limit")
        assert process.state == ProcessState.FAILED
        assert process.error_message == "Temperature exceeded limit"

    def test_steps_management(self):
        """测试步骤管理"""
        process = ProcessInstance(
            process_id="proc-001",
            equipment_id="eq-001",
            chamber_id="ch-01",
            recipe_id="recipe-01",
            recipe_name="Test",
        )

        # 添加步骤
        process.steps = [
            ProcessStep(step_id=0, name="Step 1", duration=60.0),
            ProcessStep(step_id=1, name="Step 2", duration=120.0),
            ProcessStep(step_id=2, name="Step 3", duration=60.0),
        ]

        assert len(process.steps) == 3
        assert process.current_step_info.name == "Step 1"

        # 移动到下一步
        process.move_to_step(1)
        assert process.current_step == 1
        assert process.current_step_info.name == "Step 2"

    def test_data_collection(self):
        """测试数据收集"""
        process = ProcessInstance(
            process_id="proc-001",
            equipment_id="eq-001",
            chamber_id="ch-01",
            recipe_id="recipe-01",
            recipe_name="Test",
        )

        process.add_data_point(0, "W001", {"temperature": 150.0, "pressure": 10.0})
        process.add_data_point(1, "W001", {"temperature": 160.0, "pressure": 12.0})

        assert len(process.data_points) == 2
        assert process.data_points[0].step_id == 0
        assert process.data_points[0].wafer_id == "W001"

    def test_comments(self):
        """测试评论功能"""
        process = ProcessInstance(
            process_id="proc-001",
            equipment_id="eq-001",
            chamber_id="ch-01",
            recipe_id="recipe-01",
            recipe_name="Test",
        )

        process.add_comment("Started process", "operator1")
        assert len(process.comments) == 1
        assert "operator1" in process.comments[0]

    def test_wafer_tracking(self):
        """测试晶圆追踪"""
        process = ProcessInstance(
            process_id="proc-001",
            equipment_id="eq-001",
            chamber_id="ch-01",
            recipe_id="recipe-01",
            recipe_name="Test",
            wafer_ids=["W001", "W002", "W003"],
            lot_id="LOT-001",
        )

        assert len(process.wafer_ids) == 3
        assert process.lot_id == "LOT-001"

    def test_to_dict(self):
        """测试转换为字典"""
        process = ProcessInstance(
            process_id="proc-001",
            equipment_id="eq-001",
            chamber_id="ch-01",
            recipe_id="recipe-01",
            recipe_name="Test Recipe",
        )
        process.start()

        data = process.to_dict()
        assert data["process_id"] == "proc-001"
        assert data["state"] == "RUNNING"
        assert data["progress"] > 0


class TestProcessManager:
    """工艺管理器测试"""

    def test_creation(self):
        """测试创建管理器"""
        manager = ProcessManager("eq-001")
        assert manager.equipment_id == "eq-001"

    def test_process_operations(self):
        """测试工艺操作"""
        manager = ProcessManager("eq-001")

        process = ProcessInstance(
            process_id="proc-001",
            equipment_id="eq-001",
            chamber_id="ch-01",
            recipe_id="recipe-01",
            recipe_name="Test",
        )
        manager.add_process(process)

        assert manager.get_process("proc-001") is not None
        assert len(manager.get_all_processes()) == 1

    def test_get_active_processes(self):
        """测试获取活跃工艺"""
        manager = ProcessManager("eq-001")

        # 添加不同状态的工艺
        p1 = ProcessInstance(
            process_id="proc-001",
            equipment_id="eq-001",
            chamber_id="ch-01",
            recipe_id="recipe-01",
            recipe_name="Test 1",
        )
        p1.start()

        p2 = ProcessInstance(
            process_id="proc-002",
            equipment_id="eq-001",
            chamber_id="ch-01",
            recipe_id="recipe-01",
            recipe_name="Test 2",
        )
        p2.complete()

        p3 = ProcessInstance(
            process_id="proc-003",
            equipment_id="eq-001",
            chamber_id="ch-02",
            recipe_id="recipe-01",
            recipe_name="Test 3",
        )
        p3.start()

        manager.add_process(p1)
        manager.add_process(p2)
        manager.add_process(p3)

        assert len(manager.get_active_processes()) == 2

    def test_get_chamber_process(self):
        """测试获取腔体工艺"""
        manager = ProcessManager("eq-001")

        p1 = ProcessInstance(
            process_id="proc-001",
            equipment_id="eq-001",
            chamber_id="ch-01",
            recipe_id="recipe-01",
            recipe_name="Test 1",
        )
        p1.start()

        p2 = ProcessInstance(
            process_id="proc-002",
            equipment_id="eq-001",
            chamber_id="ch-02",
            recipe_id="recipe-01",
            recipe_name="Test 2",
        )
        p2.start()

        manager.add_process(p1)
        manager.add_process(p2)

        assert len(manager.get_chamber_processes("ch-01")) == 1
        assert manager.get_chamber_active_process("ch-01").process_id == "proc-001"
        assert manager.get_chamber_active_process("ch-99") is None
