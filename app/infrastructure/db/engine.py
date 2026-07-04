from typing import Any, Protocol

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class DatabaseSettings(Protocol):
    """Protocol for database-specific settings."""

    url: Any


def create_engine_from(settings: DatabaseSettings) -> AsyncEngine:
    """Create an async SQLAlchemy engine from settings."""
    engine = create_async_engine(
        str(settings.url),
        echo=False,
    )

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory from an engine."""
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
