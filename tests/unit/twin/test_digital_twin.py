"""数字孪生核心测试"""

import asyncio
import pytest
from datetime import datetime

from myeap.twin.models import (
    HealthStatus,
    TwinEvent,
    TwinState,
)
from myeap.twin.digital_twin import DigitalTwin


@pytest.fixture
def dt():
    """创建数字孪生实例"""
    return DigitalTwin()


@pytest.fixture
async def dt_with_twin(dt):
    """创建带一个双子的数字孪生"""
    await dt.create_twin("eq-001", {
        "chambers": {"ch-1": {"Temp": 100.0}},
        "status": "IDLE",
        "sensor_data": {"Temperature": 25.0, "Pressure": 1.0, "Flow": 50.0},
    })
    return dt


class TestCreateTwin:
    """创建数字孪生测试"""

    @pytest.mark.asyncio
    async def test_create_twin(self, dt):
        """测试创建数字孪生"""
        twin = await dt.create_twin("eq-001", {
            "chambers": {"ch-1": {"Temp": 100.0}},
            "status": "IDLE",
            "sensor_data": {"Temperature": 25.0, "Pressure": 1.0},
        })
        assert twin.equipment_id == "eq-001"
        assert twin.status == "IDLE"
        assert twin.sensor_data["Temperature"] == 25.0
        assert "ch-1" in twin.chambers
        assert dt.twin_count == 1

    @pytest.mark.asyncio
    async def test_create_twin_default_status(self, dt):
        """测试创建数字孪生，默认状态"""
        twin = await dt.create_twin("eq-002", {})
        assert twin.status == "UNKNOWN"
        assert twin.sensor_data == {}
        assert twin.chambers == {}

    @pytest.mark.asyncio
    async def test_create_duplicate_twin_raises(self, dt):
        """测试创建重复数字孪生抛出异常"""
        await dt.create_twin("eq-001", {"status": "IDLE"})
        with pytest.raises(ValueError, match="already exists"):
            await dt.create_twin("eq-001", {"status": "RUNNING"})

    @pytest.mark.asyncio
    async def test_create_twin_emits_event(self, dt):
        """测试创建数字孪生触发事件"""
        events = []

        def on_event(event):
            events.append(event)

        dt.set_on_event(on_event)
        await dt.create_twin("eq-001", {"status": "IDLE"})
        assert len(events) == 1
        assert events[0].event_type == "twin_created"

    @pytest.mark.asyncio
    async def test_create_twin_with_sub_status(self, dt):
        """测试创建带子状态的数字孪生"""
        twin = await dt.create_twin("eq-001", {
            "status": "RUNNING",
            "sub_status": "HEATING",
        })
        assert twin.sub_status == "HEATING"


class TestGetTwin:
    """获取数字孪生测试"""

    @pytest.mark.asyncio
    async def test_get_existing_twin(self, dt_with_twin):
        """测试获取已存在的数字孪生"""
        twin = dt_with_twin.get_twin("eq-001")
        assert twin is not None
        assert twin.equipment_id == "eq-001"

    def test_get_nonexistent_twin(self, dt):
        """测试获取不存在的数字孪生"""
        twin = dt.get_twin("nonexistent")
        assert twin is None

    def test_get_twin_ids(self, dt):
        """测试获取所有设备ID"""
        assert dt.get_twin_ids() == []

    @pytest.mark.asyncio
    async def test_get_twin_ids_after_create(self, dt):
        """测试创建后获取设备ID"""
        await dt.create_twin("eq-001", {"status": "IDLE"})
        await dt.create_twin("eq-002", {"status": "IDLE"})
        ids = dt.get_twin_ids()
        assert len(ids) == 2
        assert "eq-001" in ids
        assert "eq-002" in ids


class TestRemoveTwin:
    """移除数字孪生测试"""

    @pytest.mark.asyncio
    async def test_remove_existing_twin(self, dt_with_twin):
        """测试移除已存在的数字孪生"""
        result = await dt_with_twin.remove_twin("eq-001")
        assert result is True
        assert dt_with_twin.get_twin("eq-001") is None
        assert dt_with_twin.twin_count == 0

    @pytest.mark.asyncio
    async def test_remove_nonexistent_twin(self, dt):
        """测试移除不存在的数字孪生"""
        result = await dt.remove_twin("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_remove_twin_clears_history(self, dt_with_twin):
        """测试移除数字孪生清除历史"""
        await dt_with_twin.remove_twin("eq-001")
        history = dt_with_twin.get_history("eq-001")
        assert history == []


class TestSyncState:
    """状态同步测试"""

    @pytest.mark.asyncio
    async def test_sync_state_basic(self, dt_with_twin):
        """测试基本状态同步"""
        twin = await dt_with_twin.sync_state(
            "eq-001",
            sensor_data={"Temperature": 30.0},
        )
        assert twin.sensor_data["Temperature"] == pytest.approx(26.5)  # EWMA: 0.3*30 + 0.7*25

    @pytest.mark.asyncio
    async def test_sync_nonexistent_twin_raises(self, dt):
        """测试同步不存在的数字孪生抛出异常"""
        with pytest.raises(ValueError, match="No twin"):
            await dt.sync_state("eq-001", {"Temperature": 25.0})

    @pytest.mark.asyncio
    async def test_sync_updates_timestamp(self, dt_with_twin):
        """测试同步更新时间戳"""
        old_ts = dt_with_twin.get_twin("eq-001").timestamp
        import time
        time.sleep(0.01)
        twin = await dt_with_twin.sync_state("eq-001", {"Temperature": 30.0})
        assert twin.timestamp > old_ts

    @pytest.mark.asyncio
    async def test_sync_updates_status(self, dt_with_twin):
        """测试同步更新状态"""
        twin = await dt_with_twin.sync_state(
            "eq-001",
            sensor_data={},
            status="RUNNING",
            sub_status="HEATING",
        )
        assert twin.status == "RUNNING"
        assert twin.sub_status == "HEATING"

    @pytest.mark.asyncio
    async def test_sync_updates_chambers(self, dt_with_twin):
        """测试同步更新腔体状态"""
        twin = await dt_with_twin.sync_state(
            "eq-001",
            sensor_data={},
            chambers={"ch-1": {"Temp": 200.0}, "ch-2": {"Press": 5.0}},
        )
        assert twin.chambers["ch-1"]["Temp"] == 200.0
        assert "ch-2" in twin.chambers

    @pytest.mark.asyncio
    async def test_sync_increments_count(self, dt_with_twin):
        """测试同步计数增加"""
        assert dt_with_twin.sync_count == 0
        await dt_with_twin.sync_state("eq-001", {"Temperature": 25.0})
        assert dt_with_twin.sync_count == 1

    @pytest.mark.asyncio
    async def test_sync_sync_version(self, dt_with_twin):
        """测试同步版本"""
        twin = dt_with_twin.sync_state_sync("eq-001", {"Temperature": 30.0})
        assert twin.sensor_data["Temperature"] == pytest.approx(26.5)

    @pytest.mark.asyncio
    async def test_ewma_multiple_syncs(self, dt_with_twin):
        """测试多次同步的EWMA平滑效果"""
        # Initial: Temperature=25.0
        # First sync: 0.3*30 + 0.7*25 = 26.5
        # Second sync: 0.3*30 + 0.7*26.5 = 27.55
        # Third sync: 0.3*30 + 0.7*27.55 = 28.285
        for _ in range(3):
            await dt_with_twin.sync_state("eq-001", {"Temperature": 30.0})
        twin = dt_with_twin.get_twin("eq-001")
        # After 3 syncs with value 30.0, should approach 30.0
        assert 28.0 < twin.sensor_data["Temperature"] < 29.0

    @pytest.mark.asyncio
    async def test_sync_new_parameter(self, dt_with_twin):
        """测试同步新参数"""
        twin = await dt_with_twin.sync_state("eq-001", {"RF_Power": 100.0})
        assert "RF_Power" in twin.sensor_data
        assert twin.sensor_data["RF_Power"] == 100.0  # First value: no old to smooth


class TestPredictNextState:
    """状态预测测试"""

    @pytest.mark.asyncio
    async def test_predict_insufficient_data(self, dt_with_twin):
        """测试数据不足时预测返回空"""
        predictions = await dt_with_twin.predict_next_state("eq-001", horizon=5)
        assert predictions == []

    @pytest.mark.asyncio
    async def test_predict_with_sufficient_data(self, dt):
        """测试有足够数据时预测"""
        await dt.create_twin("eq-001", {
            "status": "IDLE",
            "sensor_data": {"Temperature": 25.0, "Pressure": 1.0},
        })
        # Add 20 data points with linear trend
        for i in range(20):
            temp = 25.0 + i * 0.5  # Linear increase
            await dt.sync_state("eq-001", {"Temperature": temp, "Pressure": 1.0})

        predictions = await dt.predict_next_state("eq-001", horizon=3)
        assert len(predictions) == 3
        assert "values" in predictions[0]
        assert "Temperature" in predictions[0]["values"]
        # With increasing trend, predictions should be above last value
        last_temp = dt.get_twin("eq-001").sensor_data["Temperature"]
        assert predictions[0]["values"]["Temperature"] > last_temp

    @pytest.mark.asyncio
    async def test_predict_specific_parameters(self, dt):
        """测试预测特定参数"""
        await dt.create_twin("eq-001", {
            "status": "IDLE",
            "sensor_data": {"Temperature": 25.0, "Pressure": 1.0, "Flow": 50.0},
        })
        for i in range(20):
            await dt.sync_state("eq-001", {
                "Temperature": 25.0 + i * 0.1,
                "Pressure": 1.0,
                "Flow": 50.0,
            })

        predictions = await dt.predict_next_state(
            "eq-001", horizon=2, parameters=["Temperature"]
        )
        assert len(predictions) == 2
        assert "Temperature" in predictions[0]["values"]
        assert "Pressure" not in predictions[0]["values"]

    @pytest.mark.asyncio
    async def test_predict_increments_count(self, dt):
        """测试预测计数增加"""
        await dt.create_twin("eq-001", {
            "status": "IDLE",
            "sensor_data": {"Temperature": 25.0},
        })
        for i in range(20):
            await dt.sync_state("eq-001", {"Temperature": 25.0 + i * 0.1})

        assert dt.prediction_count == 0
        await dt.predict_next_state("eq-001", horizon=1)
        assert dt.prediction_count == 1

    @pytest.mark.asyncio
    async def test_predict_sync_version(self, dt):
        """测试预测同步版本"""
        await dt.create_twin("eq-001", {
            "status": "IDLE",
            "sensor_data": {"Temperature": 25.0},
        })
        for i in range(20):
            await dt.sync_state("eq-001", {"Temperature": 25.0 + i * 0.1})

        predictions = dt.predict_next_state_sync("eq-001", horizon=1)
        assert len(predictions) == 1

    @pytest.mark.asyncio
    async def test_predict_emits_event(self, dt):
        """测试预测触发事件"""
        await dt.create_twin("eq-001", {
            "status": "IDLE",
            "sensor_data": {"Temperature": 25.0},
        })
        for i in range(20):
            await dt.sync_state("eq-001", {"Temperature": 25.0 + i * 0.1})

        events = []

        def on_event(event):
            events.append(event)

        dt.set_on_event(on_event)
        await dt.predict_next_state("eq-001", horizon=1)
        assert len(events) >= 1
        assert events[-1].event_type == "prediction_completed"


class TestAssessHealth:
    """健康评估测试"""

    @pytest.mark.asyncio
    async def test_assess_health_no_twin(self, dt):
        """测试无数字孪生时的健康评估"""
        health = await dt.assess_health("nonexistent")
        assert health.equipment_id == "nonexistent"
        assert health.overall_score == 100.0

    @pytest.mark.asyncio
    async def test_assess_health_insufficient_data(self, dt_with_twin):
        """测试数据不足时的健康评估"""
        health = await dt_with_twin.assess_health("eq-001")
        assert health.overall_score >= 90.0  # Defaults to healthy

    @pytest.mark.asyncio
    async def test_assess_health_normal(self, dt):
        """测试正常数据的健康评估"""
        await dt.create_twin("eq-001", {
            "status": "IDLE",
            "sensor_data": {"Temperature": 25.0},
        })
        # Add stable data - very low variance
        for i in range(30):
            await dt.sync_state("eq-001", {"Temperature": 25.0 + (i % 3) * 0.01})

        health = await dt.assess_health("eq-001")
        assert health.overall_score >= 75.0
        assert health.status in (HealthStatus.HEALTHY, HealthStatus.NORMAL)

    @pytest.mark.asyncio
    async def test_assess_health_anomalous(self, dt):
        """测试异常数据的健康评估"""
        await dt.create_twin("eq-001", {
            "status": "IDLE",
            "sensor_data": {"Temperature": 25.0},
        })
        # Build history with stable values
        for i in range(30):
            await dt.sync_state("eq-001", {"Temperature": 25.0 + (i % 3) * 0.05})

        # Inject anomalous value
        await dt.sync_state("eq-001", {"Temperature": 80.0})

        health = await dt.assess_health("eq-001")
        assert health.overall_score < 90.0
        assert len(health.anomalies) > 0
        assert len(health.recommendations) > 0

    @pytest.mark.asyncio
    async def test_assess_health_multiple_parameters(self, dt):
        """测试多参数健康评估"""
        await dt.create_twin("eq-001", {
            "status": "IDLE",
            "sensor_data": {"Temperature": 25.0, "Pressure": 1.0, "Flow": 50.0},
        })
        for i in range(30):
            await dt.sync_state("eq-001", {
                "Temperature": 25.0 + (i % 5) * 0.1,
                "Pressure": 1.0 + (i % 5) * 0.01,
                "Flow": 50.0 + (i % 5) * 0.1,
            })

        health = await dt.assess_health("eq-001")
        assert len(health.component_scores) == 3
        assert "Temperature" in health.component_scores
        assert "Pressure" in health.component_scores
        assert "Flow" in health.component_scores

    @pytest.mark.asyncio
    async def test_assess_health_confidence(self, dt):
        """测试评估置信度"""
        await dt.create_twin("eq-001", {
            "status": "IDLE",
            "sensor_data": {"Temperature": 25.0},
        })
        for i in range(10):
            await dt.sync_state("eq-001", {"Temperature": 25.0 + i * 0.01})

        health = await dt.assess_health("eq-001")
        assert 0.0 <= health.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_assess_health_emits_event_on_anomaly(self, dt):
        """测试异常时触发健康事件"""
        await dt.create_twin("eq-001", {
            "status": "IDLE",
            "sensor_data": {"Temperature": 25.0},
        })
        for i in range(30):
            await dt.sync_state("eq-001", {"Temperature": 25.0 + (i % 3) * 0.01})
        await dt.sync_state("eq-001", {"Temperature": 100.0})  # Anomaly

        events = []

        def on_event(event):
            events.append(event)

        dt.set_on_event(on_event)
        await dt.assess_health("eq-001")
        anomaly_events = [e for e in events if e.event_type == "health_anomaly_detected"]
        assert len(anomaly_events) >= 1

    @pytest.mark.asyncio
    async def test_assess_health_increments_count(self, dt_with_twin):
        """测试健康评估计数增加"""
        assert dt_with_twin.health_check_count == 0
        await dt_with_twin.assess_health("eq-001")
        assert dt_with_twin.health_check_count == 1

    @pytest.mark.asyncio
    async def test_assess_health_sync_version(self, dt):
        """测试健康评估同步版本"""
        await dt.create_twin("eq-001", {
            "status": "IDLE",
            "sensor_data": {"Temperature": 25.0},
        })
        for i in range(20):
            await dt.sync_state("eq-001", {"Temperature": 25.0 + i * 0.1})

        health = dt.assess_health_sync("eq-001")
        assert health is not None
        assert isinstance(health.overall_score, float)

    @pytest.mark.asyncio
    async def test_assess_health_zero_variance(self, dt):
        """测试零方差的健康评估"""
        await dt.create_twin("eq-001", {
            "status": "IDLE",
            "sensor_data": {"Temperature": 25.0},
        })
        # All same values => zero variance
        for i in range(5):
            await dt.sync_state("eq-001", {"Temperature": 25.0})

        health = await dt.assess_health("eq-001")
        assert health.overall_score == 100.0
        assert len(health.anomalies) == 0


class TestHistory:
    """历史记录测试"""

    @pytest.mark.asyncio
    async def test_get_history(self, dt_with_twin):
        """测试获取历史记录"""
        for i in range(5):
            await dt_with_twin.sync_state("eq-001", {"Temperature": 25.0 + i})

        history = dt_with_twin.get_history("eq-001")
        # 1 initial + 5 syncs = 6 records
        assert len(history) == 6

    @pytest.mark.asyncio
    async def test_get_history_with_limit(self, dt_with_twin):
        """测试限制历史记录数量"""
        for i in range(10):
            await dt_with_twin.sync_state("eq-001", {"Temperature": 25.0 + i})

        history = dt_with_twin.get_history("eq-001", limit=3)
        assert len(history) == 3

    @pytest.mark.asyncio
    async def test_get_history_nonexistent(self, dt):
        """测试获取不存在设备的历史记录"""
        history = dt.get_history("nonexistent")
        assert history == []

    @pytest.mark.asyncio
    async def test_history_cap(self, dt):
        """测试历史记录上限"""
        dt.max_history = 50
        await dt.create_twin("eq-001", {
            "status": "IDLE",
            "sensor_data": {"Temperature": 25.0},
        })
        for i in range(100):
            await dt.sync_state("eq-001", {"Temperature": 25.0 + i})

        history = dt.get_history("eq-001")
        assert len(history) <= 50


class TestDegradationModel:
    """退化模型测试"""

    @pytest.mark.asyncio
    async def test_set_model(self, dt_with_twin):
        """测试设置退化模型"""
        dt_with_twin.set_degradation_model("eq-001", "Temperature", {
            "type": "linear", "rate": 0.01
        })
        model = dt_with_twin.get_degradation_model("eq-001", "Temperature")
        assert model["type"] == "linear"
        assert model["rate"] == 0.01

    @pytest.mark.asyncio
    async def test_get_model_nonexistent(self, dt):
        """测试获取不存在的退化模型"""
        model = dt.get_degradation_model("eq-001", "Temperature")
        assert model is None

    @pytest.mark.asyncio
    async def test_remove_model(self, dt_with_twin):
        """测试移除退化模型"""
        dt_with_twin.set_degradation_model("eq-001", "Temperature", {"type": "linear"})
        assert dt_with_twin.remove_degradation_model("eq-001", "Temperature")
        assert dt_with_twin.get_degradation_model("eq-001", "Temperature") is None

    @pytest.mark.asyncio
    async def test_remove_nonexistent_model(self, dt):
        """测试移除不存在的退化模型"""
        assert not dt.remove_degradation_model("eq-001", "Temperature")


class TestStatistics:
    """统计信息测试"""

    @pytest.mark.asyncio
    async def test_get_statistics(self, dt_with_twin):
        """测试获取统计信息"""
        stats = dt_with_twin.get_statistics()
        assert stats["twin_count"] == 1
        assert stats["max_history"] == 10000
        assert "smoothing_factor" in stats

    @pytest.mark.asyncio
    async def test_reset(self, dt_with_twin):
        """测试重置"""
        dt_with_twin.reset()
        assert dt_with_twin.twin_count == 0
        assert dt_with_twin.sync_count == 0
        assert dt_with_twin.prediction_count == 0
        assert dt_with_twin.health_check_count == 0


class TestEventCallback:
    """事件回调测试"""

    @pytest.mark.asyncio
    async def test_sync_callback(self, dt_with_twin):
        """测试同步回调"""
        events = []

        def on_event(event):
            events.append(event)

        dt_with_twin.set_on_event(on_event)
        await dt_with_twin.sync_state("eq-001", {"Temperature": 25.0})
        assert len(events) == 0  # sync_state does not emit directly

    @pytest.mark.asyncio
    async def test_async_callback(self, dt):
        """测试异步回调"""
        events = []

        async def on_event(event):
            events.append(event)

        dt.set_on_event(on_event, async_callback=True)
        await dt.create_twin("eq-001", {"status": "IDLE"})
        assert len(events) == 1
