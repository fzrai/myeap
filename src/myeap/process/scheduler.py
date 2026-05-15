"""工艺流程调度器

管理多个并发流程的执行、资源分配和优先级调度。
"""

import asyncio
import heapq
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from dataclasses import dataclass, field

from myeap.core.exceptions import MyEAPException
from myeap.process.engine import ProcessEngine
from myeap.process.executor import ProcessExecutor
from myeap.process.models import (
    ProcessContext,
    ProcessDefinition,
    ProcessState,
)

logger = logging.getLogger(__name__)


class SchedulerError(MyEAPException):
    """调度器错误"""

    def __init__(self, message: str, **kwargs: Any):
        super().__init__(message, code="SCHEDULER_ERROR", **kwargs)


class SchedulePriority(Enum):
    """调度优先级"""

    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    IDLE = 4


@dataclass(order=True)
class ScheduleItem:
    """调度项

    用于优先级队列中的排序。priority 越小越优先。
    """

    priority: int
    submit_time: float
    process_id: str = field(compare=False)
    definition: Optional[ProcessDefinition] = field(compare=False, default=None)
    context: Optional[ProcessContext] = field(compare=False, default=None)


@dataclass
class Resource:
    """资源定义

    表示一个可分配的资源（如腔体、传感器等）。

    Attributes:
        resource_id: 资源唯一标识
        resource_type: 资源类型
        capacity: 总容量
        available: 当前可用容量
        allocated: 已分配的资源使用记录
    """

    resource_id: str
    resource_type: str
    capacity: int = 1
    available: int = field(init=False)
    allocated: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        self.available = self.capacity  # process_id -> count

    @property
    def is_available(self) -> bool:
        """资源是否可用"""
        return self.available > 0

    def allocate(self, process_id: str, count: int = 1) -> bool:
        """分配资源

        Args:
            process_id: 流程ID
            count: 分配数量

        Returns:
            bool: 是否分配成功
        """
        if self.available < count:
            return False
        self.available -= count
        self.allocated[process_id] = self.allocated.get(process_id, 0) + count
        return True

    def release(self, process_id: str) -> int:
        """释放资源

        Args:
            process_id: 流程ID

        Returns:
            int: 释放的数量
        """
        count = self.allocated.pop(process_id, 0)
        self.available += count
        return count

    def release_all(self) -> int:
        """释放所有已分配的资源

        Returns:
            int: 释放的总数量
        """
        total = sum(self.allocated.values())
        self.allocated.clear()
        self.available = self.capacity
        return total


class ProcessScheduler:
    """工艺调度器

    管理多个并发流程的执行、资源分配和优先级调度。

    Attributes:
        engine: 流程引擎
        max_concurrent: 最大并发流程数
        on_process_queued: 流程入队回调
        on_process_started: 流程开始回调
        on_process_completed: 流程完成回调

    Example:
        >>> scheduler = ProcessScheduler(max_concurrent=4)
        >>> scheduler.register_resource("chamber_01", "process_chamber", capacity=1)
        >>> scheduler.register_resource("chamber_02", "process_chamber", capacity=1)
        >>> scheduler.submit(definition, context, priority=SchedulePriority.NORMAL)
        >>> await scheduler.run()
    """

    def __init__(
        self,
        engine: Optional[ProcessEngine] = None,
        max_concurrent: int = 4,
    ):
        """初始化调度器

        Args:
            engine: 流程引擎，如果为None则创建默认引擎
            max_concurrent: 最大并发流程数
        """
        self.engine = engine or ProcessEngine()
        self.max_concurrent = max_concurrent

        # 资源管理
        self._resources: Dict[str, Resource] = {}

        # 调度队列 (最小堆)
        self._queue: List[ScheduleItem] = []

        # 活跃执行任务
        self._running_tasks: Dict[str, asyncio.Task] = {}

        # 完成的上下文
        self._completed: Dict[str, ProcessContext] = {}

        # 调度状态
        self._is_running = False
        self._stop_requested = False

        # 资源需求注册
        self._process_resources: Dict[str, Dict[str, int]] = {}  # process_id -> {resource_id: count}

        # 回调
        self.on_process_queued: Optional[Callable[[ProcessContext], Any]] = None
        self.on_process_started: Optional[Callable[[ProcessContext], Any]] = None
        self.on_process_completed: Optional[Callable[[ProcessContext], Any]] = None

    # ---- 资源管理 ----

    def register_resource(
        self,
        resource_id: str,
        resource_type: str,
        capacity: int = 1,
    ) -> Resource:
        """注册资源

        Args:
            resource_id: 资源ID
            resource_type: 资源类型
            capacity: 资源容量

        Returns:
            Resource: 注册的资源对象

        Raises:
            SchedulerError: 如果资源已存在
        """
        if resource_id in self._resources:
            raise SchedulerError(f"Resource '{resource_id}' already registered")

        resource = Resource(
            resource_id=resource_id,
            resource_type=resource_type,
            capacity=capacity,
        )
        self._resources[resource_id] = resource
        logger.debug(f"Registered resource: {resource_id} ({resource_type}, capacity={capacity})")
        return resource

    def unregister_resource(self, resource_id: str) -> bool:
        """注销资源

        Args:
            resource_id: 资源ID

        Returns:
            bool: 是否成功注销
        """
        if resource_id in self._resources:
            del self._resources[resource_id]
            return True
        return False

    def get_resource(self, resource_id: str) -> Optional[Resource]:
        """获取资源"""
        return self._resources.get(resource_id)

    def get_available_resources(self, resource_type: Optional[str] = None) -> List[Resource]:
        """获取可用资源列表

        Args:
            resource_type: 资源类型过滤（可选）

        Returns:
            List[Resource]: 可用资源列表
        """
        resources = self._resources.values()
        if resource_type:
            resources = [r for r in resources if r.resource_type == resource_type]
        return [r for r in resources if r.is_available]

    def set_process_resources(
        self,
        process_id: str,
        required_resources: Dict[str, int],
    ) -> None:
        """设置流程所需资源

        Args:
            process_id: 流程ID
            required_resources: 所需资源映射 {resource_id: count}
        """
        self._process_resources[process_id] = required_resources

    def _try_allocate_resources(self, process_id: str) -> bool:
        """尝试为流程分配资源

        Args:
            process_id: 流程ID

        Returns:
            bool: 是否分配成功
        """
        required = self._process_resources.get(process_id, {})
        if not required:
            return True  # 无需资源即可运行

        # 检查所有资源是否足够
        for resource_id, count in required.items():
            resource = self._resources.get(resource_id)
            if not resource or resource.available < count:
                return False

        # 分配资源
        for resource_id, count in required.items():
            resource = self._resources[resource_id]
            resource.allocate(process_id, count)

        return True

    def _release_resources(self, process_id: str) -> None:
        """释放流程占用的资源

        Args:
            process_id: 流程ID
        """
        for resource in self._resources.values():
            if process_id in resource.allocated:
                resource.release(process_id)

    # ---- 调度操作 ----

    def submit(
        self,
        definition: ProcessDefinition,
        context: ProcessContext,
        priority: SchedulePriority = SchedulePriority.NORMAL,
        required_resources: Optional[Dict[str, int]] = None,
    ) -> str:
        """提交流程到调度队列

        Args:
            definition: 流程定义
            context: 执行上下文
            priority: 优先级
            required_resources: 所需资源 (可选)

        Returns:
            str: 流程ID

        Raises:
            SchedulerError: 如果流程已在队列中
        """
        process_id = context.process_id

        # 检查是否已存在
        for item in self._queue:
            if item.process_id == process_id:
                raise SchedulerError(
                    f"Process '{process_id}' is already queued"
                )

        if process_id in self._running_tasks:
            raise SchedulerError(
                f"Process '{process_id}' is already running"
            )

        # 设置所需资源
        if required_resources:
            self._process_resources[process_id] = required_resources

        # 创建调度项
        item = ScheduleItem(
            priority=priority.value,
            submit_time=datetime.utcnow().timestamp(),
            process_id=process_id,
            definition=definition,
            context=context,
        )

        heapq.heappush(self._queue, item)

        context.state = ProcessState.READY
        logger.info(
            f"Process '{process_id}' submitted to queue "
            f"(priority={priority.name}, queue_size={len(self._queue)})"
        )

        if self.on_process_queued:
            try:
                result = self.on_process_queued(context)
                if asyncio.iscoroutine(result):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)
                    except RuntimeError:
                        pass
            except Exception:
                pass

        return process_id

    def cancel(self, process_id: str) -> bool:
        """从调度队列中取消流程

        Args:
            process_id: 流程ID

        Returns:
            bool: 是否成功取消
        """
        for i, item in enumerate(self._queue):
            if item.process_id == process_id:
                self._queue.pop(i)
                heapq.heapify(self._queue)
                self._process_resources.pop(process_id, None)
                logger.info(f"Process '{process_id}' cancelled from queue")
                return True

        # 尝试中止正在运行的流程
        if process_id in self._running_tasks:
            # 使用事件循环中止
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.engine.abort(process_id))
                return True
            except RuntimeError:
                pass

        return False

    def get_queue_status(self) -> Dict[str, Any]:
        """获取调度队列状态

        Returns:
            Dict: 包含队列和运行信息的字典
        """
        return {
            "queued": len(self._queue),
            "running": len(self._running_tasks),
            "completed": len(self._completed),
            "queued_processes": [
                {
                    "process_id": item.process_id,
                    "priority": SchedulePriority(item.priority).name,
                    "wait_time": datetime.utcnow().timestamp() - item.submit_time,
                }
                for item in sorted(self._queue, key=lambda i: i.priority)
            ],
            "running_processes": list(self._running_tasks.keys()),
            "resources": {
                rid: {
                    "type": r.resource_type,
                    "capacity": r.capacity,
                    "available": r.available,
                    "allocated": dict(r.allocated),
                }
                for rid, r in self._resources.items()
            },
        }

    async def run(self) -> None:
        """运行调度器

        持续从队列中取出流程并执行，直到队列为空且所有流程完成，
        或收到停止请求。
        """
        if self._is_running:
            raise SchedulerError("Scheduler is already running")

        self._is_running = True
        self._stop_requested = False

        logger.info(
            f"Scheduler started (max_concurrent={self.max_concurrent})"
        )

        try:
            while not self._stop_requested:
                # 尝试启动更多流程
                while (
                    len(self._running_tasks) < self.max_concurrent
                    and self._queue
                ):
                    item = heapq.heappop(self._queue)

                    # 尝试分配资源
                    if self._try_allocate_resources(item.process_id):
                        task = asyncio.create_task(
                            self._execute_process(item.definition, item.context)
                        )
                        self._running_tasks[item.process_id] = task
                        logger.info(
                            f"Process '{item.process_id}' started "
                            f"(running={len(self._running_tasks)})"
                        )

                        if self.on_process_started:
                            try:
                                result = self.on_process_started(item.context)
                                if asyncio.iscoroutine(result):
                                    await result
                            except Exception:
                                pass
                    else:
                        # 资源不足，放回队列
                        heapq.heappush(self._queue, item)
                        break  # 等待资源释放

                # 如果没有活跃任务且队列为空，退出
                if not self._running_tasks and not self._queue:
                    logger.info("Scheduler idle, all processes completed")
                    break

                # 等待一段时间或某个任务完成
                if self._running_tasks:
                    done, _ = await asyncio.wait(
                        list(self._running_tasks.values()),
                        timeout=1.0,
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    # 清理已完成的任务
                    for task in done:
                        self._cleanup_task(task)
                else:
                    await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            logger.info("Scheduler cancelled")
        except Exception as e:
            logger.exception(f"Scheduler error: {e}")
        finally:
            self._is_running = False
            logger.info("Scheduler stopped")

    async def stop(self, graceful: bool = True) -> None:
        """停止调度器

        Args:
            graceful: 是否优雅停止（完成当前流程后停止）
        """
        self._stop_requested = True

        if not graceful:
            # 中止所有运行中的流程
            for process_id in list(self._running_tasks.keys()):
                await self.engine.abort(process_id)

    async def _execute_process(
        self,
        definition: ProcessDefinition,
        context: ProcessContext,
    ) -> None:
        """执行单个流程

        Args:
            definition: 流程定义
            context: 执行上下文
        """
        try:
            await self.engine.execute(definition, context)

        except Exception as e:
            logger.exception(f"Process '{context.process_id}' error: {e}")
            context.state = ProcessState.FAILED
            context.error = str(e)
            context.completed_at = datetime.utcnow()

        finally:
            self._release_resources(context.process_id)
            # 保存完成上下文（引擎执行后会将其从活跃列表移除）
            self._completed[context.process_id] = context

            if self.on_process_completed:
                try:
                    result = self.on_process_completed(context)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:
                    pass

    def _cleanup_task(self, task: asyncio.Task) -> None:
        """清理已完成的任务

        Args:
            task: 已完成的任务
        """
        for process_id, t in list(self._running_tasks.items()):
            if t is task:
                del self._running_tasks[process_id]

                logger.info(
                    f"Process '{process_id}' completed "
                    f"(completed={len(self._completed)})"
                )

                # 清理资源需求记录
                self._process_resources.pop(process_id, None)
                break

    async def wait_for(self, process_id: str, timeout: Optional[float] = None) -> Optional[ProcessContext]:
        """等待指定流程完成

        Args:
            process_id: 流程ID
            timeout: 超时时间（秒）

        Returns:
            Optional[ProcessContext]: 流程上下文，超时返回None
        """
        start = datetime.utcnow()

        while True:
            # 检查是否已完成
            context = self._completed.get(process_id)
            if context:
                return context

            # 检查是否还在运行或排队
            in_queue = any(
                item.process_id == process_id for item in self._queue
            )
            in_running = process_id in self._running_tasks

            if not in_queue and not in_running:
                return self.engine.get_context(process_id)

            # 检查超时
            if timeout:
                elapsed = (datetime.utcnow() - start).total_seconds()
                if elapsed >= timeout:
                    return None

            await asyncio.sleep(0.1)

    async def wait_all(self, timeout: Optional[float] = None) -> Dict[str, ProcessContext]:
        """等待所有流程完成

        Args:
            timeout: 超时时间（秒）

        Returns:
            Dict[str, ProcessContext]: 所有流程的上下文
        """
        if self._running_tasks:
            tasks = list(self._running_tasks.values())
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                pass

        return dict(self._completed)

    def __repr__(self) -> str:
        return (
            f"ProcessScheduler(queued={len(self._queue)}, "
            f"running={len(self._running_tasks)}, "
            f"completed={len(self._completed)})"
        )
