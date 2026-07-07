from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import persistence
from app.auth.domain import (
    AccessToken,
    AuthenticatedUser,
    Credentials,
    InvalidCredentialsError,
    RefreshReuseDetectedError,
    RefreshToken,
    UserAuthRecord,
)
from app.auth.ports import PasswordHasher, TokenSigner
from app.observability.logging import get_logger
from app.shared.clock import Clock
from app.shared.errors import AuthenticationError, ConflictError
from app.shared.types import TenantId, UserId

logger = get_logger(__name__)


class AuthService:
    """Orchestrates authentication and user registration."""

    def __init__(  # noqa: PLR0913  # Required for dependency injection
        self,
        session: "AsyncSession",
        password_hasher: PasswordHasher,
        token_signer: TokenSigner,
        clock: Clock,
        *,
        access_token_expires_minutes: int = 15,
        refresh_token_expires_days: int = 7,
    ) -> None:
        """Initialize the service.

        Note: session is typed via TYPE_CHECKING to avoid SQLAlchemy dependency
        at runtime in this layer per architecture rules.
        """
        self._session = session
        self._password_hasher = password_hasher
        self._token_signer = token_signer
        self._clock = clock
        self._access_token_expires_minutes = access_token_expires_minutes
        self._refresh_token_expires_days = refresh_token_expires_days

    async def register(self, email: str, password: str) -> AuthenticatedUser:
        """Register a new user."""
        existing = await persistence.get_user_by_email(self._session, email)
        if existing:
            raise ConflictError(detail=f"User with email {email} already exists")

        user_id = uuid4()
        password_hash = self._password_hasher.hash(password)
        created_at = self._clock.now()

        user_record = await persistence.insert_user(
            self._session,
            id=user_id,
            email=email,
            password_hash=password_hash,
            created_at=created_at,
            tenant_id=None,  # Default to no tenant for now
            disabled=False,
        )

        return AuthenticatedUser(
            user_id=UserId(str(user_record.id)),
            tenant_id=TenantId(str(user_record.tenant_id))
            if user_record.tenant_id
            else TenantId(""),
            scopes=frozenset(["user"]),  # Default scope
        )

    async def login(self, creds: Credentials) -> tuple[AccessToken, RefreshToken]:
        """Authenticate a user and issue tokens."""
        user = await persistence.get_user_by_email(self._session, creds.username)
        if not user or user.disabled:
            raise InvalidCredentialsError()

        if not self._password_hasher.verify(creds.password, user.password_hash):
            raise InvalidCredentialsError()

        return await self._issue_tokens(user)

    async def refresh(self, refresh_token_string: str) -> tuple[AccessToken, RefreshToken]:
        """Rotate a refresh token."""
        try:
            claims = self._token_signer.verify(refresh_token_string)
        except AuthenticationError as e:
            logger.warning("refresh_token_invalid", error=str(e))
            raise InvalidCredentialsError("Invalid refresh token") from e  # noqa: TRY003
        except Exception:
            logger.exception("refresh_token_unexpected_error")
            raise

        if claims.get("typ") != "refresh":
            raise InvalidCredentialsError("Invalid token type")  # noqa: TRY003

        token_id_str = claims.get("jti")
        if not token_id_str:
            raise InvalidCredentialsError("Invalid refresh token claims")  # noqa: TRY003

        token_id = UUID(token_id_str)
        token_record = await persistence.get_refresh_token_by_id(self._session, token_id)

        if not token_record:
            raise InvalidCredentialsError("Refresh token not found")  # noqa: TRY003

        if not self._password_hasher.verify(refresh_token_string, token_record.hash):
            raise InvalidCredentialsError("Invalid refresh token hash")  # noqa: TRY003

        if token_record.revoked_at and token_record.replaced_by:
            # Reuse detected!
            await persistence.revoke_refresh_token_family(
                self._session,
                family_id=token_record.family_id,
                revoked_at=self._clock.now(),
            )
            logger.error(
                "refresh_token_reuse_detected",
                user_id=token_record.user_id,
                family_id=token_record.family_id,
                token_id=token_record.id,
            )
            raise RefreshReuseDetectedError()

        if token_record.revoked_at:
            # Already revoked (e.g. via logout) but not replaced
            raise InvalidCredentialsError("Refresh token revoked")  # noqa: TRY003

        if token_record.expires_at < self._clock.now():
            raise InvalidCredentialsError("Refresh token expired")  # noqa: TRY003

        user = await persistence.get_user_by_id(self._session, token_record.user_id)
        if not user or user.disabled:
            raise InvalidCredentialsError()

        # Mark old token as replaced
        new_token_id = uuid4()
        now = self._clock.now()

        # T-907A: Insert the new refresh token before updating the old token's
        # replaced_by FK to satisfy the DB constraint.
        tokens = await self._issue_tokens(
            user, family_id=token_record.family_id, token_id=new_token_id
        )

        await persistence.mark_refresh_token_replaced(
            self._session,
            token_id=token_record.id,
            replaced_by=new_token_id,
            revoked_at=now,
        )

        return tokens

    async def logout(self, refresh_token_string: str) -> None:
        """Revoke a refresh token."""
        try:
            claims = self._token_signer.verify(refresh_token_string)
        except AuthenticationError as e:
            logger.warning("logout.invalid_token", error=str(e))
            return
        except Exception:
            logger.exception("logout.unexpected_error")
            raise

        if claims.get("typ") != "refresh":
            logger.warning("logout.invalid_token_type")
            return

        token_id_str = claims.get("jti")
        if not token_id_str:
            logger.warning("logout.missing_jti")
            return

        token_id = UUID(token_id_str)
        await persistence.revoke_refresh_token(
            self._session,
            token_id=token_id,
            revoked_at=self._clock.now(),
        )

    async def _issue_tokens(
        self,
        user: UserAuthRecord,
        family_id: UUID | None = None,
        token_id: UUID | None = None,
    ) -> tuple[AccessToken, RefreshToken]:
        now = self._clock.now()
        access_expires = now + timedelta(minutes=self._access_token_expires_minutes)
        refresh_expires = now + timedelta(days=self._refresh_token_expires_days)

        if family_id is None:
            family_id = uuid4()
        if token_id is None:
            token_id = uuid4()

        access_token_str = self._token_signer.sign(
            {
                "sub": str(user.id),
                "tenant_id": str(user.tenant_id) if user.tenant_id else None,
                "typ": "access",
                "active": not user.disabled,
                "exp": int(access_expires.timestamp()),
                "iat": int(now.timestamp()),
                "scopes": ["user"],
            }
        )

        refresh_token_str = self._token_signer.sign(
            {
                "sub": str(user.id),
                "jti": str(token_id),
                "typ": "refresh",
                "exp": int(refresh_expires.timestamp()),
                "iat": int(now.timestamp()),
            }
        )

        # Storing the hash of the refresh token
        refresh_token_hash = self._password_hasher.hash(refresh_token_str)

        await persistence.insert_refresh_token(
            self._session,
            id=token_id,
            user_id=user.id,
            family_id=family_id,
            hash=refresh_token_hash,
            issued_at=now,
            expires_at=refresh_expires,
            revoked_at=None,
            replaced_by=None,
        )

        return (
            AccessToken(token=access_token_str, expires_at=access_expires),
            RefreshToken(token=refresh_token_str, expires_at=refresh_expires),
        )
