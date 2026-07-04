from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import AppSettings
from app.core.container import Container
from app.observability.health import ProbeRegistry
from app.observability.logging import get_logger

logger = get_logger(__name__)


def get_container(request: Request) -> Container:
    """Fetch the container from the application state."""
    return cast(Container, request.app.state.container)


def get_settings(
    container: Annotated[Container, Depends(get_container)],
) -> AppSettings:
    """Dependency provider for AppSettings."""
    return container.settings


def get_probe_registry(
    container: Annotated[Container, Depends(get_container)],
) -> ProbeRegistry:
    """Dependency provider for ProbeRegistry."""
    return container.probe_registry


async def get_db_session(
    container: Annotated[Container, Depends(get_container)],
) -> AsyncIterator[AsyncSession]:
    """Dependency provider for AsyncSession.

    Opens a session from the container's session_factory and ensures it is
    closed after the request.
    """
    if container.session_factory is None:
        logger.error("session_factory_missing")
        raise RuntimeError("session_factory not initialized")  # noqa: TRY003

    async with container.session_factory() as session:
        yield session
