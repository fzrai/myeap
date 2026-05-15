"""流程调度器测试"""

import asyncio
import pytest

from myeap.process.engine import ProcessEngine
from myeap.process.executor import ProcessExecutor
from myeap.process.models import (
    ProcessContext,
    ProcessDefinition,
    ProcessState,
    ProcessStep,
    StepType,
)
from myeap.process.scheduler import (
    ProcessScheduler,
    Resource,
    ScheduleItem,
    SchedulePriority,
    SchedulerError,
)


# ---- 辅助函数 ----

def make_definition(process_id, step_count=2):
    """创建测试用流程定义"""
    steps = []
    transitions = {}
    for i in range(step_count):
        sid = f"s{i + 1}"
        steps.append(ProcessStep(
            step_id=sid,
            name=f"Step {i + 1}",
            step_type=StepType.PROCESS,
        ))
        if i < step_count - 1:
            transitions[sid] = f"s{i + 2}"
    return ProcessDefinition(
        process_id=process_id,
        name=f"Process {process_id}",
        equipment_type="CVD",
        steps=steps,
        transitions=transitions,
    )


def make_context(process_id, equipment_id="eq_001"):
    return ProcessContext(
        process_id=process_id,
        equipment_id=equipment_id,
    )


async def noop_handler(step, context):
    return {"ok": True}


class TestSchedulePriority:
    """优先级枚举测试"""

    def test_priority_values(self):
        assert SchedulePriority.CRITICAL.value == 0
        assert SchedulePriority.HIGH.value == 1
        assert SchedulePriority.NORMAL.value == 2
        assert SchedulePriority.LOW.value == 3
        assert SchedulePriority.IDLE.value == 4

    def test_priority_order(self):
        assert SchedulePriority.CRITICAL.value < SchedulePriority.NORMAL.value
        assert SchedulePriority.HIGH.value < SchedulePriority.LOW.value


class TestResource:
    """资源管理测试"""

    def test_creation(self):
        resource = Resource(
            resource_id="chamber_01",
            resource_type="process_chamber",
            capacity=2,
        )
        assert resource.resource_id == "chamber_01"
        assert resource.resource_type == "process_chamber"
        assert resource.capacity == 2
        assert resource.available == 2
        assert resource.is_available

    def test_allocate(self):
        resource = Resource(resource_id="r1", resource_type="test", capacity=2)
        assert resource.allocate("proc_001")
        assert resource.available == 1
        assert resource.allocated["proc_001"] == 1

    def test_allocate_multiple(self):
        resource = Resource(resource_id="r1", resource_type="test", capacity=2)
        assert resource.allocate("proc_001", 2)
        assert resource.available == 0
        assert not resource.is_available

    def test_allocate_exceed_capacity(self):
        resource = Resource(resource_id="r1", resource_type="test", capacity=1)
        resource.allocate("proc_001")
        assert not resource.allocate("proc_002")

    def test_release(self):
        resource = Resource(resource_id="r1", resource_type="test", capacity=2)
        resource.allocate("proc_001")
        assert resource.release("proc_001") == 1
        assert resource.available == 2
        assert "proc_001" not in resource.allocated

    def test_release_nonexistent(self):
        resource = Resource(resource_id="r1", resource_type="test")
        assert resource.release("nonexistent") == 0

    def test_release_all(self):
        resource = Resource(resource_id="r1", resource_type="test", capacity=3)
        resource.allocate("proc_001", 2)
        resource.allocate("proc_002", 1)
        assert resource.release_all() == 3
        assert resource.available == 3
        assert len(resource.allocated) == 0


class TestScheduleItem:
    """调度项测试"""

    def test_ordering(self):
        """优先级数字越小越优先"""
        item1 = ScheduleItem(priority=0, submit_time=1.0, process_id="p1")
        item2 = ScheduleItem(priority=1, submit_time=1.0, process_id="p2")
        assert item1 < item2

    def test_ordering_same_priority(self):
        """同优先级按提交时间排序"""
        item1 = ScheduleItem(priority=1, submit_time=1.0, process_id="p1")
        item2 = ScheduleItem(priority=1, submit_time=2.0, process_id="p2")
        assert item1 < item2


class TestProcessSchedulerResources:
    """资源管理测试"""

    def test_register_resource(self):
        scheduler = ProcessScheduler()
        resource = scheduler.register_resource("ch_01", "process_chamber", capacity=1)
        assert resource.resource_id == "ch_01"
        assert scheduler.get_resource("ch_01") is resource

    def test_register_duplicate(self):
        scheduler = ProcessScheduler()
        scheduler.register_resource("ch_01", "process_chamber")
        with pytest.raises(SchedulerError):
            scheduler.register_resource("ch_01", "process_chamber")

    def test_unregister_resource(self):
        scheduler = ProcessScheduler()
        scheduler.register_resource("ch_01", "process_chamber")
        assert scheduler.unregister_resource("ch_01")
        assert scheduler.get_resource("ch_01") is None
        assert not scheduler.unregister_resource("ch_01")

    def test_get_available_resources(self):
        scheduler = ProcessScheduler()
        scheduler.register_resource("ch_01", "process_chamber", capacity=1)
        scheduler.register_resource("ch_02", "process_chamber", capacity=1)
        scheduler.register_resource("buf_01", "buffer", capacity=2)

        available_chambers = scheduler.get_available_resources("process_chamber")
        assert len(available_chambers) == 2

    def test_try_allocate_resources(self):
        scheduler = ProcessScheduler()
        scheduler.register_resource("ch_01", "process_chamber", capacity=1)
        scheduler.set_process_resources("proc_001", {"ch_01": 1})

        assert scheduler._try_allocate_resources("proc_001")
        resource = scheduler.get_resource("ch_01")
        assert resource.available == 0

    def test_try_allocate_resources_insufficient(self):
        scheduler = ProcessScheduler()
        scheduler.register_resource("ch_01", "process_chamber", capacity=1)
        scheduler.get_resource("ch_01").allocate("other_proc")
        scheduler.set_process_resources("proc_001", {"ch_01": 1})

        assert not scheduler._try_allocate_resources("proc_001")

    def test_release_resources(self):
        scheduler = ProcessScheduler()
        scheduler.register_resource("ch_01", "process_chamber", capacity=2)
        scheduler.set_process_resources("proc_001", {"ch_01": 2})
        scheduler._try_allocate_resources("proc_001")

        scheduler._release_resources("proc_001")
        resource = scheduler.get_resource("ch_01")
        assert resource.available == 2


class TestProcessSchedulerSubmit:
    """调度提交测试"""

    @pytest.mark.asyncio
    async def test_submit(self):
        scheduler = ProcessScheduler()
        definition = make_definition("proc_001")
        context = make_context("proc_001")

        process_id = scheduler.submit(definition, context)
        assert process_id == "proc_001"
        assert len(scheduler._queue) == 1

    @pytest.mark.asyncio
    async def test_submit_with_priority(self):
        scheduler = ProcessScheduler()
        d1 = make_definition("p_low")
        d2 = make_definition("p_high")

        scheduler.submit(d1, make_context("p_low"), priority=SchedulePriority.LOW)
        scheduler.submit(d2, make_context("p_high"), priority=SchedulePriority.HIGH)

        # HIGH 应该在 LOW 前面
        item = scheduler._queue[0]  # heapq 堆顶是最小值
        assert item.process_id == "p_high"

    @pytest.mark.asyncio
    async def test_submit_duplicate(self):
        scheduler = ProcessScheduler()
        definition = make_definition("proc_001")
        context = make_context("proc_001")

        scheduler.submit(definition, context)
        with pytest.raises(SchedulerError, match="already queued"):
            scheduler.submit(definition, context)

    @pytest.mark.asyncio
    async def test_submit_with_resources(self):
        scheduler = ProcessScheduler()
        scheduler.register_resource("ch_01", "process_chamber")

        definition = make_definition("proc_001")
        context = make_context("proc_001")

        scheduler.submit(definition, context, required_resources={"ch_01": 1})
        assert "proc_001" in scheduler._process_resources
        assert scheduler._process_resources["proc_001"]["ch_01"] == 1


class TestProcessSchedulerCancel:
    """取消测试"""

    @pytest.mark.asyncio
    async def test_cancel_queued(self):
        scheduler = ProcessScheduler()
        definition = make_definition("proc_001")
        context = make_context("proc_001")

        scheduler.submit(definition, context)
        assert scheduler.cancel("proc_001")
        assert len(scheduler._queue) == 0

    @pytest.mark.asyncio
    async def test_cancel_nonexistent(self):
        scheduler = ProcessScheduler()
        assert not scheduler.cancel("nonexistent")


class TestProcessSchedulerRun:
    """调度执行测试"""

    @pytest.mark.asyncio
    async def test_run_single_process(self):
        """测试调度并运行单个流程"""
        executor = ProcessExecutor()
        executor.register_handler(StepType.PROCESS, noop_handler)
        engine = ProcessEngine(executor)

        scheduler = ProcessScheduler(engine=engine, max_concurrent=1)
        definition = make_definition("proc_001", step_count=2)
        context = make_context("proc_001")

        scheduler.submit(definition, context)

        # 启动调度器运行
        async def run_and_stop():
            await scheduler.run()

        # 创建一个任务来运行调度器并在完成后停止
        task = asyncio.create_task(scheduler.run())

        # 等待流程完成
        result = await scheduler.wait_for("proc_001", timeout=5.0)
        assert result is not None
        assert result.state == ProcessState.COMPLETED

        # 停止调度器
        await scheduler.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_run_multiple_processes(self):
        """测试调度运行多个流程"""
        executor = ProcessExecutor()
        executor.register_handler(StepType.PROCESS, noop_handler)
        engine = ProcessEngine(executor)

        scheduler = ProcessScheduler(engine=engine, max_concurrent=2)

        for pid in ["proc_001", "proc_002", "proc_003"]:
            scheduler.submit(make_definition(pid), make_context(pid))

        task = asyncio.create_task(scheduler.run())

        # 让调度器有时间启动流程
        await asyncio.sleep(0.05)

        # 等待所有流程完成
        results = await scheduler.wait_all(timeout=5.0)
        assert len(results) >= 3

        await scheduler.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_run_with_resource_constraint(self):
        """测试资源限制下的调度"""
        executor = ProcessExecutor()

        call_count = {"count": 0}

        async def counting_handler(step, context):
            call_count["count"] += 1
            await asyncio.sleep(0.02)
            return {"ok": True}

        executor.register_handler(StepType.PROCESS, counting_handler)
        engine = ProcessEngine(executor)

        scheduler = ProcessScheduler(engine=engine, max_concurrent=4)
        scheduler.register_resource("ch_01", "process_chamber", capacity=1)

        for pid in ["proc_high", "proc_low"]:
            scheduler.submit(
                make_definition(pid, step_count=1),
                make_context(pid),
                required_resources={"ch_01": 1},
            )

        task = asyncio.create_task(scheduler.run())

        # 让调度器有时间启动流程
        await asyncio.sleep(0.05)

        # 等待全部完成
        await scheduler.wait_all(timeout=10.0)
        assert call_count["count"] >= 2

        await scheduler.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class TestProcessSchedulerStatus:
    """调度器状态测试"""

    def test_get_queue_status_empty(self):
        scheduler = ProcessScheduler()
        status = scheduler.get_queue_status()
        assert status["queued"] == 0
        assert status["running"] == 0
        assert status["completed"] == 0

    @pytest.mark.asyncio
    async def test_get_queue_status_with_items(self):
        scheduler = ProcessScheduler()
        scheduler.register_resource("ch_01", "process_chamber", capacity=2)

        scheduler.submit(make_definition("p1"), make_context("p1"))
        scheduler.submit(make_definition("p2"), make_context("p2"))

        status = scheduler.get_queue_status()
        assert status["queued"] == 2
        assert len(status["queued_processes"]) == 2
        assert "ch_01" in status["resources"]

    def test_repr(self):
        scheduler = ProcessScheduler()
        r = repr(scheduler)
        assert "queued=0" in r
        assert "running=0" in r

    def test_max_concurrent_default(self):
        scheduler = ProcessScheduler()
        assert scheduler.max_concurrent == 4

    def test_engine_default(self):
        scheduler = ProcessScheduler()
        assert isinstance(scheduler.engine, ProcessEngine)


class TestProcessSchedulerCallbacks:
    """调度器回调测试"""

    @pytest.mark.asyncio
    async def test_on_process_queued(self):
        executor = ProcessExecutor()
        executor.register_handler(StepType.PROCESS, noop_handler)
        engine = ProcessEngine(executor)

        scheduler = ProcessScheduler(engine=engine)
        queued = []

        async def on_queued(context):
            queued.append(context.process_id)

        scheduler.on_process_queued = on_queued

        scheduler.submit(make_definition("proc_001"), make_context("proc_001"))
        # 让事件循环处理已调度的异步回调
        await asyncio.sleep(0)
        assert len(queued) == 1

    @pytest.mark.asyncio
    async def test_on_process_completed(self):
        executor = ProcessExecutor()
        executor.register_handler(StepType.PROCESS, noop_handler)
        engine = ProcessEngine(executor)

        scheduler = ProcessScheduler(engine=engine, max_concurrent=1)
        completed = []

        def on_completed(context):
            completed.append(context.process_id)

        scheduler.on_process_completed = on_completed

        scheduler.submit(make_definition("proc_001"), make_context("proc_001"))

        task = asyncio.create_task(scheduler.run())
        await scheduler.wait_for("proc_001", timeout=5.0)
        assert len(completed) == 1

        await scheduler.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
