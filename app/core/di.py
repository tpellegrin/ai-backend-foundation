from typing import Annotated, cast

from fastapi import Depends, Request

from app.core.config.settings import AppSettings
from app.core.container import Container
from app.observability.health import ProbeRegistry


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
