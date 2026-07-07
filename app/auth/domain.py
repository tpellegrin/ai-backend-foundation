from dataclasses import dataclass
from datetime import datetime

from app.shared.errors import AppError
from app.shared.types import TenantId, UserId


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
    tenant_id: TenantId
    scopes: frozenset[str]


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
