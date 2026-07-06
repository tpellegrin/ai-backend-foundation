from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config.settings import AppSettings
from app.observability.health import ProbeRegistry
from app.platform.cache.ports import Cache
from app.platform.storage.ports import BlobStorage


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
    blob_storage: BlobStorage | None = None
    cache: Cache | None = None
