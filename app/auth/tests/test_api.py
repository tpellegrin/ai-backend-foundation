# ruff: noqa: S101, PLR2004, S105, S106
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import register_exception_handlers
from app.auth.api import router
from app.auth.deps import get_auth_service, get_clock
from app.auth.domain import (
    AccessToken,
    AuthenticatedUser,
    InvalidCredentialsError,
    RefreshToken,
)
from app.observability.correlation import CorrelationMiddleware
from app.shared.clock import FixedClock
from app.shared.types import TenantId, UserId

FIXED_NOW = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def mock_auth_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def fixed_clock() -> FixedClock:
    return FixedClock(FIXED_NOW)


@pytest.fixture
def app(mock_auth_service: AsyncMock, fixed_clock: FixedClock) -> FastAPI:
    app = FastAPI()
    app.add_middleware(CorrelationMiddleware)
    register_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_auth_service] = lambda: mock_auth_service
    app.dependency_overrides[get_clock] = lambda: fixed_clock
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.api
def test_register_happy_path(client: TestClient, mock_auth_service: AsyncMock) -> None:
    user_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    mock_auth_service.register.return_value = AuthenticatedUser(
        user_id=UserId(user_id),
        tenant_id=TenantId(tenant_id),
        scopes=frozenset(["user"]),
    )

    response = client.post(
        "/register",
        json={"email": "test@example.com", "password": "password123"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == user_id
    assert data["tenant_id"] == tenant_id
    assert "X-Request-ID" in response.headers


@pytest.mark.api
def test_login_happy_path(client: TestClient, mock_auth_service: AsyncMock) -> None:
    access_expires_at = FIXED_NOW + timedelta(minutes=15)
    mock_auth_service.login.return_value = (
        AccessToken(token="access-token", expires_at=access_expires_at),
        RefreshToken(token="refresh-token", expires_at=FIXED_NOW + timedelta(days=7)),
    )

    response = client.post(
        "/login",
        json={"username": "test@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"] == "access-token"
    assert data["refresh_token"] == "refresh-token"
    assert data["token_type"] == "Bearer"
    assert data["expires_in"] == 900
    assert "X-Request-ID" in response.headers


@pytest.mark.api
def test_login_invalid_credentials(client: TestClient, mock_auth_service: AsyncMock) -> None:
    mock_auth_service.login.side_effect = InvalidCredentialsError("Invalid email or password")

    response = client.post(
        "/login",
        json={"username": "test@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.headers["Content-Type"] == "application/problem+json"
    data = response.json()
    assert data["code"] == "invalid-credentials"
    assert data["title"] == "Invalid credentials"
    assert "type" in data
    assert "status" in data
    assert "detail" in data
    assert "request_id" in data
    assert "X-Request-ID" in response.headers
    assert data["request_id"] == response.headers["X-Request-ID"]


@pytest.mark.api
def test_refresh_happy_path(client: TestClient, mock_auth_service: AsyncMock) -> None:
    access_expires_at = FIXED_NOW + timedelta(minutes=15)
    mock_auth_service.refresh.return_value = (
        AccessToken(token="new-access-token", expires_at=access_expires_at),
        RefreshToken(token="new-refresh-token", expires_at=FIXED_NOW + timedelta(days=7)),
    )

    response = client.post(
        "/refresh",
        json={"refresh_token": "old-refresh-token"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"] == "new-access-token"
    assert data["refresh_token"] == "new-refresh-token"
    assert data["expires_in"] == 900
    assert "X-Request-ID" in response.headers


@pytest.mark.api
def test_refresh_invalid_token(client: TestClient, mock_auth_service: AsyncMock) -> None:
    mock_auth_service.refresh.side_effect = InvalidCredentialsError("Invalid refresh token")

    response = client.post(
        "/refresh",
        json={"refresh_token": "invalid-token"},
    )

    assert response.status_code == 401
    data = response.json()
    assert data["code"] == "invalid-credentials"
    assert "X-Request-ID" in response.headers


@pytest.mark.api
def test_logout_happy_path(client: TestClient, mock_auth_service: AsyncMock) -> None:
    response = client.post(
        "/logout",
        json={"refresh_token": "refresh-token-to-revoke"},
    )

    assert response.status_code == 204
    mock_auth_service.logout.assert_called_once_with("refresh-token-to-revoke")
    assert "X-Request-ID" in response.headers


@pytest.mark.api
def test_login_invalid_payload(client: TestClient) -> None:
    response = client.post(
        "/login",
        json={"username": "test@example.com"},  # Missing password
    )

    assert response.status_code == 422
    assert response.headers["Content-Type"] == "application/problem+json"
    data = response.json()
    assert data["code"] == "validation-error"
    assert "type" in data
    assert "title" in data
    assert "status" in data
    assert "detail" in data
    assert "request_id" in data
    assert "X-Request-ID" in response.headers
    assert data["request_id"] == response.headers["X-Request-ID"]
