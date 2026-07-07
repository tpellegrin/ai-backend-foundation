from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from app.auth.domain import AuthenticatedUser, Credentials


@runtime_checkable
class PasswordHasher(Protocol):
    """Port for password hashing and verification."""

    def hash(self, password: str) -> str:
        """Hash a plaintext password."""
        ...

    def verify(self, password: str, password_hash: str) -> bool:
        """Verify a plaintext password against a hash."""
        ...

    def needs_rehash(self, password_hash: str) -> bool:
        """Check if the password hash needs to be re-hashed."""
        ...


@runtime_checkable
class TokenSigner(Protocol):
    """Port for signing and verifying tokens."""

    def sign(self, claims: Mapping[str, Any]) -> str:
        """Sign a set of claims into a token."""
        ...

    def verify(self, token: str) -> Mapping[str, Any]:
        """Verify a token and return the contained claims."""
        ...


@runtime_checkable
class IdentityProvider(Protocol):
    """Port for authenticating credentials against an identity store."""

    async def authenticate(self, creds: Credentials) -> AuthenticatedUser:
        """Authenticate credentials and return the authenticated user."""
        ...
