# ruff: noqa: S101
from uuid import uuid4

import pytest

from app.auth.domain import AuthenticatedUser
from app.auth.policies import require_active_user, require_authenticated
from app.shared.errors import AuthenticationError
from app.shared.types import TenantId, UserId


@pytest.fixture
def auth_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=UserId(str(uuid4())),
        email="test@example.com",
        tenant_id=TenantId(str(uuid4())),
        scopes=frozenset(["user"]),
    )


@pytest.mark.unit
def test_require_authenticated_success(auth_user: AuthenticatedUser) -> None:
    assert require_authenticated(auth_user) == auth_user


@pytest.mark.unit
def test_require_authenticated_failure() -> None:
    with pytest.raises(AuthenticationError):
        require_authenticated(None)


@pytest.mark.unit
def test_require_active_user_success(auth_user: AuthenticatedUser) -> None:
    assert require_active_user(auth_user, active=True) == auth_user


@pytest.mark.unit
def test_require_active_user_failure(auth_user: AuthenticatedUser) -> None:
    with pytest.raises(AuthenticationError) as excinfo:
        require_active_user(auth_user, active=False)
    assert excinfo.value.detail == "User is disabled"


@pytest.mark.unit
def test_require_active_user_fail_closed(auth_user: AuthenticatedUser) -> None:
    # Missing 'active' claim (None) should fail
    with pytest.raises(AuthenticationError) as excinfo:
        require_active_user(auth_user, active=None)
    assert excinfo.value.detail == "User is disabled"
