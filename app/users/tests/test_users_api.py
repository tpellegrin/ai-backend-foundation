# ruff: noqa: S101, PLR2004
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import register_exception_handlers
from app.auth.deps import get_current_user
from app.auth.domain import AuthenticatedUser
from app.observability.correlation import CorrelationMiddleware
from app.shared.types import TenantId, UserId
from app.users.api import router
from app.users.deps import get_user_service
from app.users.domain import UserProfile
from app.users.service import UserService


@pytest.fixture
def mock_user_service() -> MagicMock:
    return MagicMock(spec=UserService)


@pytest.fixture
def app(mock_user_service: MagicMock) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.add_middleware(CorrelationMiddleware)
    app.include_router(router)

    # Override dependencies
    app.dependency_overrides[get_user_service] = lambda: mock_user_service

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.unit
def test_get_me_unauthenticated(client: TestClient) -> None:
    request_id = str(uuid.uuid4())
    response = client.get("/me", headers={"X-Request-ID": request_id})

    assert response.status_code == 401
    assert response.headers["X-Request-ID"] == request_id
    assert response.headers["Content-Type"] == "application/problem+json"

    data = response.json()
    assert data["status"] == 401
    assert data["code"] == "authentication-error"
    assert data["request_id"] == request_id
    assert "type" in data
    assert "title" in data
    assert "detail" in data


@pytest.mark.unit
def test_get_me_authenticated_success(
    client: TestClient, mock_user_service: MagicMock, app: FastAPI
) -> None:
    user_id = uuid.uuid4()
    email = "test@example.com"
    request_id = str(uuid.uuid4())

    mock_user = AuthenticatedUser(
        user_id=UserId(str(user_id)),
        email=email,
        tenant_id=TenantId(""),
        scopes=frozenset(["user"]),
    )

    app.dependency_overrides[get_current_user] = lambda: mock_user

    now = datetime.now(UTC)
    profile = UserProfile(
        id=user_id,
        email=email,
        created_at=now,
        updated_at=now,
    )
    mock_user_service.get_or_create_profile = AsyncMock(return_value=profile)

    response = client.get("/me", headers={"X-Request-ID": request_id})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id
    data = response.json()
    assert data["id"] == str(user_id)
    assert data["email"] == email

    mock_user_service.get_or_create_profile.assert_called_once_with(
        user_id=user_id,
        email=email,
    )
