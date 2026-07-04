from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config.settings import AppSettings
from app.infrastructure.db import create_engine_from, create_session_factory
from app.observability.health import ProbeResult


def setup_db(
    settings: AppSettings,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Initialize the database infrastructure."""
    engine = create_engine_from(settings.db)
    session_factory = create_session_factory(engine)
    return engine, session_factory


class DBProbe:
    """Database readiness probe."""

    name: str = "db"

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def check(self) -> ProbeResult:
        """Check the database connection."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return ProbeResult(name=self.name, status="ok")
