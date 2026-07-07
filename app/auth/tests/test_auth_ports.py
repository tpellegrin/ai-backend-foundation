from collections.abc import Mapping
from typing import Any

import pytest

from app.auth.domain import AuthenticatedUser, Credentials
from app.auth.ports import IdentityProvider, PasswordHasher, TokenSigner
from app.shared.types import TenantId, UserId

# ruff: noqa: S101, S106


class FakePasswordHasher:
    """Fake implementation of PasswordHasher."""

    def hash(self, plaintext: str) -> str:
        return f"hashed_{plaintext}"

    def verify(self, hash: str, plaintext: str) -> bool:
        return hash == f"hashed_{plaintext}"


class FakeTokenSigner:
    """Fake implementation of TokenSigner."""

    def sign(self, claims: Mapping[str, Any]) -> str:
        return "signed_token"

    def verify(self, token: str) -> Mapping[str, Any]:
        return {"sub": "user_123"}


class FakeIdentityProvider:
    """Fake implementation of IdentityProvider."""

    async def authenticate(self, creds: Credentials) -> AuthenticatedUser:
        return AuthenticatedUser(
            user_id=UserId("user_123"),
            tenant_id=TenantId("tenant_456"),
            scopes=frozenset(["read", "write"]),
        )


@pytest.mark.unit
def test_password_hasher_protocol() -> None:
    hasher: PasswordHasher = FakePasswordHasher()
    assert hasher.hash("password") == "hashed_password"
    assert hasher.verify("hashed_password", "password") is True
    assert isinstance(hasher, PasswordHasher)


@pytest.mark.unit
def test_token_signer_protocol() -> None:
    signer: TokenSigner = FakeTokenSigner()
    assert signer.sign({"sub": "user_123"}) == "signed_token"
    assert signer.verify("signed_token") == {"sub": "user_123"}
    assert isinstance(signer, TokenSigner)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_identity_provider_protocol() -> None:
    provider: IdentityProvider = FakeIdentityProvider()
    creds = Credentials(username="testuser", password="password")
    user = await provider.authenticate(creds)
    assert user.user_id == "user_123"
    assert user.tenant_id == "tenant_456"
    assert "read" in user.scopes
    assert isinstance(provider, IdentityProvider)
