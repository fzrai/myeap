"""集群引擎模块

集群管理的核心引擎，协调服务发现、高可用管理和配置热更新。
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

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

logger = logging.getLogger(__name__)


class ClusterEngine:
    """集群引擎

    集群管理的核心编排类，整合服务发现、高可用和配置管理。

    Attributes:
        config: 集群配置
        discovery: 服务发现实例
        ha: 高可用管理器
        config_watcher: 配置监听器
        _running: 运行状态

    Example:
        config = ClusterConfig(cluster_name="myeap-prod", node_id="node-1")
        engine = ClusterEngine(config)
        engine.register_health_check("db", check_db_health)
        await engine.start()
        nodes = await engine.get_cluster_nodes()
    """

    def __init__(self, config: Optional[ClusterConfig] = None):
        """初始化集群引擎

        Args:
            config: 集群配置，不提供则使用默认配置
        """
        self.config = config or ClusterConfig()

        # 如果未设置节点ID，自动生成
        if not self.config.node_id:
            self.config.node_id = self._generate_node_id()

        # 初始化子模块
        self.discovery = ServiceDiscovery(
            registry_backend=self.config.discovery_backend
        )
        self.ha = HAManager(
            node_id=self.config.node_id,
            role=self.config.ha_role.value,
            max_failover_count=self.config.max_failover_count,
            failover_cooldown=self.config.failover_timeout,
        )

        # 配置监听器（可选）
        self.config_watcher: Optional[ConfigWatcher] = None

        self._running: bool = False
        self._started_at: Optional[datetime] = None

        # 事件回调
        self._on_event: Optional[Callable[[str, Dict[str, Any]], Any]] = None

        # 默认健康检查
        self._registered_default_checks: bool = False

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running

    @property
    def node_id(self) -> str:
        """当前节点ID"""
        return self.config.node_id

    @property
    def cluster_name(self) -> str:
        """集群名称"""
        return self.config.cluster_name

    @property
    def uptime_seconds(self) -> Optional[float]:
        """运行时长（秒）"""
        if self._started_at:
            return (datetime.now(timezone.utc) - self._started_at).total_seconds()
        return None

    # ---- 生命周期管理 ----

    async def start(self) -> None:
        """启动集群引擎

        执行以下步骤：
        1. 启动服务发现
        2. 注册当前节点
        3. 启动健康监测
        4. 启动配置监听
        5. 注册默认健康检查
        """
        if self._running:
            logger.warning("Cluster engine already running")
            return

        logger.info(
            "Starting cluster engine: cluster=%s, node=%s",
            self.cluster_name,
            self.node_id,
        )

        # 1. 注册默认健康检查
        if not self._registered_default_checks:
            self._register_default_health_checks()
            self._registered_default_checks = True

        # 2. 注册当前节点到服务发现
        await self.discovery.register_node(
            node_id=self.node_id,
            address=self._get_local_address(),
            metadata={
                "cluster": self.cluster_name,
                "role": self.config.ha_role.value,
                "version": self._get_version(),
            },
            labels=self.config.labels,
        )

        # 3. 启动心跳监控
        self.discovery.start_heartbeat_monitor(
            timeout=self.config.node_ttl,
            cleanup_interval=self.config.heartbeat_interval // 2,
        )

        # 4. 设置HA回调
        self.ha.on_failover(self._handle_failover)
        self.ha.on_role_change(self._handle_role_change)

        # 5. 如果HA启用，启动健康监测
        if self.config.ha_enabled:
            self.ha.start_health_monitoring()

        # 6. 启动配置监听（如果配置了路径）
        if self.config.config_reload_enabled:
            config_path = os.environ.get(
                "MYEAP_CONFIG_PATH",
                os.path.join(os.getcwd(), "config", "myeap.json"),
            )
            if os.path.exists(config_path):
                self.config_watcher = ConfigWatcher(config_path)
                await self.config_watcher.start(
                    poll_interval=self.config.config_poll_interval
                )

        self._running = True
        self._started_at = datetime.now(timezone.utc)

        # 启动心跳循环
        asyncio.create_task(self._heartbeat_loop())

        logger.info(
            "Cluster engine started: cluster=%s, node=%s, role=%s",
            self.cluster_name,
            self.node_id,
            self.ha.role,
        )

        await self._emit_event("engine_started", {"node_id": self.node_id})

    async def stop(self) -> None:
        """停止集群引擎

        执行以下步骤：
        1. 注销节点
        2. 停止健康监测
        3. 停止配置监听
        4. 停止心跳监控
        5. 清理服务发现
        """
        if not self._running:
            return

        logger.info(
            "Stopping cluster engine: cluster=%s, node=%s",
            self.cluster_name,
            self.node_id,
        )

        self._running = False

        # 1. 注销节点
        await self.discovery.deregister_node(self.node_id)

        # 2. 停止HA
        await self.ha.shutdown()

        # 3. 停止配置监听
        if self.config_watcher:
            await self.config_watcher.stop()

        # 4. 停止服务发现
        await self.discovery.shutdown()

        self._started_at = None
        logger.info("Cluster engine stopped")

        await self._emit_event("engine_stopped", {"node_id": self.node_id})

    # ---- 节点管理 ----

    async def get_local_node(self) -> Optional[NodeInfo]:
        """获取本地节点信息

        Returns:
            Optional[NodeInfo]: 节点信息
        """
        return await self.discovery.get_node(self.node_id)

    async def get_cluster_nodes(self) -> List[Dict[str, Any]]:
        """获取集群节点列表

        Returns:
            节点列表
        """
        return await self.discovery.get_active_nodes()

    async def get_cluster_node_count(self) -> int:
        """获取集群节点数量

        Returns:
            活跃节点数量
        """
        return await self.discovery.get_node_count()

    async def update_local_heartbeat(self) -> None:
        """更新本地节点心跳"""
        await self.discovery.heartbeat(self.node_id)

    # ---- 服务管理 ----

    async def register_service(
        self,
        name: str,
        endpoints: List[str],
        namespace: str = "default",
    ) -> ServiceInfo:
        """注册服务

        Args:
            name: 服务名称
            endpoints: 端点列表
            namespace: 命名空间

        Returns:
            ServiceInfo: 服务信息
        """
        return await self.discovery.register_service(
            name=name,
            endpoints=endpoints,
            namespace=namespace,
        )

    async def get_service(
        self,
        name: str,
        namespace: str = "default",
    ) -> Optional[ServiceInfo]:
        """获取服务信息

        Args:
            name: 服务名称
            namespace: 命名空间

        Returns:
            Optional[ServiceInfo]: 服务信息
        """
        return await self.discovery.get_service(name, namespace)

    # ---- HA管理 ----

    def register_health_check(
        self,
        name: str,
        check: Callable[[], Any],
        interval: int = 30,
    ) -> None:
        """注册健康检查

        Args:
            name: 检查名称
            check: 检查函数
            interval: 检查间隔
        """
        self.ha.register_health_check(name, check, interval)

    def unregister_health_check(self, name: str) -> bool:
        """取消注册健康检查

        Args:
            name: 检查名称

        Returns:
            bool: 是否成功
        """
        return self.ha.unregister_health_check(name)

    async def run_health_checks(self) -> Dict[str, HealthCheckResult]:
        """运行所有健康检查

        Returns:
            检查结果字典
        """
        return await self.ha.run_all_checks()

    async def check_health(self) -> bool:
        """检查整体健康状态

        Returns:
            bool: 是否所有检查都健康
        """
        return await self.ha.check_health_status()

    async def trigger_failover(self, reason: str = "manual") -> bool:
        """手动触发故障切换

        Args:
            reason: 切换原因

        Returns:
            bool: 是否成功触发
        """
        return await self.ha.trigger_failover(reason)

    def promote_to_active(self) -> None:
        """提升为活跃节点"""
        self.ha.promote_to_active()

    def demote_to_standby(self) -> None:
        """降级为备用节点"""
        self.ha.demote_to_standby()

    # ---- 配置管理 ----

    async def watch_config_key(
        self,
        key: str,
        callback: Callable[[str, Any], Any],
    ) -> None:
        """监听配置键变更

        Args:
            key: 配置键
            callback: 变更回调
        """
        if self.config_watcher:
            self.config_watcher.watch(key, callback)

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """获取配置值

        Args:
            key: 配置键
            default: 默认值

        Returns:
            配置值
        """
        if self.config_watcher:
            return self.config_watcher.get(key, default)
        return default

    async def reload_config(self) -> Optional[Dict[str, Any]]:
        """重新加载配置

        Returns:
            新配置字典
        """
        if self.config_watcher:
            return await self.config_watcher.reload()
        return None

    # ---- 事件回调 ----

    def on_event(self, callback: Callable[[str, Dict[str, Any]], Any]) -> None:
        """设置集群事件回调

        Args:
            callback: 回调函数 (event_type, event_data) -> Any
        """
        self._on_event = callback

    def on_node_join(self, callback: Callable[[NodeInfo], Any]) -> None:
        """设置节点加入回调

        Args:
            callback: 回调函数
        """
        self.discovery.on_node_join(callback)

    def on_node_leave(self, callback: Callable[[NodeInfo], Any]) -> None:
        """设置节点离开回调

        Args:
            callback: 回调函数
        """
        self.discovery.on_node_leave(callback)

    def on_config_change(self, callback: Callable[[ConfigChangeEvent], Any]) -> None:
        """设置配置变更回调

        Args:
            callback: 回调函数
        """
        if self.config_watcher:
            self.config_watcher.on_change(callback)

    # ---- 内部方法 ----

    def _generate_node_id(self) -> str:
        """生成节点ID"""
        hostname = os.environ.get("HOSTNAME", "unknown")
        short_id = uuid.uuid4().hex[:8]
        return f"{hostname}-{short_id}"

    def _get_local_address(self) -> str:
        """获取本地地址"""
        host = os.environ.get("POD_IP", os.environ.get("HOST", "127.0.0.1"))
        port = int(os.environ.get("PORT", "8000"))
        return f"{host}:{port}"

    @staticmethod
    def _get_version() -> str:
        """获取版本"""
        try:
            from myeap import __version__
            return __version__
        except ImportError:
            return "0.1.0"

    def _register_default_health_checks(self) -> None:
        """注册默认健康检查"""
        self.ha.register_health_check(
            "cluster_self",
            lambda: True,
            interval=30,
        )

    async def _heartbeat_loop(self) -> None:
        """心跳循环"""
        while self._running:
            try:
                await self.discovery.heartbeat(self.node_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Heartbeat error: %s", e)

            await asyncio.sleep(self.config.heartbeat_interval)

    async def _handle_failover(self, reason: str) -> None:
        """处理故障切换

        Args:
            reason: 切换原因
        """
        previous_role = self.config.ha_role.value
        logger.warning("Cluster failover triggered: %s (previous_role=%s)", reason, previous_role)
        self.config.ha_role = NodeRole.STANDBY
        await self._emit_event("failover", {
            "node_id": self.node_id,
            "reason": reason,
            "previous_role": previous_role,
        })

    async def _handle_role_change(self, old_role: str, new_role: str) -> None:
        """处理角色变更

        Args:
            old_role: 旧角色
            new_role: 新角色
        """
        await self._emit_event("role_change", {
            "node_id": self.node_id,
            "old_role": old_role,
            "new_role": new_role,
        })

    async def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """发送集群事件

        Args:
            event_type: 事件类型
            data: 事件数据
        """
        if self._on_event:
            try:
                result = self._on_event(event_type, data)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.exception("Error in event callback: %s", e)
