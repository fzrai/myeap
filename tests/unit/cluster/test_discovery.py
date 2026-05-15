"""服务发现测试"""
import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

from myeap.cluster.discovery import ServiceDiscovery
from myeap.cluster.models import NodeInfo, NodeStatus, ServiceInfo, ServiceStatus


@pytest.fixture
def discovery():
    """创建服务发现实例"""
    return ServiceDiscovery(registry_backend="etcd")


class TestServiceDiscoveryNodeRegistration:
    """测试节点注册"""

    @pytest.mark.asyncio
    async def test_register_node(self, discovery):
        node = await discovery.register_node(
            "node-1", "192.168.1.10:8000",
            metadata={"zone": "A"},
            host="server01",
            port=8000,
            labels={"env": "prod"},
        )
        assert node.node_id == "node-1"
        assert node.address == "192.168.1.10:8000"
        assert node.host == "server01"
        assert node.port == 8000
        assert node.metadata == {"zone": "A"}
        assert node.labels == {"env": "prod"}
        assert node.status == NodeStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_register_node_defaults(self, discovery):
        node = await discovery.register_node("node-2", "10.0.0.2:8000")
        assert node.node_id == "node-2"
        assert node.metadata == {}
        assert node.labels == {}
        assert node.host == ""

    @pytest.mark.asyncio
    async def test_deregister_node(self, discovery):
        await discovery.register_node("node-1", "192.168.1.10:8000")
        result = await discovery.deregister_node("node-1")
        assert result is True

    @pytest.mark.asyncio
    async def test_deregister_nonexistent_node(self, discovery):
        result = await discovery.deregister_node("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_node(self, discovery):
        await discovery.register_node("node-1", "addr1")
        node = await discovery.get_node("node-1")
        assert node is not None
        assert node.node_id == "node-1"

    @pytest.mark.asyncio
    async def test_get_node_nonexistent(self, discovery):
        node = await discovery.get_node("nonexistent")
        assert node is None

    @pytest.mark.asyncio
    async def test_register_node_triggers_callback(self, discovery):
        callback = Mock()
        discovery.on_node_join(callback)
        await discovery.register_node("node-1", "addr1")
        callback.assert_called_once()
        called_node = callback.call_args[0][0]
        assert called_node.node_id == "node-1"

    @pytest.mark.asyncio
    async def test_deregister_node_triggers_callback(self, discovery):
        await discovery.register_node("node-1", "addr1")
        callback = Mock()
        discovery.on_node_leave(callback)
        await discovery.deregister_node("node-1")
        callback.assert_called_once()


class TestServiceDiscoveryNodeQueries:
    """测试节点查询"""

    @pytest.mark.asyncio
    async def test_get_active_nodes(self, discovery):
        await discovery.register_node("node-1", "addr1")
        await discovery.register_node("node-2", "addr2")
        active = await discovery.get_active_nodes()
        assert len(active) == 2
        node_ids = [n["node_id"] for n in active]
        assert "node-1" in node_ids
        assert "node-2" in node_ids

    @pytest.mark.asyncio
    async def test_get_active_nodes_excludes_inactive(self, discovery):
        await discovery.register_node("node-1", "addr1")
        await discovery.register_node("node-2", "addr2")
        await discovery.set_node_status("node-2", NodeStatus.INACTIVE)
        active = await discovery.get_active_nodes()
        assert len(active) == 1
        assert active[0]["node_id"] == "node-1"

    @pytest.mark.asyncio
    async def test_get_all_nodes(self, discovery):
        await discovery.register_node("node-1", "addr1")
        await discovery.register_node("node-2", "addr2")
        await discovery.set_node_status("node-2", NodeStatus.INACTIVE)
        all_nodes = await discovery.get_all_nodes()
        assert len(all_nodes) == 2

    @pytest.mark.asyncio
    async def test_get_node_count(self, discovery):
        await discovery.register_node("node-1", "addr1")
        await discovery.register_node("node-2", "addr2")
        count = await discovery.get_node_count()
        assert count == 2

    @pytest.mark.asyncio
    async def test_get_node_count_excludes_inactive(self, discovery):
        await discovery.register_node("node-1", "addr1")
        await discovery.register_node("node-2", "addr2")
        await discovery.set_node_status("node-1", NodeStatus.INACTIVE)
        count = await discovery.get_node_count()
        assert count == 1


class TestServiceDiscoveryHeartbeat:
    """测试心跳管理"""

    @pytest.mark.asyncio
    async def test_heartbeat_updates_timestamp(self, discovery):
        await discovery.register_node("node-1", "addr1")
        old_beat = discovery._nodes["node-1"].last_heartbeat
        await asyncio.sleep(0.01)
        result = await discovery.heartbeat("node-1")
        assert result is True
        assert discovery._nodes["node-1"].last_heartbeat > old_beat

    @pytest.mark.asyncio
    async def test_heartbeat_unknown_node(self, discovery):
        result = await discovery.heartbeat("unknown-node")
        assert result is False

    @pytest.mark.asyncio
    async def test_heartbeat_reactivates_node(self, discovery):
        await discovery.register_node("node-1", "addr1")
        await discovery.set_node_status("node-1", NodeStatus.INACTIVE)
        await discovery.heartbeat("node-1")
        assert discovery._nodes["node-1"].status == NodeStatus.ACTIVE


class TestServiceDiscoveryNodeMetadata:
    """测试节点元数据管理"""

    @pytest.mark.asyncio
    async def test_update_node_metadata(self, discovery):
        await discovery.register_node("node-1", "addr1", metadata={"zone": "A"})
        result = await discovery.update_node_metadata("node-1", {"region": "us-east"})
        assert result is True
        assert discovery._nodes["node-1"].metadata == {"zone": "A", "region": "us-east"}

    @pytest.mark.asyncio
    async def test_update_node_metadata_nonexistent(self, discovery):
        result = await discovery.update_node_metadata("nonexistent", {"key": "val"})
        assert result is False

    @pytest.mark.asyncio
    async def test_set_node_status(self, discovery):
        await discovery.register_node("node-1", "addr1")
        result = await discovery.set_node_status("node-1", NodeStatus.STOPPING)
        assert result is True
        assert discovery._nodes["node-1"].status == NodeStatus.STOPPING

    @pytest.mark.asyncio
    async def test_set_node_status_nonexistent(self, discovery):
        result = await discovery.set_node_status("nonexistent", NodeStatus.INACTIVE)
        assert result is False


class TestServiceDiscoveryServiceRegistration:
    """测试服务注册"""

    @pytest.mark.asyncio
    async def test_register_service(self, discovery):
        svc = await discovery.register_service(
            "api", ["http://ep1:8080", "http://ep2:8080"],
            namespace="production",
        )
        assert svc.name == "api"
        assert svc.namespace == "production"
        assert len(svc.endpoints) == 2

    @pytest.mark.asyncio
    async def test_deregister_service(self, discovery):
        await discovery.register_service("api", ["http://ep1:8080"])
        result = await discovery.deregister_service("api")
        assert result is True

    @pytest.mark.asyncio
    async def test_deregister_service_nonexistent(self, discovery):
        result = await discovery.deregister_service("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_service(self, discovery):
        await discovery.register_service("api", ["http://ep1:8080"], namespace="ns1")
        svc = await discovery.get_service("api", "ns1")
        assert svc is not None
        assert svc.name == "api"

    @pytest.mark.asyncio
    async def test_get_service_nonexistent(self, discovery):
        svc = await discovery.get_service("nonexistent")
        assert svc is None

    @pytest.mark.asyncio
    async def test_get_services(self, discovery):
        await discovery.register_service("svc1", ["http://a:1"], namespace="ns1")
        await discovery.register_service("svc2", ["http://b:1"], namespace="ns1")
        await discovery.register_service("svc3", ["http://c:1"], namespace="ns2")

        all_svcs = await discovery.get_services()
        assert len(all_svcs) == 3

        ns1_svcs = await discovery.get_services(namespace="ns1")
        assert len(ns1_svcs) == 2

    @pytest.mark.asyncio
    async def test_update_service_endpoints(self, discovery):
        await discovery.register_service("api", ["http://old:8080"])
        result = await discovery.update_service_endpoints(
            "api", ["http://new1:8080", "http://new2:8080"]
        )
        assert result is True
        svc = await discovery.get_service("api")
        assert svc.endpoints == ["http://new1:8080", "http://new2:8080"]

    @pytest.mark.asyncio
    async def test_update_service_endpoints_nonexistent(self, discovery):
        result = await discovery.update_service_endpoints(
            "nonexistent", ["http://ep:8080"]
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_register_service_triggers_callback(self, discovery):
        callback = Mock()
        discovery.on_service_change(callback)
        await discovery.register_service("api", ["http://ep:8080"])
        callback.assert_called_once()


class TestServiceDiscoveryLifecycle:
    """测试服务发现生命周期"""

    @pytest.mark.asyncio
    async def test_clear(self, discovery):
        await discovery.register_node("node-1", "addr1")
        await discovery.register_service("svc1", ["http://ep:8080"])
        discovery.clear()
        assert len(discovery._nodes) == 0
        assert len(discovery._services) == 0

    @pytest.mark.asyncio
    async def test_shutdown(self, discovery):
        await discovery.register_node("node-1", "addr1")
        discovery.start_heartbeat_monitor(timeout=10)
        await discovery.shutdown()
        assert len(discovery._nodes) == 0

    @pytest.mark.asyncio
    async def test_heartbeat_monitor_marks_expired(self, discovery):
        await discovery.register_node("node-1", "addr1")
        # Manually age the heartbeat
        discovery._nodes["node-1"].last_heartbeat = datetime.now(timezone.utc) - timedelta(seconds=120)
        await discovery._check_heartbeats()
        assert discovery._nodes["node-1"].status == NodeStatus.INACTIVE

    @pytest.mark.asyncio
    async def test_heartbeat_monitor_triggers_callback(self, discovery):
        callback = Mock()
        discovery.on_node_timeout(callback)
        await discovery.register_node("node-1", "addr1")
        discovery._nodes["node-1"].last_heartbeat = datetime.now(timezone.utc) - timedelta(seconds=120)
        await discovery._check_heartbeats()
        callback.assert_called_once_with("node-1")

    @pytest.mark.asyncio
    async def test_stop_heartbeat_monitor(self, discovery):
        discovery.start_heartbeat_monitor(timeout=10, cleanup_interval=100)
        discovery.stop_heartbeat_monitor()
        assert discovery._heartbeat_monitor_task is None
