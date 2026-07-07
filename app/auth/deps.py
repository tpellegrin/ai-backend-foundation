from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.domain import AuthenticatedUser
from app.auth.policies import require_active_user, require_authenticated
from app.auth.service import AuthService
from app.observability.logging import get_logger
from app.shared.errors import AppError, AuthenticationError
from app.shared.types import TenantId, UserId

logger = get_logger(__name__)

security = HTTPBearer(auto_error=False)


async def _get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Local provider for AsyncSession to avoid app.core import."""
    container: Any = request.app.state.container
    if not hasattr(container, "session_factory") or container.session_factory is None:
        logger.error("session_factory_missing")
        raise AppError(
            code="wiring-error",
            title="Session factory not initialized",
            status=500,
            detail="session_factory not initialized in container",
        )
    async with container.session_factory() as session:
        yield session


async def get_auth_service(
    request: Request,
    session: Annotated[AsyncSession, Depends(_get_db_session)],
) -> AuthService:
    """Dependency provider for AuthService."""
    container: Any = request.app.state.container
    settings = container.settings

    password_hasher = container.password_hasher
    if password_hasher is None:
        logger.error("password_hasher_missing")
        raise AppError(
            code="wiring-error",
            title="PasswordHasher not wired",
            status=500,
            detail="PasswordHasher not wired in container",
        )

    token_signer = container.token_signer
    if token_signer is None:
        logger.error("token_signer_missing")
        raise AppError(
            code="wiring-error",
            title="TokenSigner not wired",
            status=500,
            detail="TokenSigner not wired in container",
        )

    return AuthService(
        session=session,
        password_hasher=password_hasher,
        token_signer=token_signer,
        access_token_expires_minutes=settings.jwt.access_ttl_seconds // 60,
        refresh_token_expires_days=settings.jwt.refresh_ttl_seconds // (60 * 60 * 24),
    )


async def get_current_user(
    request: Request,
    auth_creds: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> AuthenticatedUser:
    """Fetch the current authenticated user from the request."""
    if not auth_creds:
        # Policy will raise AuthenticationError
        return require_authenticated(None)

    container: Any = request.app.state.container
    token_signer = container.token_signer
    if token_signer is None:
        logger.error("token_signer_missing")
        raise AppError(
            code="wiring-error",
            title="TokenSigner not wired",
            status=500,
            detail="TokenSigner not wired in container",
        )

    token = auth_creds.credentials
    try:
        claims = token_signer.verify(token)
    except AuthenticationError:
        raise
    except Exception as e:
        logger.exception("token_verification_error")
        raise AuthenticationError("Invalid token") from e  # noqa: TRY003

    if claims.get("typ") != "access":
        raise AuthenticationError("Invalid token type")  # noqa: TRY003

    user_id_str = claims.get("sub")
    if not user_id_str:
        raise AuthenticationError("Invalid token claims: missing sub")  # noqa: TRY003

    tenant_id_str = claims.get("tenant_id")
    scopes = claims.get("scopes", [])

    user = AuthenticatedUser(
        user_id=UserId(str(UUID(user_id_str))),
        tenant_id=TenantId(str(UUID(tenant_id_str))) if tenant_id_str else TenantId(""),
        scopes=frozenset(scopes),
    )

    return require_active_user(
        require_authenticated(user),
        active=claims.get("active"),
    )
