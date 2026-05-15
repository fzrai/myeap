"""集群管理模块

提供K8s集成、服务发现、高可用管理和配置热更新功能。
"""

from myeap.cluster.models import (
    ClusterConfig,
    NodeInfo,
    NodeRole,
    NodeStatus,
    ServiceInfo,
    ServiceStatus,
)
from myeap.cluster.discovery import ServiceDiscovery
from myeap.cluster.ha import HAManager, HealthCheckResult
from myeap.cluster.config_watcher import ConfigWatcher, ConfigChangeEvent
from myeap.cluster.engine import ClusterEngine

__all__ = [
    # Models
    "ClusterConfig",
    "NodeInfo",
    "NodeRole",
    "NodeStatus",
    "ServiceInfo",
    "ServiceStatus",
    # Discovery
    "ServiceDiscovery",
    # HA
    "HAManager",
    "HealthCheckResult",
    # Config
    "ConfigWatcher",
    "ConfigChangeEvent",
    # Engine
    "ClusterEngine",
]
