# ruff: noqa: S101
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.deps import get_auth_service, get_current_user
from app.auth.domain import AuthenticatedUser
from app.shared.errors import AuthenticationError


@pytest.fixture
def mock_container() -> MagicMock:
    container = MagicMock()
    container.password_hasher = MagicMock()
    container.token_signer = MagicMock()
    container.settings = MagicMock()
    container.settings.jwt.access_ttl_seconds = 900
    container.settings.jwt.refresh_ttl_seconds = 60 * 60 * 24 * 7
    return container


@pytest.fixture
def mock_request(mock_container: MagicMock) -> MagicMock:
    request = MagicMock(spec=Request)
    request.app.state.container = mock_container
    return request


@pytest.mark.unit
async def test_get_auth_service(mock_request: MagicMock, mock_container: MagicMock) -> None:
    session = AsyncMock()
    service = await get_auth_service(mock_request, session)
    assert service._session == session
    assert service._password_hasher == mock_container.password_hasher
    assert service._token_signer == mock_container.token_signer
    assert service._access_token_expires_minutes == 15  # noqa: PLR2004
    assert service._refresh_token_expires_days == 7  # noqa: PLR2004


@pytest.mark.unit
async def test_get_current_user_happy_path(
    mock_request: MagicMock, mock_container: MagicMock
) -> None:
    user_id = uuid4()
    tenant_id = uuid4()
    mock_container.token_signer.verify.return_value = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "typ": "access",
        "active": True,
        "scopes": ["user"],
    }

    auth_creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-token")

    user = await get_current_user(mock_request, auth_creds)

    assert isinstance(user, AuthenticatedUser)
    assert user.user_id == str(user_id)
    assert user.tenant_id == str(tenant_id)
    assert "user" in user.scopes


@pytest.mark.unit
async def test_get_current_user_invalid_token(
    mock_request: MagicMock, mock_container: MagicMock
) -> None:
    mock_container.token_signer.verify.side_effect = Exception("Invalid token")

    auth_creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid-token")

    with pytest.raises(AuthenticationError):
        await get_current_user(mock_request, auth_creds)


@pytest.mark.unit
async def test_get_current_user_disabled_user(
    mock_request: MagicMock, mock_container: MagicMock
) -> None:
    mock_container.token_signer.verify.return_value = {
        "sub": str(uuid4()),
        "typ": "access",
        "active": False,
        "scopes": ["user"],
    }

    auth_creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-token")

    with pytest.raises(AuthenticationError) as excinfo:
        await get_current_user(mock_request, auth_creds)
    assert excinfo.value.detail == "User is disabled"


@pytest.mark.unit
async def test_get_current_user_missing_active_claim(
    mock_request: MagicMock, mock_container: MagicMock
) -> None:
    mock_container.token_signer.verify.return_value = {
        "sub": str(uuid4()),
        "typ": "access",
        # "active" is missing
        "scopes": ["user"],
    }

    auth_creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-token")

    with pytest.raises(AuthenticationError) as excinfo:
        await get_current_user(mock_request, auth_creds)
    assert excinfo.value.detail == "User is disabled"


@pytest.mark.unit
async def test_get_current_user_wrong_token_type(
    mock_request: MagicMock, mock_container: MagicMock
) -> None:
    mock_container.token_signer.verify.return_value = {
        "sub": str(uuid4()),
        "typ": "refresh",
        "active": True,
        "scopes": ["user"],
    }

    auth_creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-token")

    with pytest.raises(AuthenticationError) as excinfo:
        await get_current_user(mock_request, auth_creds)
    assert excinfo.value.detail == "Invalid token type"


@pytest.mark.unit
async def test_get_current_user_no_creds(
    mock_request: MagicMock, mock_container: MagicMock
) -> None:
    with pytest.raises(AuthenticationError):
        await get_current_user(mock_request, None)
