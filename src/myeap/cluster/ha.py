"""高可用管理模块

提供节点角色管理、健康检查、故障切换等功能。
支持主备架构和基于健康检查的自动故障切换。
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, Optional

from myeap.cluster.models import NodeRole

logger = logging.getLogger(__name__)


class FailoverReason(str, Enum):
    """故障切换原因"""
    HEALTH_CHECK_FAILED = "health_check_failed"
    MANUAL_TRIGGER = "manual_trigger"
    NODE_TIMEOUT = "node_timeout"
    FORCE_TAKEOVER = "force_takeover"


@dataclass
class HealthCheckResult:
    """健康检查结果

    Attributes:
        name: 检查名称
        healthy: 是否健康
        message: 结果消息
        details: 详细信息
        timestamp: 检查时间
        latency_ms: 响应延迟（毫秒）
    """
    name: str
    healthy: bool
    message: str = ""
    details: Dict[str, Any] = None
    timestamp: datetime = None
    latency_ms: float = 0.0

    def __post_init__(self):
        if self.details is None:
            self.details = {}
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


class HAManager:
    """高可用管理器

    负责节点角色管理、健康监测和自动故障切换。

    Attributes:
        node_id: 当前节点ID
        role: 当前角色（active/standby）
        _health_checks: 健康检查注册表
        _failover_handler: 故障切换回调
        _failover_count: 故障切换计数
        _max_failover_count: 最大故障切换次数
        _role_change_handler: 角色变更回调
        _monitor_task: 监控后台任务

    Example:
        ha = HAManager("node-1", role="active")
        ha.register_health_check("database", check_db, interval=10)
        ha.on_failover(lambda reason: activate_standby())
        ha.start_health_monitoring()
    """

    def __init__(
        self,
        node_id: str,
        role: str = "active",
        max_failover_count: int = 3,
        failover_cooldown: int = 60,
    ):
        """初始化高可用管理器

        Args:
            node_id: 节点ID
            role: 初始角色 (active/standby)
            max_failover_count: 最大故障切换次数（0表示无限制）
            failover_cooldown: 故障切换冷却时间（秒）
        """
        self.node_id = node_id
        self.role = role  # active, standby
        self.max_failover_count = max_failover_count
        self.failover_cooldown = failover_cooldown

        self._health_checks: Dict[str, dict] = {}
        self._monitor_task: Optional[asyncio.Task] = None

        # 回调
        self._failover_handler: Optional[Callable[[str], Any]] = None
        self._role_change_handler: Optional[Callable[[str, str], Any]] = None
        self._health_status_handler: Optional[Callable[[str, bool], Any]] = None

        # 统计数据
        self._failover_count: int = 0
        self._last_failover_time: Optional[datetime] = None
        self._consecutive_failures: Dict[str, int] = {}
        self._max_consecutive_failures: int = 3

    @property
    def is_active(self) -> bool:
        """是否为活跃角色"""
        return self.role == NodeRole.ACTIVE.value

    @property
    def failover_count(self) -> int:
        """故障切换次数"""
        return self._failover_count

    def register_health_check(
        self,
        name: str,
        check: Callable[[], Any],
        interval: int = 30,
    ) -> None:
        """注册健康检查

        Args:
            name: 检查名称
            check: 健康检查函数（返回布尔值表示健康状态）
            interval: 检查间隔（秒）
        """
        self._health_checks[name] = {
            "check": check,
            "interval": interval,
        }
        logger.info("Health check registered: %s (interval=%ds)", name, interval)

    def unregister_health_check(self, name: str) -> bool:
        """取消注册健康检查

        Args:
            name: 检查名称

        Returns:
            bool: 是否成功取消
        """
        if name in self._health_checks:
            del self._health_checks[name]
            logger.info("Health check unregistered: %s", name)
            return True
        return False

    def on_failover(self, handler: Callable[[str], Any]) -> None:
        """设置故障切换回调

        Args:
            handler: 回调函数（接收failover原因字符串）
        """
        self._failover_handler = handler

    def on_role_change(self, handler: Callable[[str, str], Any]) -> None:
        """设置角色变更回调

        Args:
            handler: 回调函数（接收old_role, new_role）
        """
        self._role_change_handler = handler

    def on_health_status(self, handler: Callable[[str, bool], Any]) -> None:
        """设置健康状态变化回调

        Args:
            handler: 回调函数（接收check_name, is_healthy）
        """
        self._health_status_handler = handler

    def start_health_monitoring(self) -> None:
        """启动健康监测循环

        在后台启动异步任务，定期执行所有注册的健康检查。
        """
        if self._monitor_task is None or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self._health_monitor_loop())
            logger.info("Health monitoring started for node %s (role=%s)", self.node_id, self.role)

    def stop_health_monitoring(self) -> None:
        """停止健康监测"""
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            self._monitor_task = None
            logger.info("Health monitoring stopped")

    async def run_health_check(self, name: str) -> HealthCheckResult:
        """运行指定健康检查

        Args:
            name: 检查名称

        Returns:
            HealthCheckResult: 检查结果
        """
        check_config = self._health_checks.get(name)
        if not check_config:
            return HealthCheckResult(
                name=name,
                healthy=False,
                message=f"Health check not found: {name}",
            )

        start = datetime.now(timezone.utc)
        try:
            check_fn = check_config["check"]
            result = check_fn()
            if asyncio.iscoroutine(result):
                result = await result

            latency_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            healthy = bool(result)

            return HealthCheckResult(
                name=name,
                healthy=healthy,
                message="OK" if healthy else "FAIL",
                details={"latency_ms": latency_ms},
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            return HealthCheckResult(
                name=name,
                healthy=False,
                message=f"Error: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__},
                latency_ms=latency_ms,
            )

    async def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """运行所有健康检查

        Returns:
            Dict[str, HealthCheckResult]: 检查结果字典
        """
        results = {}
        for name in self._health_checks:
            result = await self.run_health_check(name)
            results[name] = result

            # 通知健康状态变化
            if self._health_status_handler:
                await self._invoke_callback(
                    self._health_status_handler, name, result.healthy
                )

        return results

    async def check_health_status(self) -> bool:
        """检查整体健康状态

        Returns:
            bool: 是否所有检查都健康
        """
        results = await self.run_all_checks()
        return all(r.healthy for r in results.values())

    def switch_role(self, new_role: str) -> None:
        """切换节点角色

        Args:
            new_role: 新角色 (active/standby/witness)
        """
        if new_role != self.role:
            old_role = self.role
            self.role = new_role
            logger.info(
                "Node %s role switched: %s -> %s",
                self.node_id,
                old_role,
                new_role,
            )

            if self._role_change_handler:
                try:
                    self._role_change_handler(old_role, new_role)
                except Exception as e:
                    logger.exception("Error in role change callback: %s", e)

    def promote_to_active(self) -> None:
        """提升为活跃节点"""
        self.switch_role(NodeRole.ACTIVE.value)

    def demote_to_standby(self) -> None:
        """降级为备用节点"""
        self.switch_role(NodeRole.STANDBY.value)

    async def trigger_failover(
        self,
        reason: str,
    ) -> bool:
        """手动触发故障切换

        Args:
            reason: 切换原因

        Returns:
            bool: 是否成功触发
        """
        if not self.is_active:
            logger.warning(
                "Cannot trigger failover for non-active node %s (role=%s)",
                self.node_id,
                self.role,
            )
            return False

        # 检查冷却时间
        if self._last_failover_time:
            cooldown_remaining = self.failover_cooldown - (
                datetime.now(timezone.utc) - self._last_failover_time
            ).total_seconds()
            if cooldown_remaining > 0:
                logger.warning(
                    "Failover cooldown active for node %s (remaining=%ds)",
                    self.node_id,
                    int(cooldown_remaining),
                )
                return False

        # 检查最大切换次数
        if self.max_failover_count > 0 and self._failover_count >= self.max_failover_count:
            logger.error(
                "Max failover count reached for node %s (%d/%d)",
                self.node_id,
                self._failover_count,
                self.max_failover_count,
            )
            return False

        self._failover_count += 1
        self._last_failover_time = datetime.now(timezone.utc)

        logger.warning(
            "Failover triggered for node %s (reason=%s, count=%d)",
            self.node_id,
            reason,
            self._failover_count,
        )

        # 切换角色
        self.demote_to_standby()

        # 触发回调
        if self._failover_handler:
            await self._invoke_callback(self._failover_handler, reason)

        return True

    async def _health_monitor_loop(self) -> None:
        """健康监测后台循环"""
        if not self._health_checks:
            logger.warning("No health checks registered")
            return

        while True:
            for name, config in self._health_checks.items():
                try:
                    result = await self.run_health_check(name)

                    if not result.healthy:
                        # 跟踪连续失败
                        self._consecutive_failures[name] = (
                            self._consecutive_failures.get(name, 0) + 1
                        )

                        logger.warning(
                            "Health check failed: %s (consecutive=%d): %s",
                            name,
                            self._consecutive_failures[name],
                            result.message,
                        )

                        # 连续失败触发故障切换
                        if (
                            self.is_active
                            and self._consecutive_failures[name] >= self._max_consecutive_failures
                        ):
                            await self.trigger_failover(
                                f"{FailoverReason.HEALTH_CHECK_FAILED.value}:{name}"
                            )
                    else:
                        # 重置连续失败计数
                        self._consecutive_failures[name] = 0

                except asyncio.CancelledError:
                    return
                except Exception as e:
                    logger.error("Health monitor error for check %s: %s", name, e)

            # 按最小检查间隔睡眠
            if self._health_checks:
                min_interval = min(
                    config["interval"] for config in self._health_checks.values()
                )
                try:
                    await asyncio.sleep(min_interval)
                except asyncio.CancelledError:
                    return

    async def shutdown(self) -> None:
        """关闭高可用管理器"""
        self.stop_health_monitoring()
        logger.info("HA Manager shutdown complete for node %s", self.node_id)

    def reset_stats(self) -> None:
        """重置统计数据"""
        self._failover_count = 0
        self._last_failover_time = None
        self._consecutive_failures.clear()

    @staticmethod
    async def _invoke_callback(callback: Callable, *args: Any) -> None:
        """调用回调函数

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
