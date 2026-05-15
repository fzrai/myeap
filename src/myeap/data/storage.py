"""数据存储

提供数据存储抽象，支持多种存储后端。
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from myeap.data.models import DataBatch, DataPoint

logger = logging.getLogger(__name__)


class DataStorage(ABC):
    """数据存储抽象基类

    定义数据存储接口，支持不同的存储后端。
    """

    @abstractmethod
    async def store_batch(self, batch: DataBatch) -> bool:
        """存储数据批次

        Args:
            batch: 数据批次

        Returns:
            bool: 存储是否成功
        """
        pass

    @abstractmethod
    async def store_point(self, point: DataPoint) -> bool:
        """存储单个数据点

        Args:
            point: 数据点

        Returns:
            bool: 存储是否成功
        """
        pass

    @abstractmethod
    async def get_points(
        self,
        equipment_id: str,
        parameter_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[DataPoint]:
        """获取数据点

        Args:
            equipment_id: 设备ID
            parameter_name: 参数名称（可选）
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制

        Returns:
            数据点列表
        """
        pass

    @abstractmethod
    async def delete_points(
        self,
        equipment_id: str,
        before_time: datetime,
    ) -> int:
        """删除数据点

        Args:
            equipment_id: 设备ID
            before_time: 删除此时间之前的点

        Returns:
            删除的数据点数量
        """
        pass

    async def close(self) -> None:
        """关闭存储连接"""
        pass


class InMemoryDataStorage(DataStorage):
    """内存数据存储

    简单的内存存储实现，用于测试或小规模数据。
    """

    def __init__(self, max_points: int = 100000):
        """初始化内存存储

        Args:
            max_points: 最大存储点数
        """
        self.max_points = max_points
        self._points: List[DataPoint] = []
        self._lock = asyncio.Lock()

    async def store_batch(self, batch: DataBatch) -> bool:
        """存储数据批次"""
        async with self._lock:
            for point in batch.points:
                self._points.append(point)
            # 保持数据量在限制内
            if len(self._points) > self.max_points:
                self._points = self._points[-self.max_points:]
            return True

    async def store_point(self, point: DataPoint) -> bool:
        """存储单个数据点"""
        async with self._lock:
            self._points.append(point)
            if len(self._points) > self.max_points:
                self._points = self._points[-self.max_points:]
            return True

    async def get_points(
        self,
        equipment_id: str,
        parameter_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[DataPoint]:
        """获取数据点"""
        async with self._lock:
            filtered = []
            for point in self._points:
                if point.equipment_id != equipment_id:
                    continue
                if parameter_name and point.parameter_name != parameter_name:
                    continue
                if start_time and point.timestamp < start_time:
                    continue
                if end_time and point.timestamp > end_time:
                    continue
                filtered.append(point)

            # 按时间排序
            filtered.sort(key=lambda p: p.timestamp)
            return filtered[-limit:]

    async def delete_points(
        self,
        equipment_id: str,
        before_time: datetime,
    ) -> int:
        """删除数据点"""
        async with self._lock:
            original_count = len(self._points)
            self._points = [
                p for p in self._points
                if not (p.equipment_id == equipment_id and p.timestamp < before_time)
            ]
            return original_count - len(self._points)

    @property
    def point_count(self) -> int:
        """当前存储的点数"""
        return len(self._points)

    def clear(self) -> None:
        """清空所有数据"""
        self._points.clear()


class BufferingDataStorage(DataStorage):
    """缓冲数据存储

    包装另一个存储，在内存中缓冲数据，批量写入。
    适用于高频率写入场景。
    """

    def __init__(
        self,
        backend: DataStorage,
        buffer_size: int = 100,
        flush_interval: float = 5.0,
    ):
        """初始化缓冲存储

        Args:
            backend: 底层存储后端
            buffer_size: 缓冲区大小
            flush_interval: 刷新间隔（秒）
        """
        self.backend = backend
        self._buffer_size = buffer_size
        self.flush_interval = flush_interval
        self._buffer: List[DataPoint] = []
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False

    @property
    def buffer_size(self) -> int:
        """当前缓冲区大小"""
        return len(self._buffer)

    async def start(self) -> None:
        """启动缓冲存储"""
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def stop(self) -> None:
        """停止缓冲存储"""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self.flush()

    async def _flush_loop(self) -> None:
        """刷新循环"""
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval)
                await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in flush loop: {e}")

    async def flush(self) -> None:
        """刷新缓冲区"""
        async with self._lock:
            if not self._buffer:
                return

            points_to_store = self._buffer.copy()
            self._buffer.clear()

        # 批量存储
        for point in points_to_store:
            await self.backend.store_point(point)

        logger.debug(f"Flushed {len(points_to_store)} points")

    async def store_batch(self, batch: DataBatch) -> bool:
        """存储数据批次"""
        async with self._lock:
            for point in batch.points:
                self._buffer.append(point)
            if len(self._buffer) >= self._buffer_size:
                asyncio.create_task(self.flush())
            return True

    async def store_point(self, point: DataPoint) -> bool:
        """存储单个数据点"""
        async with self._lock:
            self._buffer.append(point)
            if len(self._buffer) >= self._buffer_size:
                asyncio.create_task(self.flush())
            return True

    async def get_points(
        self,
        equipment_id: str,
        parameter_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[DataPoint]:
        """获取数据点（从后端）"""
        return await self.backend.get_points(
            equipment_id,
            parameter_name,
            start_time,
            end_time,
            limit,
        )

    async def delete_points(
        self,
        equipment_id: str,
        before_time: datetime,
    ) -> int:
        """删除数据点"""
        return await self.backend.delete_points(equipment_id, before_time)


class MetricsCollectingStorage(DataStorage):
    """带指标收集的存储

    包装另一个存储，收集存储指标。
    """

    def __init__(
        self,
        backend: DataStorage,
        on_store: Optional[callable] = None,
    ):
        """初始化带指标的存储

        Args:
            backend: 底层存储后端
            on_store: 存储回调，接收存储的点数
        """
        self.backend = backend
        self.on_store = on_store
        self._total_points_stored = 0
        self._total_batches_stored = 0
        self._total_errors = 0

    async def store_batch(self, batch: DataBatch) -> bool:
        """存储数据批次"""
        try:
            result = await self.backend.store_batch(batch)
            if result:
                self._total_points_stored += len(batch.points)
                self._total_batches_stored += 1
                if self.on_store:
                    self.on_store(len(batch.points))
            return result
        except Exception as e:
            self._total_errors += 1
            logger.error(f"Error storing batch: {e}")
            raise

    async def store_point(self, point: DataPoint) -> bool:
        """存储单个数据点"""
        try:
            result = await self.backend.store_point(point)
            if result:
                self._total_points_stored += 1
                if self.on_store:
                    self.on_store(1)
            return result
        except Exception as e:
            self._total_errors += 1
            logger.error(f"Error storing point: {e}")
            raise

    async def get_points(
        self,
        equipment_id: str,
        parameter_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[DataPoint]:
        """获取数据点"""
        return await self.backend.get_points(
            equipment_id,
            parameter_name,
            start_time,
            end_time,
            limit,
        )

    async def delete_points(
        self,
        equipment_id: str,
        before_time: datetime,
    ) -> int:
        """删除数据点"""
        return await self.backend.delete_points(equipment_id, before_time)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_points_stored": self._total_points_stored,
            "total_batches_stored": self._total_batches_stored,
            "total_errors": self._total_errors,
        }
