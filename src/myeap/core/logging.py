"""日志配置"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from structlog.types import Processor

from myeap.core.config import get_settings


def setup_logging(log_level: str = "INFO") -> None:
    """配置结构化日志"""
    settings = get_settings()

    # 时间戳处理器
    timestamper = structlog.processors.TimeStamper(
        fmt="iso",
        utc=True,
    )

    # 日志级别处理器
    add_log_level = structlog.processors.add_log_level

    # 异常处理器
    add_exc_info = structlog.processors.ExceptionRenderer(
        exception_formatter=structlog.dev.plain_traceback,
    )

    # JSON渲染（生产环境）
    if settings.environment == "production":
        renderer = structlog.processors.JSONRenderer()
    else:
        # 控制台渲染（开发环境）
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            timestamper,
            structlog.processors.StackInfoRenderer(),
            add_exc_info,
            structlog.processors.UnicodeDecoder(),
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """获取命名的logger"""
    return structlog.get_logger(name)


class LoggerMixin:
    """日志混入类"""

    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        if not hasattr(self, "_logger"):
            self._logger = structlog.get_logger(self.__class__.__name__)
        return self._logger
