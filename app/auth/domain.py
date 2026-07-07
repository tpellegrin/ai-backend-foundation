from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.shared.errors import AppError
from app.shared.types import TenantId, UserId


@dataclass(frozen=True, slots=True)
class UserAuthRecord:
    id: UUID
    email: str
    password_hash: str
    created_at: datetime
    tenant_id: UUID | None
    disabled: bool


@dataclass(frozen=True, slots=True)
class RefreshTokenRecord:
    id: UUID
    user_id: UUID
    family_id: UUID
    hash: str
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    replaced_by: UUID | None


@dataclass(frozen=True)
class Credentials:
    """Login credentials."""

    username: str
    password: str

    def __repr__(self) -> str:
        return f"Credentials(username={self.username!r}, password='***')"


@dataclass(frozen=True)
class AuthenticatedUser:
    """A user that has been successfully authenticated."""

    user_id: UserId
    email: str
    tenant_id: TenantId
    scopes: frozenset[str]

    def __post_init__(self) -> None:
        if not self.email:
            raise ValueError("email must not be empty")  # noqa: TRY003


@dataclass(frozen=True)
class AccessToken:
    """An issued access token."""

    token: str
    expires_at: datetime

    def __repr__(self) -> str:
        return f"AccessToken(token='***', expires_at={self.expires_at!r})"


@dataclass(frozen=True)
class RefreshToken:
    """An issued refresh token."""

    token: str
    expires_at: datetime

    def __repr__(self) -> str:
        return f"RefreshToken(token='***', expires_at={self.expires_at!r})"


class InvalidCredentialsError(AppError):
    """Raised when provided credentials do not match."""

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(
            code="invalid-credentials",
            title="Invalid credentials",
            status=401,
            detail=detail,
        )


class RefreshReuseDetectedError(AppError):
    """Raised when a refresh token is reused, indicating potential theft."""

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(
            code="refresh-token-reuse",
            title="Refresh token reuse detected",
            status=401,
            detail=detail,
        )
