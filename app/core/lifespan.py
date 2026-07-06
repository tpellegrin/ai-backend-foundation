from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.container import Container
from app.core.wiring.cache import RedisProbe, setup_cache, setup_redis_client, shutdown_redis
from app.core.wiring.db import DBProbe, setup_db
from app.core.wiring.storage import setup_storage


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifecycle and dependency container.

    Runs startup hooks and manages the readiness flag. The Container
    is pre-constructed and installed on app.state.container by the factory.
    """
    # 1. Read pre-constructed container
    container: Container = app.state.container

    # 2. Initial state: not ready
    app.state.ready = False

    # 3. Startup hooks
    await _on_startup(container)

    # 4. Success -> ready
    app.state.ready = True

    # Redis/Cache wiring (T-708)
    redis_client = setup_redis_client(container.settings)

    try:
        # Redis/Cache wiring (T-708)
        container.cache = setup_cache(redis_client)
        container.probe_registry.add_probe(RedisProbe(redis_client))
        yield
    finally:
        # 5. Shutdown -> not ready
        app.state.ready = False
        await _on_shutdown(container)
        # Redis cleanup (T-708)
        await shutdown_redis(redis_client)


async def _on_startup(container: Container) -> None:
    """Run all startup hooks."""
    # DB wiring (T-701)
    engine, session_factory = setup_db(container.settings)
    container.db_engine = engine
    container.session_factory = session_factory
    container.probe_registry.add_probe(DBProbe(engine))

    # Storage wiring (T-708)
    container.blob_storage = setup_storage(container.settings)


async def _on_shutdown(container: Container) -> None:
    """Run all shutdown hooks."""
    # DB cleanup (T-701)
    if container.db_engine:
        await container.db_engine.dispose()
