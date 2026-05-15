"""异步数据库会话管理"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from myeap.core.config import get_settings


class DatabaseManager:
    """数据库管理器"""

    def __init__(
        self,
        database_url: str | None = None,
        pool_size: int = 20,
        max_overflow: int = 10,
    ):
        """初始化数据库管理器

        Args:
            database_url: 数据库连接URL，如果为None则使用配置中的URL
            pool_size: 连接池大小
            max_overflow: 最大溢出连接数
        """
        if database_url is None:
            settings = get_settings()
            database_url = settings.database.url
            pool_size = settings.database.pool_size
            max_overflow = settings.database.max_overflow

        self.engine: AsyncEngine = create_async_engine(
            database_url,
            echo=False,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
        )
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取数据库会话的依赖注入函数

        Yields:
            AsyncSession: 异步数据库会话
        """
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    @asynccontextmanager
    async def session_scope(
        self,
    ) -> AsyncGenerator[AsyncSession, None]:
        """上下文管理器形式的会话

        Yields:
            AsyncSession: 异步数据库会话
        """
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def close(self) -> None:
        """关闭数据库连接"""
        await self.engine.dispose()


# 全局数据库管理器实例
_db_manager: DatabaseManager | None = None


def get_db_manager() -> DatabaseManager:
    """获取数据库管理器单例"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def get_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话的快捷函数"""
    return get_db_manager().get_session()
