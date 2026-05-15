"""服务发现模块

提供集群节点的注册、发现、心跳和健康管理。
支持多种注册后端（etcd、consul、文件等）。
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set

from myeap.cluster.models import NodeInfo, NodeStatus, ServiceInfo, ServiceStatus

logger = logging.getLogger(__name__)


class ServiceDiscovery:
    """集群服务发现

    负责维护集群节点和服务注册表，管理节点生命周期。

    Attributes:
        backend: 注册后端标识
        _nodes: 注册的节点字典
        _services: 注册的服务字典
        _on_node_join: 节点加入回调
        _on_node_leave: 节点离开回调
        _on_node_timeout: 节点超时回调

    Example:
        discovery = ServiceDiscovery(registry_backend="etcd")
        await discovery.register_node("node-1", "192.168.1.10:8000", metadata={"zone": "A"})
        nodes = await discovery.get_active_nodes()
    """

    def __init__(self, registry_backend: str = "etcd"):
        """初始化服务发现

        Args:
            registry_backend: 注册后端类型 (etcd/consul/kubernetes/file)
        """
        self._nodes: Dict[str, NodeInfo] = {}
        self._services: Dict[str, ServiceInfo] = {}
        self._backend = registry_backend

        # 回调函数
        self._on_node_join: Optional[Callable[[NodeInfo], Any]] = None
        self._on_node_leave: Optional[Callable[[NodeInfo], Any]] = None
        self._on_node_timeout: Optional[Callable[[str], Any]] = None
        self._on_service_change: Optional[Callable[[ServiceInfo], Any]] = None

        # 心跳监控任务
        self._heartbeat_monitor_task: Optional[asyncio.Task] = None
        self._heartbeat_timeout: int = 90
        self._cleanup_interval: int = 15

    async def register_node(
        self,
        node_id: str,
        address: str,
        metadata: Optional[Dict[str, Any]] = None,
        host: str = "",
        port: int = 0,
        labels: Optional[Dict[str, str]] = None,
    ) -> NodeInfo:
        """注册集群节点

        Args:
            node_id: 节点唯一标识
            address: 节点地址
            metadata: 节点元数据
            host: 主机名
            port: 端口号
            labels: 节点标签

        Returns:
            NodeInfo: 注册的节点信息
        """
        node = NodeInfo(
            node_id=node_id,
            address=address,
            host=host,
            port=port,
            metadata=metadata or {},
            labels=labels or {},
            registered_at=datetime.now(timezone.utc),
            last_heartbeat=datetime.now(timezone.utc),
            status=NodeStatus.ACTIVE,
        )
        self._nodes[node_id] = node
        logger.info("Node registered: %s at %s", node_id, address)

        # 触发节点加入回调
        if self._on_node_join:
            await self._invoke_callback(self._on_node_join, node)

        return node

    async def deregister_node(self, node_id: str) -> bool:
        """注销节点

        Args:
            node_id: 节点ID

        Returns:
            bool: 是否成功注销
        """
        node = self._nodes.pop(node_id, None)
        if node:
            node.status = NodeStatus.REMOVED
            logger.info("Node deregistered: %s", node_id)

            # 触发节点离开回调
            if self._on_node_leave:
                await self._invoke_callback(self._on_node_leave, node)

            return True
        logger.warning("Node not found for deregistration: %s", node_id)
        return False

    async def get_node(self, node_id: str) -> Optional[NodeInfo]:
        """获取指定节点信息

        Args:
            node_id: 节点ID

        Returns:
            Optional[NodeInfo]: 节点信息，不存在返回None
        """
        return self._nodes.get(node_id)

    async def get_active_nodes(self) -> List[Dict[str, Any]]:
        """获取活跃节点列表

        Returns:
            活跃节点信息列表
        """
        return [
            {
                "node_id": nid,
                "address": info.address,
                "host": info.host,
                "port": info.port,
                "role": info.role.value,
                "status": info.status.value,
                "metadata": info.metadata,
                "labels": info.labels,
                "registered_at": info.registered_at.isoformat(),
                "last_heartbeat": info.last_heartbeat.isoformat(),
                "version": info.version,
            }
            for nid, info in self._nodes.items()
            if info.status == NodeStatus.ACTIVE
        ]

    async def get_all_nodes(self) -> List[Dict[str, Any]]:
        """获取所有节点列表（包括非活跃）"""
        return [
            {
                "node_id": nid,
                "address": info.address,
                "host": info.host,
                "status": info.status.value,
                "role": info.role.value,
                "last_heartbeat": info.last_heartbeat.isoformat(),
            }
            for nid, info in self._nodes.items()
        ]

    async def get_node_count(self) -> int:
        """获取活跃节点数量"""
        active = await self.get_active_nodes()
        return len(active)

    async def heartbeat(self, node_id: str) -> bool:
        """更新节点心跳

        Args:
            node_id: 节点ID

        Returns:
            bool: 是否成功更新
        """
        if node_id in self._nodes:
            self._nodes[node_id].last_heartbeat = datetime.now(timezone.utc)
            if self._nodes[node_id].status == NodeStatus.INACTIVE:
                self._nodes[node_id].status = NodeStatus.ACTIVE
                logger.info("Node recovered via heartbeat: %s", node_id)
            return True
        logger.debug("Heartbeat from unknown node: %s", node_id)
        return False

    async def update_node_metadata(
        self,
        node_id: str,
        metadata: Dict[str, Any],
    ) -> bool:
        """更新节点元数据

        Args:
            node_id: 节点ID
            metadata: 新的元数据（合并更新）

        Returns:
            bool: 是否成功更新
        """
        node = self._nodes.get(node_id)
        if node:
            node.metadata.update(metadata)
            return True
        return False

    async def set_node_status(self, node_id: str, status: NodeStatus) -> bool:
        """设置节点状态

        Args:
            node_id: 节点ID
            status: 新状态

        Returns:
            bool: 是否成功设置
        """
        node = self._nodes.get(node_id)
        if node:
            old_status = node.status
            node.status = status
            logger.info("Node %s status changed: %s -> %s", node_id, old_status.value, status.value)
            return True
        return False

    # ---- 服务注册 ----

    async def register_service(
        self,
        name: str,
        endpoints: List[str],
        namespace: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ServiceInfo:
        """注册服务

        Args:
            name: 服务名称
            endpoints: 端点列表
            namespace: 命名空间
            metadata: 元数据

        Returns:
            ServiceInfo: 注册的服务信息
        """
        service_key = f"{namespace}/{name}"
        service = ServiceInfo(
            name=name,
            namespace=namespace,
            endpoints=endpoints,
            metadata=metadata or {},
            registered_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._services[service_key] = service
        logger.info("Service registered: %s (endpoints: %d)", service_key, len(endpoints))

        if self._on_service_change:
            await self._invoke_callback(self._on_service_change, service)

        return service

    async def deregister_service(self, name: str, namespace: str = "default") -> bool:
        """注销服务

        Args:
            name: 服务名称
            namespace: 命名空间

        Returns:
            bool: 是否成功注销
        """
        service_key = f"{namespace}/{name}"
        service = self._services.pop(service_key, None)
        if service:
            service.status = ServiceStatus.UNAVAILABLE
            logger.info("Service deregistered: %s", service_key)

            if self._on_service_change:
                await self._invoke_callback(self._on_service_change, service)

            return True
        return False

    async def get_service(self, name: str, namespace: str = "default") -> Optional[ServiceInfo]:
        """获取服务信息

        Args:
            name: 服务名称
            namespace: 命名空间

        Returns:
            Optional[ServiceInfo]: 服务信息
        """
        service_key = f"{namespace}/{name}"
        return self._services.get(service_key)

    async def get_services(self, namespace: Optional[str] = None) -> List[ServiceInfo]:
        """获取服务列表

        Args:
            namespace: 命名空间过滤

        Returns:
            服务信息列表
        """
        services = list(self._services.values())
        if namespace:
            services = [s for s in services if s.namespace == namespace]
        return services

    async def update_service_endpoints(
        self,
        name: str,
        endpoints: List[str],
        namespace: str = "default",
    ) -> bool:
        """更新服务端点

        Args:
            name: 服务名称
            endpoints: 端点列表
            namespace: 命名空间

        Returns:
            bool: 是否成功更新
        """
        service = await self.get_service(name, namespace)
        if service:
            service.endpoints = endpoints
            service.updated_at = datetime.now(timezone.utc)
            return True
        return False

    # ---- 回调管理 ----

    def on_node_join(self, callback: Callable[[NodeInfo], Any]) -> None:
        """设置节点加入回调

        Args:
            callback: 回调函数
        """
        self._on_node_join = callback

    def on_node_leave(self, callback: Callable[[NodeInfo], Any]) -> None:
        """设置节点离开回调

        Args:
            callback: 回调函数
        """
        self._on_node_leave = callback

    def on_node_timeout(self, callback: Callable[[str], Any]) -> None:
        """设置节点超时回调

        Args:
            callback: 回调函数（接收node_id）
        """
        self._on_node_timeout = callback

    def on_service_change(self, callback: Callable[[ServiceInfo], Any]) -> None:
        """设置服务变更回调

        Args:
            callback: 回调函数
        """
        self._on_service_change = callback

    # ---- 心跳监控 ----

    def start_heartbeat_monitor(
        self,
        timeout: int = 90,
        cleanup_interval: int = 15,
    ) -> None:
        """启动心跳监控

        定期检查所有节点的心跳时间，清理超时节点。

        Args:
            timeout: 心跳超时（秒）
            cleanup_interval: 清理间隔（秒）
        """
        self._heartbeat_timeout = timeout
        self._cleanup_interval = cleanup_interval

        if self._heartbeat_monitor_task is None or self._heartbeat_monitor_task.done():
            self._heartbeat_monitor_task = asyncio.create_task(
                self._heartbeat_monitor_loop()
            )
            logger.info(
                "Heartbeat monitor started (timeout=%ds, interval=%ds)",
                timeout,
                cleanup_interval,
            )

    def stop_heartbeat_monitor(self) -> None:
        """停止心跳监控"""
        if self._heartbeat_monitor_task and not self._heartbeat_monitor_task.done():
            self._heartbeat_monitor_task.cancel()
            self._heartbeat_monitor_task = None
            logger.info("Heartbeat monitor stopped")

    async def _heartbeat_monitor_loop(self) -> None:
        """心跳监控循环"""
        while True:
            try:
                await self._check_heartbeats()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Heartbeat monitor error: %s", e)
            await asyncio.sleep(self._cleanup_interval)

    async def _check_heartbeats(self) -> None:
        """检查所有节点心跳"""
        now = datetime.now(timezone.utc)
        expired_nodes: List[str] = []

        for node_id, info in self._nodes.items():
            if info.status == NodeStatus.ACTIVE:
                delta = (now - info.last_heartbeat).total_seconds()
                if delta > self._heartbeat_timeout:
                    expired_nodes.append(node_id)

        for node_id in expired_nodes:
            node = self._nodes.get(node_id)
            if node:
                node.status = NodeStatus.INACTIVE
                logger.warning("Node heartbeat expired: %s (last: %s)", node_id, node.last_heartbeat)

                if self._on_node_timeout:
                    await self._invoke_callback(self._on_node_timeout, node_id)

    # ---- 清理 ----

    def clear(self) -> None:
        """清除所有注册信息"""
        self._nodes.clear()
        self._services.clear()
        logger.info("Service discovery cleared")

    async def shutdown(self) -> None:
        """关闭服务发现"""
        self.stop_heartbeat_monitor()
        self.clear()
        logger.info("Service discovery shutdown complete")

    @staticmethod
    async def _invoke_callback(callback: Callable, *args: Any) -> None:
        """调用回调函数（支持同步和异步）

        Args:
            callback: 回调函数
            *args: 回调参数
        """
        try:
            result = callback(*args)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.exception("Error invoking callback: %s", e)
