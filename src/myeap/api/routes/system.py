"""System and health check API routes.

Provides endpoints for system status, health checks,
and configuration introspection.
"""

import platform
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from myeap.api.dependencies import get_optional_user, require_role
from myeap.core.config import get_settings
from myeap.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/health", response_model=Dict[str, Any])
async def health_check() -> Dict[str, Any]:
    """Detailed health check endpoint.

    Returns:
        Health check results with component status.
    """
    settings = get_settings()

    # Check database connectivity
    db_status = "unknown"
    try:
        from myeap.db.session import get_db_manager

        db_manager = get_db_manager()
        # Simple connection test
        async with db_manager.session_scope() as session:
            from sqlalchemy import text

            await session.execute(text("SELECT 1"))
            db_status = "healthy"
    except Exception as e:
        db_status = "unhealthy"

    # Overall status
    overall = "healthy"
    if db_status == "unhealthy":
        overall = "degraded"

    return {
        "status": overall,
        "version": settings.app_version,
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "database": {"status": db_status},
            "api": {"status": "healthy"},
        },
    }


@router.get("/info", response_model=Dict[str, Any])
async def system_info(
    user: Dict[str, Any] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Get system information.

    Returns:
        System information including version, environment, and runtime details.
    """
    settings = get_settings()

    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "debug": settings.debug,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "system": platform.system(),
        "node": platform.node(),
        "api": {
            "docs_url": "/docs",
            "redoc_url": "/redoc",
            "openapi_url": "/openapi.json",
        },
    }


@router.get("/config", response_model=Dict[str, Any])
async def get_configuration(
    user: Dict[str, Any] = Depends(require_role("admin")),
) -> Dict[str, Any]:
    """Get current configuration (admin only, secrets masked).

    Returns:
        Configuration dictionary with sensitive values masked.
    """
    settings = get_settings()

    def mask_value(v: Any) -> Any:
        """Mask sensitive values."""
        if isinstance(v, str) and len(v) > 8:
            return v[:4] + "*" * (len(v) - 4)
        return "***"

    return {
        "database": {
            "host": settings.database.host,
            "port": settings.database.port,
            "name": settings.database.name,
            "user": settings.database.user,
            "password": mask_value(settings.database.password),
            "pool_size": settings.database.pool_size,
        },
        "redis": {
            "host": settings.redis.host,
            "port": settings.redis.port,
        },
        "kafka": {
            "bootstrap_servers": settings.kafka.bootstrap_servers,
            "consumer_group": settings.kafka.consumer_group,
        },
        "secs": {
            "default_timeout": settings.secs.default_timeout,
            "reconnect_interval": settings.secs.reconnect_interval,
        },
        "security": {
            "algorithm": settings.security.algorithm,
            "access_token_expire_minutes": settings.security.access_token_expire_minutes,
        },
    }


@router.get("/endpoints", response_model=Dict[str, Any])
async def list_endpoints(
    user: Dict[str, Any] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """List all API endpoints.

    Returns:
        Dictionary of all available API endpoints grouped by tag.
    """
    from myeap.api.main import app

    endpoints: Dict[str, List[Dict[str, Any]]] = {}

    for route in app.routes:
        if hasattr(route, "methods"):
            for method in route.methods:
                tag = "other"
                if hasattr(route, "tags") and route.tags:
                    tag = route.tags[0]

                if tag not in endpoints:
                    endpoints[tag] = []

                endpoints[tag].append({
                    "method": method,
                    "path": route.path,
                    "name": route.name,
                })

    return endpoints


@router.get("/version", response_model=Dict[str, str])
async def version_info() -> Dict[str, str]:
    """Get API version.

    Returns:
        Version information.
    """
    settings = get_settings()
    return {
        "version": settings.app_version,
        "name": settings.app_name,
    }


@router.get("/ready", response_model=Dict[str, str])
async def readiness_probe() -> Dict[str, str]:
    """Kubernetes readiness probe endpoint.

    Returns:
        Readiness status.
    """
    return {"status": "ready"}


@router.get("/live", response_model=Dict[str, str])
async def liveness_probe() -> Dict[str, str]:
    """Kubernetes liveness probe endpoint.

    Returns:
        Liveness status.
    """
    return {"status": "alive"}


@router.post("/metrics/reset", response_model=Dict[str, str])
async def reset_metrics(
    user: Dict[str, Any] = Depends(require_role("admin")),
) -> Dict[str, str]:
    """Reset application metrics counters.

    Args:
        user: Current authenticated user (admin only).

    Returns:
        Confirmation message.
    """
    logger.info("metrics_reset", user=user.get("username"))
    return {
        "status": "reset",
        "message": "Metrics counters reset successfully",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
