"""FastAPI application entry point for MyEAP.

Creates and configures the FastAPI application with all routers,
middleware, and lifecycle handlers.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from myeap.api.middleware import setup_middleware
from myeap.api.routes import (
    alarm,
    equipment,
    fdc,
    recipe,
    spc,
    system,
    tracking,
    work_order,
)
from myeap.core.config import get_settings
from myeap.core.exceptions import MyEAPException
from myeap.core.logging import get_logger
from myeap.observability.metrics import get_metrics_collector

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown.

    Args:
        app: The FastAPI application instance.
    """
    settings = get_settings()
    logger.info(
        "api_starting",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )

    # Startup
    try:
        from myeap.db.session import get_db_manager

        db_manager = get_db_manager()
        logger.info("database_initialized")
    except Exception as e:
        logger.warning("database_init_skipped", error=str(e))

    yield

    # Shutdown
    logger.info("api_shutting_down")
    try:
        from myeap.db.session import get_db_manager

        await get_db_manager().close()
    except Exception:
        pass


app = FastAPI(
    title="MyEAP",
    description="Equipment Automation Platform - REST API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware
setup_middleware(app)

# Include routers
app.include_router(equipment.router, prefix="/api/v1/equipment", tags=["Equipment"])
app.include_router(recipe.router, prefix="/api/v1/recipes", tags=["Recipe"])
app.include_router(alarm.router, prefix="/api/v1/alarms", tags=["Alarm"])
app.include_router(work_order.router, prefix="/api/v1/work-orders", tags=["Work Order"])
app.include_router(tracking.router, prefix="/api/v1/tracking", tags=["Tracking"])
app.include_router(spc.router, prefix="/api/v1/spc", tags=["SPC"])
app.include_router(fdc.router, prefix="/api/v1/fdc", tags=["FDC"])
app.include_router(system.router, prefix="/api/v1/system", tags=["System"])


# Exception handlers
@app.exception_handler(MyEAPException)
async def myeap_exception_handler(request: Request, exc: MyEAPException) -> JSONResponse:
    """Handle MyEAP custom exceptions."""
    logger.warning(
        "myeap_exception",
        code=exc.code,
        message=exc.message,
        path=str(request.url.path),
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {"code": exc.code, "message": exc.message, "details": exc.details},
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Handle ValueError exceptions."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": {"code": "VALUE_ERROR", "message": str(exc)}},
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle 404 Not Found."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": {"code": "NOT_FOUND", "message": f"Resource not found: {request.url.path}"}},
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle internal server errors."""
    logger.error(
        "internal_error",
        path=str(request.url.path),
        error=str(exc),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
            }
        },
    )


# Root health endpoint
@app.get("/health")
async def health() -> Dict[str, Any]:
    """Health check endpoint."""
    settings = get_settings()
    return {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.environment,
    }


@app.get("/")
async def root() -> Dict[str, Any]:
    """API root with basic information."""
    settings = get_settings()
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
    }


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint."""
    try:
        import prometheus_client

        return Response(
            content=prometheus_client.generate_latest(),
            media_type="text/plain; charset=utf-8",
        )
    except ImportError:
        collector = get_metrics_collector()
        return JSONResponse(content=collector.get_all())
