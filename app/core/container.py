from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config.settings import AppSettings
from app.observability.health import ProbeRegistry


@dataclass
class Container:
    """Composition root for the application.

    This dataclass holds all adapters and providers. It is incremental;
    fields are added as their wiring tasks are completed.
    """

    settings: AppSettings
    probe_registry: ProbeRegistry
    db_engine: AsyncEngine | None = None
    session_factory: async_sessionmaker[AsyncSession] | None = None
