"""数据采集器测试"""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from myeap.data.models import DataPoint, DataBatch
from myeap.data.collector import DataCollector
from myeap.data.sampler import DataSampler
from myeap.data.storage import InMemoryDataStorage


class TestDataPoint:
    """数据点测试"""

    def test_creation(self):
        """测试创建数据点"""
        point = DataPoint(
            equipment_id="eq-001",
            parameter_name="Temperature",
            value=25.5,
        )
        assert point.equipment_id == "eq-001"
        assert point.parameter_name == "Temperature"
        assert point.value == 25.5
        assert point.quality == "normal"
        assert point.chamber_id is None
        assert point.timestamp is not None

    def test_with_chamber(self):
        """测试带腔体ID的数据点"""
        point = DataPoint(
            equipment_id="eq-001",
            chamber_id="ch-01",
            parameter_name="Pressure",
            value=100.0,
            unit="torr",
        )
        assert point.chamber_id == "ch-01"
        assert point.unit == "torr"

    def test_to_dict(self):
        """测试转换为字典"""
        point = DataPoint(
            equipment_id="eq-001",
            parameter_name="Temperature",
            value=25.5,
            quality="suspect",
        )
        data = point.to_dict()
        assert data["equipment_id"] == "eq-001"
        assert data["parameter_name"] == "Temperature"
        assert data["value"] == 25.5
        assert data["quality"] == "suspect"

    def test_repr(self):
        """测试字符串表示"""
        point = DataPoint(
            equipment_id="eq-001",
            parameter_name="Temperature",
            value=25.5,
        )
        assert "eq-001" in repr(point)
        assert "Temperature" in repr(point)


class TestDataBatch:
    """数据批次测试"""

    def test_creation(self):
        """测试创建数据批次"""
        points = [
            DataPoint("eq-001", "Temp1", 25.0),
            DataPoint("eq-001", "Temp2", 26.0),
        ]
        batch = DataBatch("eq-001", points)
        assert batch.equipment_id == "eq-001"
        assert len(batch.points) == 2
        assert batch.collected_at is not None

    def test_to_dict(self):
        """测试转换为字典"""
        points = [DataPoint("eq-001", "Temp", 25.0)]
        batch = DataBatch("eq-001", points, chamber_id="ch-01")
        data = batch.to_dict()
        assert data["equipment_id"] == "eq-001"
        assert data["chamber_id"] == "ch-01"
        assert len(data["points"]) == 1


class TestDataCollector:
    """数据采集器测试"""

    @pytest.fixture
    def storage(self):
        """创建测试存储"""
        return InMemoryDataStorage()

    @pytest.fixture
    def sampler(self):
        """创建测试采样器"""
        return DataSampler()

    @pytest.fixture
    def collector(self, storage, sampler):
        """创建测试采集器"""
        return DataCollector(storage=storage, sampler=sampler)

    def test_creation(self, collector, storage, sampler):
        """测试创建采集器"""
        assert collector.storage is storage
        assert collector.sampler is sampler
        assert not collector.is_running
        assert collector.task_count == 0

    def test_set_parameter_reader(self, collector):
        """测试设置参数读取函数"""
        mock_reader = MagicMock(return_value=42.0)
        collector.set_parameter_reader(mock_reader)
        assert collector._parameter_reader is not None

    @pytest.mark.asyncio
    async def test_start_collecting(self, collector):
        """测试开始采集"""
        await collector.start_collecting(
            "eq-001",
            ["Temperature", "Pressure"],
            sampling_interval=0.1,
        )
        assert collector.is_running
        assert "eq-001" in collector.active_equipment
        await collector.stop_all()

    @pytest.mark.asyncio
    async def test_stop_collecting(self, collector):
        """测试停止采集"""
        await collector.start_collecting(
            "eq-001",
            ["Temperature"],
            sampling_interval=0.1,
        )
        await asyncio.sleep(0.2)
        await collector.stop_collecting("eq-001")
        assert "eq-001" not in collector.active_equipment

    @pytest.mark.asyncio
    async def test_duplicate_start(self, collector):
        """测试重复开始采集"""
        await collector.start_collecting("eq-001", ["Temp"], sampling_interval=0.1)
        task_count = collector.task_count
        # 再次启动同一个设备应该被忽略
        await collector.start_collecting("eq-001", ["Temp"], sampling_interval=0.1)
        assert collector.task_count == task_count
        await collector.stop_all()

    @pytest.mark.asyncio
    async def test_stop_nonexistent(self, collector):
        """测试停止不存在的采集"""
        await collector.stop_collecting("nonexistent")
        assert collector.task_count == 0

    @pytest.mark.asyncio
    async def test_stop_all(self, collector):
        """测试停止所有采集"""
        await collector.start_collecting("eq-001", ["Temp"], sampling_interval=0.1)
        await collector.start_collecting("eq-002", ["Temp"], sampling_interval=0.1)
        assert collector.task_count == 2
        await collector.stop_all()
        assert collector.task_count == 0

    @pytest.mark.asyncio
    async def test_collect_with_storage(self, storage, sampler):
        """测试采集并存储"""
        collected_batches = []

        def on_data(batch):
            collected_batches.append(batch)

        collector = DataCollector(
            storage=storage,
            sampler=sampler,
            on_data_callback=on_data,
        )

        # 使用异步模拟的读数函数
        async def mock_reader(e, p):
            return 50.0

        collector.set_parameter_reader(mock_reader)

        await collector.start_collecting(
            "eq-001",
            ["Temperature"],
            sampling_interval=0.05,
        )

        # 等待足够时间让采集完成
        await asyncio.sleep(0.15)

        await collector.stop_all()

        # 应该有批次被收集
        assert len(collected_batches) >= 1
        # 存储中应该有数据
        assert storage.point_count > 0

    @pytest.mark.asyncio
    async def test_read_parameter_with_mock(self, collector):
        """测试参数读取"""
        async def mock_reader(e, p):
            return 42.0

        collector.set_parameter_reader(mock_reader)
        value = await collector._read_parameter("eq-001", "Temperature")
        assert value == 42.0

    @pytest.mark.asyncio
    async def test_read_parameter_default(self, collector):
        """测试默认参数读取（模拟值）"""
        value = await collector._read_parameter("eq-001", "Temperature")
        assert isinstance(value, float)
        assert 0 <= value <= 100
