"""集群引擎测试"""
import asyncio
import os
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

from myeap.cluster.engine import ClusterEngine
from myeap.cluster.models import ClusterConfig, NodeRole, NodeStatus


@pytest.fixture
def config():
    """创建测试配置"""
    return ClusterConfig(
        cluster_name="test-cluster",
        node_id="test-node-1",
        discovery_backend="etcd",
        ha_enabled=False,
        config_reload_enabled=False,
        heartbeat_interval=5,
    )


@pytest.fixture
def engine(config):
    """创建集群引擎实例"""
    return ClusterEngine(config)


class TestClusterEngineInit:
    """测试集群引擎初始化"""

    def test_init_default_config(self):
        engine = ClusterEngine()
        assert engine.cluster_name == "myeap"
        assert engine.node_id != ""  # auto-generated
        assert engine.is_running is False
        assert engine.uptime_seconds is None

    def test_init_custom_config(self, engine, config):
        assert engine.config == config
        assert engine.node_id == "test-node-1"
        assert engine.cluster_name == "test-cluster"
        assert engine.is_running is False

    def test_node_id_auto_generated(self):
        engine = ClusterEngine(ClusterConfig())
        assert engine.node_id != ""
        assert len(engine.node_id) > 0

    def test_submodules_initialized(self, engine):
        assert engine.discovery is not None
        assert engine.ha is not None
        assert engine.config_watcher is None  # config_reload_enabled=False


class TestClusterEngineServiceManagement:
    """测试集群引擎服务管理"""

    @pytest.mark.asyncio
    async def test_register_service(self, engine):
        svc = await engine.register_service("api", ["http://ep1:8080"])
        assert svc.name == "api"
        assert svc.endpoints == ["http://ep1:8080"]

    @pytest.mark.asyncio
    async def test_get_service(self, engine):
        await engine.register_service("api", ["http://ep1:8080"])
        svc = await engine.get_service("api")
        assert svc is not None
        assert svc.name == "api"

    @pytest.mark.asyncio
    async def test_get_service_nonexistent(self, engine):
        svc = await engine.get_service("nonexistent")
        assert svc is None


class TestClusterEngineHAManagement:
    """测试HA管理"""

    def test_register_health_check(self, engine):
        check_fn = lambda: True
        engine.register_health_check("db_check", check_fn, interval=30)
        assert "db_check" in engine.ha._health_checks

    def test_unregister_health_check(self, engine):
        engine.register_health_check("db_check", lambda: True)
        result = engine.unregister_health_check("db_check")
        assert result is True

    @pytest.mark.asyncio
    async def test_run_health_checks(self, engine):
        engine.register_health_check("check_ok", lambda: True, interval=30)
        results = await engine.run_health_checks()
        assert "check_ok" in results
        assert results["check_ok"].healthy is True

    @pytest.mark.asyncio
    async def test_check_health(self, engine):
        engine.register_health_check("check_ok", lambda: True, interval=30)
        assert await engine.check_health() is True

    @pytest.mark.asyncio
    async def test_check_health_unhealthy(self, engine):
        engine.register_health_check("check_fail", lambda: False, interval=30)
        assert await engine.check_health() is False

    @pytest.mark.asyncio
    async def test_trigger_failover(self, engine):
        # Engine needs to be "started" for node to be registered as active
        engine.ha._failover_count = 0
        engine.ha._last_failover_time = None
        engine.ha.max_failover_count = 3
        result = await engine.trigger_failover("test_reason")
        assert result is True
        assert engine.ha.failover_count == 1

    def test_promote_to_active(self, engine):
        engine.ha.demote_to_standby()
        engine.promote_to_active()
        assert engine.ha.is_active is True

    def test_demote_to_standby(self, engine):
        engine.demote_to_standby()
        assert engine.ha.is_active is False


class TestClusterEngineConfigManagement:
    """测试配置管理"""

    @pytest.mark.asyncio
    async def test_watch_config_key_no_watcher(self, engine):
        # config_watcher is None when config_reload_enabled=False
        await engine.watch_config_key("key", lambda k, v: None)
        # Should not raise

    def test_get_config_value_no_watcher(self, engine):
        result = engine.get_config_value("key", "default")
        assert result == "default"

    @pytest.mark.asyncio
    async def test_reload_config_no_watcher(self, engine):
        result = await engine.reload_config()
        assert result is None


class TestClusterEngineNodeManagement:
    """测试节点管理"""

    @pytest.mark.asyncio
    async def test_get_local_node(self, engine):
        # Register local node in discovery first
        await engine.discovery.register_node(engine.node_id, "addr1")
        node = await engine.get_local_node()
        assert node is not None
        assert node.node_id == engine.node_id

    @pytest.mark.asyncio
    async def test_get_cluster_nodes(self, engine):
        await engine.discovery.register_node("n1", "addr1")
        await engine.discovery.register_node("n2", "addr2")
        nodes = await engine.get_cluster_nodes()
        assert len(nodes) == 2

    @pytest.mark.asyncio
    async def test_get_cluster_node_count(self, engine):
        await engine.discovery.register_node("n1", "addr1")
        await engine.discovery.register_node("n2", "addr2")
        count = await engine.get_cluster_node_count()
        assert count == 2

    @pytest.mark.asyncio
    async def test_update_local_heartbeat(self, engine):
        await engine.discovery.register_node(engine.node_id, "addr1")
        old_heartbeat = engine.discovery._nodes[engine.node_id].last_heartbeat
        await asyncio.sleep(0.01)
        await engine.update_local_heartbeat()
        new_heartbeat = engine.discovery._nodes[engine.node_id].last_heartbeat
        assert new_heartbeat >= old_heartbeat


class TestClusterEngineCallbacks:
    """测试事件回调"""

    def test_on_event_callback(self, engine):
        callback = Mock()
        engine.on_event(callback)
        assert engine._on_event == callback

    def test_on_node_join_callback(self, engine):
        callback = Mock()
        engine.on_node_join(callback)
        assert engine.discovery._on_node_join == callback

    def test_on_node_leave_callback(self, engine):
        callback = Mock()
        engine.on_node_leave(callback)
        assert engine.discovery._on_node_leave == callback

    @pytest.mark.asyncio
    async def test_on_config_change_no_watcher(self, engine):
        callback = Mock()
        engine.on_config_change(callback)
        # Should not raise even when config_watcher is None


class TestClusterEngineLifecycle:
    """测试生命周期"""

    @pytest.mark.asyncio
    async def test_start(self, engine):
        await engine.start()
        assert engine.is_running is True
        assert engine.uptime_seconds is not None
        assert engine.uptime_seconds >= 0
        await engine.stop()

    @pytest.mark.asyncio
    async def test_stop(self, engine):
        await engine.start()
        await engine.stop()
        assert engine.is_running is False
        assert engine.uptime_seconds is None

    @pytest.mark.asyncio
    async def test_start_registers_node(self, engine):
        await engine.start()
        node = await engine.discovery.get_node(engine.node_id)
        assert node is not None
        assert node.address != ""
        await engine.stop()

    @pytest.mark.asyncio
    async def test_stop_deregisters_node(self, engine):
        await engine.start()
        await engine.stop()
        node = await engine.discovery.get_node(engine.node_id)
        assert node is None

    @pytest.mark.asyncio
    async def test_start_already_running(self, engine):
        await engine.start()
        # Should warn and not crash
        await engine.start()
        assert engine.is_running is True
        await engine.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, engine):
        # Should not raise
        await engine.stop()
        assert engine.is_running is False

    @pytest.mark.asyncio
    async def test_uptime_calculation(self, engine):
        await engine.start()
        await asyncio.sleep(0.05)
        uptime = engine.uptime_seconds
        assert uptime is not None
        assert uptime >= 0.05
        await engine.stop()


class TestClusterEngineInternalMethods:
    """测试内部方法"""

    def test_generate_node_id(self, engine):
        node_id = engine._generate_node_id()
        assert isinstance(node_id, str)
        assert len(node_id) > 0

    def test_get_local_address(self, engine):
        addr = engine._get_local_address()
        assert ":" in addr

    def test_get_version(self, engine):
        version = engine._get_version()
        assert isinstance(version, str)
        assert len(version) > 0

    @pytest.mark.asyncio
    async def test_emit_event(self, engine):
        received = []

        def on_event(event_type, data):
            received.append((event_type, data))

        engine.on_event(on_event)
        await engine._emit_event("test_event", {"key": "value"})
        assert len(received) == 1
        assert received[0] == ("test_event", {"key": "value"})

    @pytest.mark.asyncio
    async def test_emit_event_no_callback(self, engine):
        # Should not raise
        await engine._emit_event("test_event", {"key": "value"})


class TestClusterEngineWithConfigWatcher:
    """测试带配置监听器的引擎"""

    @pytest.mark.asyncio
    async def test_engine_with_config_watcher(self, tmp_path):
        import json
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps({"app": {"name": "myeap"}}),
            encoding="utf-8",
        )

        config = ClusterConfig(
            cluster_name="test",
            node_id="node-1",
            config_reload_enabled=True,
        )

        with patch.dict(os.environ, {"MYEAP_CONFIG_PATH": str(config_path)}):
            engine = ClusterEngine(config)
            await engine.start()

            assert engine.config_watcher is not None
            value = engine.get_config_value("app.name")
            assert value == "myeap"

            await engine.stop()
