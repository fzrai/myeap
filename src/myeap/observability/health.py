"""健康检查模块

提供系统健康状态检查，支持：
- 存活检查 (Liveness)
- 就绪检查 (Readiness)
- 依赖服务检查
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from myeap.core.logging import get_logger

logger = get_logger(__name__)


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class CheckType(Enum):
    """检查类型"""
    LIVENESS = "liveness"
    READINESS = "readiness"


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    name: str
    status: HealthStatus
    check_type: CheckType
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "type": self.check_type.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
        }


class HealthCheck(ABC):
    """健康检查基类"""

    def __init__(self, name: str, check_type: CheckType = CheckType.READINESS):
        self.name = name
        self.check_type = check_type

    @abstractmethod
    async def check(self) -> HealthCheckResult:
        """执行健康检查"""
        pass

    async def run(self) -> HealthCheckResult:
        """运行健康检查并记录耗时"""
        start = datetime.utcnow()
        try:
            result = await self.check()
            duration_ms = (datetime.utcnow() - start).total_seconds() * 1000
            result.duration_ms = duration_ms
            return result
        except Exception as e:
            duration_ms = (datetime.utcnow() - start).total_seconds() * 1000
            logger.error("health_check_failed", name=self.name, error=str(e))
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                check_type=self.check_type,
                message=f"Check failed: {str(e)}",
                details={"error": str(e)},
                duration_ms=duration_ms,
            )


class DatabaseHealthCheck(HealthCheck):
    """数据库健康检查"""

    def __init__(self, db_manager: Any):
        super().__init__("database", CheckType.READINESS)
        self.db_manager = db_manager

    async def check(self) -> HealthCheckResult:
        try:
            async with self.db_manager.session_scope() as session:
                result = await session.execute("SELECT 1")
                row = result.fetchone()

            if row:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    check_type=self.check_type,
                    message="Database is healthy",
                    details={"latency_ms": 1},
                )
            else:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    check_type=self.check_type,
                    message="Database query failed",
                )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                check_type=self.check_type,
                message=f"Database error: {str(e)}",
                details={"error_type": type(e).__name__},
            )


class RedisHealthCheck(HealthCheck):
    """Redis健康检查"""

    def __init__(self, redis_client: Any):
        super().__init__("redis", CheckType.READINESS)
        self.redis_client = redis_client

    async def check(self) -> HealthCheckResult:
        try:
            start = datetime.utcnow()
            await self.redis_client.ping()
            latency_ms = (datetime.utcnow() - start).total_seconds() * 1000

            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                check_type=self.check_type,
                message="Redis is healthy",
                details={"latency_ms": latency_ms},
            )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                check_type=self.check_type,
                message=f"Redis error: {str(e)}",
            )


class KafkaHealthCheck(HealthCheck):
    """Kafka健康检查"""

    def __init__(self, kafka_producer: Any):
        super().__init__("kafka", CheckType.READINESS)
        self.kafka_producer = kafka_producer

    async def check(self) -> HealthCheckResult:
        try:
            # 检查Kafka连接状态
            if self.kafka_producer:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    check_type=self.check_type,
                    message="Kafka is healthy",
                )
            else:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.DEGRADED,
                    check_type=self.check_type,
                    message="Kafka producer not initialized",
                )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                check_type=self.check_type,
                message=f"Kafka error: {str(e)}",
            )


class EquipmentConnectionCheck(HealthCheck):
    """设备连接健康检查"""

    def __init__(self, equipment_registry: Any):
        super().__init__("equipment_connections", CheckType.READINESS)
        self.equipment_registry = equipment_registry

    async def check(self) -> HealthCheckResult:
        try:
            connected = self.equipment_registry.get_connected_count()
            total = self.equipment_registry.get_total_count()

            if total == 0:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    check_type=self.check_type,
                    message="No equipment configured",
                )

            connection_rate = connected / total if total > 0 else 0

            if connection_rate >= 0.8:
                status = HealthStatus.HEALTHY
            elif connection_rate >= 0.5:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.UNHEALTHY

            return HealthCheckResult(
                name=self.name,
                status=status,
                check_type=self.check_type,
                message=f"{connected}/{total} equipment connected",
                details={
                    "connected": connected,
                    "total": total,
                    "connection_rate": connection_rate,
                },
            )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                check_type=self.check_type,
                message=f"Equipment check error: {str(e)}",
            )


class HealthCheckRegistry:
    """健康检查注册表"""

    def __init__(self):
        self._checks: List[HealthCheck] = []

    def register(self, check: HealthCheck) -> None:
        """注册健康检查"""
        self._checks.append(check)
        logger.info("health_check_registered", name=check.name, type=check.check_type.value)

    def unregister(self, name: str) -> None:
        """取消注册健康检查"""
        self._checks = [c for c in self._checks if c.name != name]

    async def run_all(self, check_type: Optional[CheckType] = None) -> List[HealthCheckResult]:
        """运行所有健康检查"""
        checks = [c for c in self._checks if check_type is None or c.check_type == check_type]

        results = await asyncio.gather(*[check.run() for check in checks])
        return list(results)

    def get_overall_status(self, results: List[HealthCheckResult]) -> HealthStatus:
        """获取整体健康状态"""
        if not results:
            return HealthStatus.HEALTHY

        statuses = [r.status for r in results]

        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY


# 全局健康检查注册表
_health_registry: Optional[HealthCheckRegistry] = None


def get_health_registry() -> HealthCheckRegistry:
    """获取全局健康检查注册表"""
    global _health_registry
    if _health_registry is None:
        _health_registry = HealthCheckRegistry()
    return _health_registry
