"""FastAPI middleware for MyEAP.

Provides request logging, timing, error handling, and request ID tracking.
"""

import time
import uuid
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from myeap.core.logging import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs incoming requests and their responses."""

    def __init__(self, app: ASGIApp, log_headers: bool = False):
        super().__init__(app)
        self.log_headers = log_headers

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        start_time = time.monotonic()
        method = request.method
        path = request.url.path

        logger.info(
            "api_request_start",
            request_id=request_id,
            method=method,
            path=path,
            client=request.client.host if request.client else "unknown",
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed = time.monotonic() - start_time
            logger.error(
                "api_request_error",
                request_id=request_id,
                method=method,
                path=path,
                elapsed_ms=round(elapsed * 1000, 2),
                error=str(exc),
            )
            raise

        elapsed = time.monotonic() - start_time
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "api_request_complete",
            request_id=request_id,
            method=method,
            path=path,
            status_code=response.status_code,
            elapsed_ms=round(elapsed * 1000, 2),
        )

        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Middleware that adds X-Process-Time header to all responses."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start_time = time.monotonic()
        response = await call_next(request)
        elapsed = time.monotonic() - start_time
        response.headers["X-Process-Time"] = str(round(elapsed * 1000, 2))
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that adds security headers to responses."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        return response


def setup_middleware(app: FastAPI) -> None:
    """Register all application middleware.

    Args:
        app: The FastAPI application instance.
    """
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
