# ruff: noqa: S101, S105, S106, PLR2004
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from app.auth.domain import (
    AccessToken,
    AuthenticatedUser,
    Credentials,
    InvalidCredentialsError,
    RefreshReuseDetectedError,
    RefreshToken,
)
from app.shared.types import TenantId, UserId


@pytest.mark.unit
def test_credentials_is_frozen() -> None:
    c = Credentials(username="user", password="password")
    with pytest.raises(FrozenInstanceError):
        c.username = "new"  # type: ignore[misc]


@pytest.mark.unit
def test_authenticated_user_is_frozen() -> None:
    u = AuthenticatedUser(
        user_id=UserId("user-1"),
        email="test@example.com",
        tenant_id=TenantId("tenant-1"),
        scopes=frozenset(["read"]),
    )
    with pytest.raises(FrozenInstanceError):
        u.user_id = UserId("user-2")  # type: ignore[misc]


@pytest.mark.unit
def test_access_token_is_frozen() -> None:
    t = AccessToken(token="secret", expires_at=datetime.now(UTC))
    with pytest.raises(FrozenInstanceError):
        t.token = "new"  # type: ignore[misc]


@pytest.mark.unit
def test_refresh_token_is_frozen() -> None:
    t = RefreshToken(token="secret", expires_at=datetime.now(UTC))
    with pytest.raises(FrozenInstanceError):
        t.token = "new"  # type: ignore[misc]


@pytest.mark.unit
def test_refresh_reuse_detected_error_code() -> None:
    err = RefreshReuseDetectedError()
    assert err.code == "refresh-token-reuse"
    assert err.status == 401


@pytest.mark.unit
def test_invalid_credentials_error_code() -> None:
    err = InvalidCredentialsError()
    assert err.code == "invalid-credentials"
    assert err.status == 401


@pytest.mark.unit
def test_domain_reprs_mask_secrets() -> None:
    c = Credentials(username="user", password="secret-password")
    assert "secret-password" not in repr(c)
    assert "***" in repr(c)

    now = datetime.now(UTC)
    at = AccessToken(token="secret-access", expires_at=now)
    assert "secret-access" not in repr(at)
    assert "***" in repr(at)

    rt = RefreshToken(token="secret-refresh", expires_at=now)
    assert "secret-refresh" not in repr(rt)
    assert "***" in repr(rt)
