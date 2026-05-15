"""数据采集器

从SECS/GEM设备收集工艺数据，支持实时采集、采样率控制和批量存储。
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from myeap.data.models import DataPoint, DataBatch
from myeap.data.sampler import DataSampler
from myeap.data.storage import DataStorage

logger = logging.getLogger(__name__)


class DataCollector:
    """数据采集器

    从SECS/GEM设备收集工艺数据：
    - 实时数据收集
    - 采样率控制
    - 数据缓冲
    - 批量存储

    Attributes:
        storage: 数据存储实例
        sampler: 数据采样器实例
        on_data_callback: 数据回调函数（可选）

    Example:
        collector = DataCollector(storage=storage, sampler=sampler)
        await collector.start_collecting("eq-001", ["Temperature", "Pressure"])
    """

    def __init__(
        self,
        storage: DataStorage,
        sampler: DataSampler,
        on_data_callback: Optional[Callable[[DataBatch], None]] = None,
    ):
        """初始化数据采集器

        Args:
            storage: 数据存储实例
            sampler: 数据采样器实例
            on_data_callback: 数据回调函数（可选）
        """
        self.storage = storage
        self.sampler = sampler
        self.on_data_callback = on_data_callback
        self._running = False
        self._tasks: Dict[str, asyncio.Task] = {}
        self._parameter_reader: Optional[Callable[[str, str], float]] = None

    def set_parameter_reader(
        self,
        reader: Callable[[str, str], float],
    ) -> None:
        """设置参数读取函数

        Args:
            reader: 读取函数，接收(equipment_id, parameter_name)，返回参数值
        """
        self._parameter_reader = reader

    async def start_collecting(
        self,
        equipment_id: str,
        parameters: List[str],
        sampling_interval: float = 1.0,
        sampling_strategy: str = "time_based",
    ) -> None:
        """开始采集

        Args:
            equipment_id: 设备ID
            parameters: 要采集的参数列表
            sampling_interval: 采样间隔（秒）
            sampling_strategy: 采样策略 (time_based, change_based, statistical, smart)
        """
        if equipment_id in self._tasks:
            logger.warning(f"Already collecting from {equipment_id}")
            return

        self._running = True
        task = asyncio.create_task(
            self._collect_loop(
                equipment_id,
                parameters,
                sampling_interval,
                sampling_strategy,
            )
        )
        self._tasks[equipment_id] = task
        logger.info(
            f"Started collecting from {equipment_id} "
            f"(interval={sampling_interval}s, strategy={sampling_strategy})"
        )

    async def stop_collecting(self, equipment_id: str) -> None:
        """停止采集

        Args:
            equipment_id: 设备ID
        """
        if equipment_id not in self._tasks:
            logger.warning(f"Not collecting from {equipment_id}")
            return

        self._tasks[equipment_id].cancel()
        try:
            await self._tasks[equipment_id]
        except asyncio.CancelledError:
            pass
        del self._tasks[equipment_id]
        logger.info(f"Stopped collecting from {equipment_id}")

    async def stop_all(self) -> None:
        """停止所有采集任务"""
        self._running = False
        for equipment_id in list(self._tasks.keys()):
            await self.stop_collecting(equipment_id)

    async def _collect_loop(
        self,
        equipment_id: str,
        parameters: List[str],
        interval: float,
        strategy: str,
    ) -> None:
        """采集循环

        Args:
            equipment_id: 设备ID
            parameters: 参数列表
            interval: 采样间隔
            strategy: 采样策略
        """
        while self._running:
            try:
                # 收集数据
                batch = await self._collect_batch(equipment_id, parameters)

                if not batch.points:
                    await asyncio.sleep(interval)
                    continue

                # 采样
                sampled_points = self.sampler.sample(batch.points, strategy)

                # 创建采样后的批次
                sampled_batch = DataBatch(
                    equipment_id=equipment_id,
                    chamber_id=batch.chamber_id,
                    points=sampled_points,
                    collected_at=datetime.now(timezone.utc),
                )

                # 存储
                await self.storage.store_batch(sampled_batch)

                # 回调
                if self.on_data_callback:
                    self.on_data_callback(sampled_batch)

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error collecting from {equipment_id}: {e}")
                await asyncio.sleep(interval)

    async def _collect_batch(
        self,
        equipment_id: str,
        parameters: List[str],
    ) -> DataBatch:
        """收集一批数据

        Args:
            equipment_id: 设备ID
            parameters: 参数列表

        Returns:
            DataBatch: 采集的数据批次
        """
        points = []
        for param in parameters:
            value = await self._read_parameter(equipment_id, param)
            points.append(DataPoint(
                equipment_id=equipment_id,
                chamber_id=None,
                parameter_name=param,
                value=value,
                unit=None,
                timestamp=datetime.now(timezone.utc),
            ))
        return DataBatch(equipment_id, points, None, datetime.now(timezone.utc))

    async def _read_parameter(
        self,
        equipment_id: str,
        parameter_name: str,
    ) -> float:
        """读取参数值

        Args:
            equipment_id: 设备ID
            parameter_name: 参数名称

        Returns:
            float: 参数值
        """
        if self._parameter_reader:
            return await self._parameter_reader(equipment_id, parameter_name)
        # 默认返回模拟值
        import random
        return random.uniform(0, 100)

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running

    @property
    def active_equipment(self) -> List[str]:
        """正在采集的设备列表"""
        return list(self._tasks.keys())

    @property
    def task_count(self) -> int:
        """活跃任务数量"""
        return len(self._tasks)
