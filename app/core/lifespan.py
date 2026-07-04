from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.container import Container
from app.core.wiring.db import DBProbe, setup_db


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

    try:
        yield
    finally:
        # 5. Shutdown -> not ready
        app.state.ready = False
        await _on_shutdown(container)


async def _on_startup(container: Container) -> None:
    """Run all startup hooks."""
    # DB wiring (T-701)
    engine, session_factory = setup_db(container.settings)
    container.db_engine = engine
    container.session_factory = session_factory
    container.probe_registry.add_probe(DBProbe(engine))


async def _on_shutdown(container: Container) -> None:
    """Run all shutdown hooks."""
    # DB cleanup (T-701)
    if container.db_engine:
        await container.db_engine.dispose()
