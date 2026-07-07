from collections.abc import AsyncIterator
from typing import Annotated, Protocol, cast, runtime_checkable

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.observability.logging import get_logger
from app.shared.clock import Clock
from app.users.service import UserService


@runtime_checkable
class _Container(Protocol):
    session_factory: async_sessionmaker[AsyncSession] | None
    clock: Clock | None


logger = get_logger(__name__)


async def _get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Local provider for AsyncSession to avoid app.core import."""
    container = cast(_Container, request.app.state.container)
    if not hasattr(container, "session_factory") or container.session_factory is None:
        logger.error("session_factory_missing")
        raise RuntimeError("session_factory not initialized in container")  # noqa: TRY003

    async with container.session_factory() as session:
        yield session


async def get_user_service(
    request: Request,
    session: Annotated[AsyncSession, Depends(_get_db_session)],
) -> UserService:
    """Dependency provider for UserService."""
    container = cast(_Container, request.app.state.container)
    clock = container.clock
    if clock is None:
        logger.error("clock_missing")
        raise RuntimeError("Clock not wired in container")  # noqa: TRY003

    return UserService(session=session, clock=clock)
