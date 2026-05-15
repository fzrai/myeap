"""数据存储测试"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

from myeap.data.models import DataPoint, DataBatch
from myeap.data.storage import (
    DataStorage,
    InMemoryDataStorage,
    BufferingDataStorage,
    MetricsCollectingStorage,
)


class TestInMemoryDataStorage:
    """内存存储测试"""

    @pytest.fixture
    def storage(self):
        """创建测试存储"""
        return InMemoryDataStorage(max_points=100)

    @pytest.fixture
    def sample_point(self):
        """创建测试数据点"""
        return DataPoint(
            equipment_id="eq-001",
            parameter_name="Temperature",
            value=25.5,
        )

    @pytest.fixture
    def sample_batch(self):
        """创建测试数据批次"""
        return DataBatch(
            equipment_id="eq-001",
            points=[
                DataPoint("eq-001", "Temp1", 25.0),
                DataPoint("eq-001", "Temp2", 26.0),
            ],
        )

    def test_creation(self, storage):
        """测试创建存储"""
        assert storage.point_count == 0
        assert storage.max_points == 100

    @pytest.mark.asyncio
    async def test_store_point(self, storage, sample_point):
        """测试存储单个数据点"""
        result = await storage.store_point(sample_point)
        assert result is True
        assert storage.point_count == 1

    @pytest.mark.asyncio
    async def test_store_batch(self, storage, sample_batch):
        """测试存储批次"""
        result = await storage.store_batch(sample_batch)
        assert result is True
        assert storage.point_count == 2

    @pytest.mark.asyncio
    async def test_get_points(self, storage):
        """测试获取数据点"""
        now = datetime.utcnow()
        points = [
            DataPoint("eq-001", "Temp", 25.0 + i, timestamp=now + timedelta(minutes=i))
            for i in range(5)
        ]
        for p in points:
            await storage.store_point(p)

        result = await storage.get_points("eq-001")
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_get_points_by_parameter(self, storage):
        """测试按参数名获取数据点"""
        now = datetime.utcnow()
        await storage.store_point(DataPoint("eq-001", "Temp", 25.0, timestamp=now))
        await storage.store_point(DataPoint("eq-001", "Pressure", 100.0, timestamp=now))
        await storage.store_point(DataPoint("eq-001", "Temp", 26.0, timestamp=now))

        result = await storage.get_points("eq-001", parameter_name="Temp")
        assert len(result) == 2
        assert all(p.parameter_name == "Temp" for p in result)

    @pytest.mark.asyncio
    async def test_get_points_by_time(self, storage):
        """测试按时间获取数据点"""
        now = datetime.utcnow()
        for i in range(5):
            await storage.store_point(
                DataPoint("eq-001", "Temp", 25.0 + i, timestamp=now + timedelta(minutes=i))
            )

        result = await storage.get_points(
            "eq-001",
            start_time=now + timedelta(minutes=2),
        )
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_get_points_with_limit(self, storage):
        """测试获取数据点数量限制"""
        now = datetime.utcnow()
        for i in range(10):
            await storage.store_point(
                DataPoint("eq-001", "Temp", 25.0 + i, timestamp=now + timedelta(minutes=i))
            )

        result = await storage.get_points("eq-001", limit=3)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_delete_points(self, storage):
        """测试删除数据点"""
        now = datetime.utcnow()
        for i in range(5):
            await storage.store_point(
                DataPoint("eq-001", "Temp", 25.0 + i, timestamp=now + timedelta(minutes=i))
            )

        deleted = await storage.delete_points("eq-001", before_time=now + timedelta(minutes=2))
        assert deleted == 2
        assert storage.point_count == 3

    @pytest.mark.asyncio
    async def test_delete_points_by_equipment(self, storage):
        """测试按设备删除"""
        now = datetime.utcnow()
        await storage.store_point(
            DataPoint("eq-001", "Temp", 25.0, timestamp=now)
        )
        await storage.store_point(
            DataPoint("eq-002", "Temp", 30.0, timestamp=now)
        )

        await storage.delete_points("eq-001", before_time=now + timedelta(hours=1))
        assert storage.point_count == 1

    def test_clear(self, storage):
        """测试清空数据"""
        storage._points = [1, 2, 3]  # 直接修改
        storage.clear()
        assert storage.point_count == 0

    @pytest.mark.asyncio
    async def test_max_points_limit(self):
        """测试最大点数限制"""
        storage = InMemoryDataStorage(max_points=5)
        for i in range(10):
            await storage.store_point(
                DataPoint("eq-001", "Temp", float(i), timestamp=datetime.utcnow())
            )
        assert storage.point_count == 5


class TestBufferingDataStorage:
    """缓冲存储测试"""

    @pytest.fixture
    def backend(self):
        """创建底层存储"""
        return InMemoryDataStorage()

    @pytest.fixture
    def storage(self, backend):
        """创建缓冲存储"""
        return BufferingDataStorage(
            backend=backend,
            buffer_size=5,
            flush_interval=0.1,
        )

    @pytest.mark.asyncio
    async def test_buffering(self, storage, backend):
        """测试缓冲功能"""
        await storage.start()

        for i in range(3):
            await storage.store_point(
                DataPoint("eq-001", "Temp", float(i))
            )

        # 数据应该在缓冲区中
        assert storage.buffer_size == 3
        assert backend.point_count == 0

        await storage.flush()
        assert backend.point_count == 3

        await storage.stop()

    @pytest.mark.asyncio
    async def test_auto_flush(self, storage, backend):
        """测试自动刷新"""
        await storage.start()

        for i in range(6):  # 超过 buffer_size
            await storage.store_point(
                DataPoint("eq-001", "Temp", float(i))
            )

        # 等待自动刷新
        await asyncio.sleep(0.2)
        assert backend.point_count >= 5

        await storage.stop()

    @pytest.mark.asyncio
    async def test_get_points(self, storage, backend):
        """测试获取数据点（透传到后端）"""
        await storage.start()
        await storage.store_point(DataPoint("eq-001", "Temp", 25.0))
        await storage.flush()

        result = await storage.get_points("eq-001")
        assert len(result) == 1

        await storage.stop()


class TestMetricsCollectingStorage:
    """带指标的存储测试"""

    @pytest.fixture
    def backend(self):
        """创建底层存储"""
        return InMemoryDataStorage()

    @pytest.fixture
    def storage(self, backend):
        """创建带指标的存储"""
        return MetricsCollectingStorage(backend=backend)

    @pytest.mark.asyncio
    async def test_store_batch_updates_stats(self, storage):
        """测试存储批次更新统计"""
        batch = DataBatch(
            equipment_id="eq-001",
            points=[
                DataPoint("eq-001", "Temp", 25.0),
                DataPoint("eq-001", "Temp", 26.0),
            ],
        )
        await storage.store_batch(batch)

        stats = storage.get_stats()
        assert stats["total_points_stored"] == 2
        assert stats["total_batches_stored"] == 1
        assert stats["total_errors"] == 0

    @pytest.mark.asyncio
    async def test_store_point_updates_stats(self, storage):
        """测试存储单点更新统计"""
        await storage.store_point(DataPoint("eq-001", "Temp", 25.0))

        stats = storage.get_stats()
        assert stats["total_points_stored"] == 1
        assert stats["total_batches_stored"] == 0

    @pytest.mark.asyncio
    async def test_callback(self, storage):
        """测试存储回调"""
        callback_counts = []

        def on_store(count):
            callback_counts.append(count)

        storage.on_store = on_store
        await storage.store_point(DataPoint("eq-001", "Temp", 25.0))
        assert 1 in callback_counts

    @pytest.mark.asyncio
    async def test_error_tracking(self, storage, backend):
        """测试错误追踪"""
        # 让后端抛出错误
        original_store = backend.store_point
        backend.store_point = AsyncMock(side_effect=Exception("Test error"))

        with pytest.raises(Exception):
            await storage.store_point(DataPoint("eq-001", "Temp", 25.0))

        stats = storage.get_stats()
        assert stats["total_errors"] == 1
