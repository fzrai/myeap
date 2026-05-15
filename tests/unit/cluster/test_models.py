"""集群模型测试"""
import json
import pytest
from datetime import datetime, timezone, timedelta

from myeap.cluster.models import (
    ClusterConfig,
    NodeInfo,
    NodeRole,
    NodeStatus,
    ServiceInfo,
    ServiceStatus,
)


class TestNodeRole:
    """测试节点角色枚举"""

    def test_role_values(self):
        assert NodeRole.ACTIVE.value == "active"
        assert NodeRole.STANDBY.value == "standby"
        assert NodeRole.WITNESS.value == "witness"

    def test_role_from_string(self):
        assert NodeRole("active") == NodeRole.ACTIVE
        assert NodeRole("standby") == NodeRole.STANDBY
        assert NodeRole("witness") == NodeRole.WITNESS


class TestNodeStatus:
    """测试节点状态枚举"""

    def test_status_values(self):
        assert NodeStatus.ACTIVE.value == "ACTIVE"
        assert NodeStatus.INACTIVE.value == "INACTIVE"
        assert NodeStatus.UNKNOWN.value == "UNKNOWN"
        assert NodeStatus.STARTING.value == "STARTING"
        assert NodeStatus.STOPPING.value == "STOPPING"
        assert NodeStatus.REMOVED.value == "REMOVED"


class TestServiceStatus:
    """测试服务状态枚举"""

    def test_status_values(self):
        assert ServiceStatus.AVAILABLE.value == "available"
        assert ServiceStatus.UNAVAILABLE.value == "unavailable"
        assert ServiceStatus.DEGRADED.value == "degraded"
        assert ServiceStatus.STARTING.value == "starting"


class TestNodeInfo:
    """测试节点信息模型"""

    def test_create_node_info(self):
        node = NodeInfo(
            node_id="node-1",
            address="192.168.1.10:8000",
            host="server01",
            port=8000,
        )
        assert node.node_id == "node-1"
        assert node.address == "192.168.1.10:8000"
        assert node.host == "server01"
        assert node.port == 8000
        assert node.role == NodeRole.ACTIVE
        assert node.status == NodeStatus.ACTIVE

    def test_node_info_defaults(self):
        node = NodeInfo(node_id="node-2", address="10.0.0.1:8000")
        assert node.host == ""
        assert node.port == 0
        assert node.metadata == {}
        assert node.labels == {}
        assert node.version == ""
        assert isinstance(node.registered_at, datetime)
        assert isinstance(node.last_heartbeat, datetime)

    def test_node_info_is_active(self):
        active_node = NodeInfo(
            node_id="n1", address="a1", status=NodeStatus.ACTIVE
        )
        assert active_node.is_active is True

        inactive_node = NodeInfo(
            node_id="n2", address="a2", status=NodeStatus.INACTIVE
        )
        assert inactive_node.is_active is False

    def test_node_info_is_healthy(self):
        healthy = NodeInfo(
            node_id="n1", address="a1", last_heartbeat=datetime.now(timezone.utc)
        )
        assert healthy.is_healthy is True

        old_heartbeat = datetime.now(timezone.utc) - timedelta(seconds=120)
        unhealthy = NodeInfo(
            node_id="n2", address="a2", last_heartbeat=old_heartbeat
        )
        assert unhealthy.is_healthy is False

    def test_to_dict(self):
        node = NodeInfo(
            node_id="node-1",
            address="192.168.1.10:8000",
            host="server01",
            port=8000,
            role=NodeRole.ACTIVE,
            status=NodeStatus.ACTIVE,
            metadata={"zone": "A"},
            labels={"env": "prod"},
            version="1.0.0",
        )
        d = node.to_dict()
        assert d["node_id"] == "node-1"
        assert d["address"] == "192.168.1.10:8000"
        assert d["host"] == "server01"
        assert d["port"] == 8000
        assert d["role"] == "active"
        assert d["status"] == "ACTIVE"
        assert d["metadata"] == {"zone": "A"}
        assert d["labels"] == {"env": "prod"}
        assert d["version"] == "1.0.0"

    def test_from_dict(self):
        data = {
            "node_id": "node-1",
            "address": "192.168.1.10:8000",
            "host": "server01",
            "port": 8000,
            "role": "active",
            "status": "ACTIVE",
            "metadata": {"zone": "A"},
            "registered_at": "2024-01-01T00:00:00",
            "last_heartbeat": "2024-01-01T00:00:30",
            "version": "1.0.0",
            "labels": {"env": "prod"},
        }
        node = NodeInfo.from_dict(data)
        assert node.node_id == "node-1"
        assert node.address == "192.168.1.10:8000"
        assert node.role == NodeRole.ACTIVE
        assert node.status == NodeStatus.ACTIVE
        assert node.version == "1.0.0"

    def test_to_dict_from_dict_roundtrip(self):
        node = NodeInfo(
            node_id="node-x",
            address="10.0.0.1:9000",
            host="host-x",
            port=9000,
            labels={"k": "v"},
        )
        restored = NodeInfo.from_dict(node.to_dict())
        assert restored.node_id == node.node_id
        assert restored.address == node.address
        assert restored.host == node.host
        assert restored.port == node.port


class TestServiceInfo:
    """测试服务信息模型"""

    def test_create_service_info(self):
        svc = ServiceInfo(
            name="my-service",
            namespace="production",
            endpoints=["http://ep1:8080", "http://ep2:8080"],
        )
        assert svc.name == "my-service"
        assert svc.namespace == "production"
        assert len(svc.endpoints) == 2
        assert svc.status == ServiceStatus.AVAILABLE

    def test_service_info_defaults(self):
        svc = ServiceInfo(name="default-svc")
        assert svc.namespace == "default"
        assert svc.endpoints == []
        assert svc.metadata == {}
        assert svc.version == ""

    def test_to_dict(self):
        svc = ServiceInfo(
            name="svc1",
            namespace="ns1",
            endpoints=["http://ep1:8080"],
            status=ServiceStatus.DEGRADED,
            metadata={"desc": "test"},
            version="2.0.0",
        )
        d = svc.to_dict()
        assert d["name"] == "svc1"
        assert d["namespace"] == "ns1"
        assert d["endpoints"] == ["http://ep1:8080"]
        assert d["status"] == "degraded"
        assert d["version"] == "2.0.0"

    def test_from_dict(self):
        data = {
            "name": "svc1",
            "namespace": "ns1",
            "endpoints": ["http://ep1:8080"],
            "status": "available",
            "version": "1.0.0",
        }
        svc = ServiceInfo.from_dict(data)
        assert svc.name == "svc1"
        assert svc.namespace == "ns1"
        assert svc.status == ServiceStatus.AVAILABLE

    def test_to_dict_from_dict_roundtrip(self):
        svc = ServiceInfo(
            name="svc-round",
            namespace="test",
            endpoints=["http://a:1"],
            metadata={"key": "value"},
        )
        restored = ServiceInfo.from_dict(svc.to_dict())
        assert restored.name == svc.name
        assert restored.namespace == svc.namespace
        assert restored.endpoints == svc.endpoints


class TestClusterConfig:
    """测试集群配置模型"""

    def test_default_config(self):
        config = ClusterConfig()
        assert config.cluster_name == "myeap"
        assert config.node_id == ""
        assert config.discovery_backend == "etcd"
        assert config.discovery_endpoints == ["localhost:2379"]
        assert config.heartbeat_interval == 30
        assert config.heartbeat_timeout == 10
        assert config.node_ttl == 90
        assert config.ha_enabled is True
        assert config.ha_role == NodeRole.ACTIVE
        assert config.failover_timeout == 30
        assert config.max_failover_count == 3
        assert config.config_reload_enabled is True
        assert config.config_poll_interval == 5
        assert config.k8s_namespace == "default"
        assert config.k8s_incluster is False
        assert config.labels == {}

    def test_custom_config(self):
        config = ClusterConfig(
            cluster_name="myeap-prod",
            node_id="node-1",
            discovery_backend="consul",
            discovery_endpoints=["consul:8500"],
            heartbeat_interval=10,
            ha_role=NodeRole.STANDBY,
            max_failover_count=5,
        )
        assert config.cluster_name == "myeap-prod"
        assert config.node_id == "node-1"
        assert config.discovery_backend == "consul"
        assert config.heartbeat_interval == 10
        assert config.ha_role == NodeRole.STANDBY
        assert config.max_failover_count == 5

    def test_to_dict(self):
        config = ClusterConfig(
            cluster_name="test-cluster",
            node_id="node-1",
            labels={"env": "test"},
        )
        d = config.to_dict()
        assert d["cluster_name"] == "test-cluster"
        assert d["node_id"] == "node-1"
        assert d["ha_role"] == "active"
        assert d["labels"] == {"env": "test"}
