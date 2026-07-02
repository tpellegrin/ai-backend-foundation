from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config.settings import get_settings
from app.core.container import Container
from app.observability.health import ProbeRegistry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifecycle and dependency container.

    Initializes the container, runs startup hooks, and sets the readiness flag.
    """
    # 1. Bootstrap
    settings = get_settings()
    # T-504: Probe registry is bootstrapped empty here.
    probe_registry = ProbeRegistry([])

    # 2. Initialize Container
    container = Container(
        settings=settings,
        probe_registry=probe_registry,
    )

    # 3. Store on app state
    app.state.container = container
    app.state.ready = False

    # 4. Startup hooks
    await _on_startup(container)

    # Flip readiness flag only after success
    app.state.ready = True

    try:
        yield
    finally:
        # Flip back on shutdown
        app.state.ready = False
        await _on_shutdown(container)


async def _on_startup(container: Container) -> None:
    """Run all startup hooks."""
    # Placeholder for future wiring (T-701, T-702, etc.)
    pass


async def _on_shutdown(container: Container) -> None:
    """Run all shutdown hooks."""
    # Placeholder for future wiring
    pass
