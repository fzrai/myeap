"""集群数据模型

定义集群节点、服务、配置等核心数据结构。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class NodeRole(str, Enum):
    """节点角色"""
    ACTIVE = "active"
    STANDBY = "standby"
    WITNESS = "witness"


class NodeStatus(str, Enum):
    """节点状态"""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    UNKNOWN = "UNKNOWN"
    STARTING = "STARTING"
    STOPPING = "STOPPING"
    REMOVED = "REMOVED"


class ServiceStatus(str, Enum):
    """服务状态"""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    STARTING = "starting"


@dataclass
class NodeInfo:
    """集群节点信息

    Attributes:
        node_id: 节点唯一标识
        address: 节点地址
        host: 主机名
        port: 端口
        role: 节点角色
        status: 节点状态
        metadata: 节点元数据
        registered_at: 注册时间
        last_heartbeat: 最后心跳时间
        version: 节点版本
        labels: 节点标签
    """
    node_id: str
    address: str
    host: str = ""
    port: int = 0
    role: NodeRole = NodeRole.ACTIVE
    status: NodeStatus = NodeStatus.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    version: str = ""
    labels: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "node_id": self.node_id,
            "address": self.address,
            "host": self.host,
            "port": self.port,
            "role": self.role.value,
            "status": self.status.value,
            "metadata": self.metadata,
            "registered_at": self.registered_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "version": self.version,
            "labels": self.labels,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodeInfo":
        """从字典创建"""
        return cls(
            node_id=data["node_id"],
            address=data["address"],
            host=data.get("host", ""),
            port=data.get("port", 0),
            role=NodeRole(data.get("role", "active")),
            status=NodeStatus(data.get("status", "ACTIVE")),
            metadata=data.get("metadata", {}),
            registered_at=datetime.fromisoformat(data["registered_at"])
                if "registered_at" in data else datetime.now(timezone.utc),
            last_heartbeat=datetime.fromisoformat(data["last_heartbeat"])
                if "last_heartbeat" in data else datetime.now(timezone.utc),
            version=data.get("version", ""),
            labels=data.get("labels", {}),
        )

    @property
    def is_active(self) -> bool:
        """是否为活跃状态"""
        return self.status == NodeStatus.ACTIVE

    @property
    def is_healthy(self) -> bool:
        """是否健康（心跳近期更新）"""
        delta = (datetime.now(timezone.utc) - self.last_heartbeat).total_seconds()
        return delta < 60  # 心跳间隔默认30秒，2倍容差


@dataclass
class ServiceInfo:
    """服务信息

    Attributes:
        name: 服务名称
        namespace: 命名空间
        endpoints: 端点列表
        status: 服务状态
        metadata: 元数据
        registered_at: 注册时间
        updated_at: 更新时间
        version: 版本
    """
    name: str
    namespace: str = "default"
    endpoints: List[str] = field(default_factory=list)
    status: ServiceStatus = ServiceStatus.AVAILABLE
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "namespace": self.namespace,
            "endpoints": self.endpoints,
            "status": self.status.value,
            "metadata": self.metadata,
            "registered_at": self.registered_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServiceInfo":
        """从字典创建"""
        return cls(
            name=data["name"],
            namespace=data.get("namespace", "default"),
            endpoints=data.get("endpoints", []),
            status=ServiceStatus(data.get("status", "available")),
            metadata=data.get("metadata", {}),
            registered_at=datetime.fromisoformat(data["registered_at"])
                if "registered_at" in data else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(data["updated_at"])
                if "updated_at" in data else datetime.now(timezone.utc),
            version=data.get("version", ""),
        )


@dataclass
class ClusterConfig:
    """集群配置

    Attributes:
        cluster_name: 集群名称
        node_id: 当前节点ID
        discovery_backend: 服务发现后端 (etcd/consul/kubernetes/file)
        discovery_endpoints: 服务发现端点列表
        heartbeat_interval: 心跳间隔（秒）
        heartbeat_timeout: 心跳超时（秒）
        node_ttl: 节点过期时间（秒）
        ha_enabled: 是否启用高可用
        ha_role: HA角色
        failover_timeout: 故障切换超时（秒）
        max_failover_count: 最大故障切换次数
        config_reload_enabled: 是否启用配置热更新
        config_poll_interval: 配置轮询间隔（秒）
        k8s_namespace: Kubernetes命名空间
        k8s_incluster: 是否使用集群内配置
        labels: 集群标签
    """
    cluster_name: str = "myeap"
    node_id: str = ""
    discovery_backend: str = "etcd"
    discovery_endpoints: List[str] = field(default_factory=lambda: ["localhost:2379"])
    heartbeat_interval: int = 30
    heartbeat_timeout: int = 10
    node_ttl: int = 90
    ha_enabled: bool = True
    ha_role: NodeRole = NodeRole.ACTIVE
    failover_timeout: int = 30
    max_failover_count: int = 3
    config_reload_enabled: bool = True
    config_poll_interval: int = 5
    k8s_namespace: str = "default"
    k8s_incluster: bool = False
    labels: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "cluster_name": self.cluster_name,
            "node_id": self.node_id,
            "discovery_backend": self.discovery_backend,
            "discovery_endpoints": self.discovery_endpoints,
            "heartbeat_interval": self.heartbeat_interval,
            "heartbeat_timeout": self.heartbeat_timeout,
            "node_ttl": self.node_ttl,
            "ha_enabled": self.ha_enabled,
            "ha_role": self.ha_role.value,
            "failover_timeout": self.failover_timeout,
            "max_failover_count": self.max_failover_count,
            "config_reload_enabled": self.config_reload_enabled,
            "config_poll_interval": self.config_poll_interval,
            "k8s_namespace": self.k8s_namespace,
            "k8s_incluster": self.k8s_incluster,
            "labels": self.labels,
        }
