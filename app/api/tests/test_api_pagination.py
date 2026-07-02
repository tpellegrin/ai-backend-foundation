# ruff: noqa: S101, PLR2004
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.errors import register_exception_handlers
from app.api.pagination import get_cursor_params
from app.shared.pagination import CursorParams


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/test-pagination")
    async def test_pagination(
        params: Annotated[CursorParams, Depends(get_cursor_params)],
    ) -> CursorParams:
        return params

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.api
def test_pagination_defaults(client: TestClient) -> None:
    response = client.get("/test-pagination")
    assert response.status_code == 200
    data = response.json()
    assert data["cursor"] is None
    assert data["limit"] == 20


@pytest.mark.api
def test_pagination_custom_values(client: TestClient) -> None:
    response = client.get("/test-pagination?cursor=abc&limit=50")
    assert response.status_code == 200
    data = response.json()
    assert data["cursor"] == "abc"
    assert data["limit"] == 50


@pytest.mark.api
def test_pagination_limit_too_low(client: TestClient) -> None:
    response = client.get("/test-pagination?limit=0")
    assert response.status_code == 422
    data = response.json()
    assert data["code"] == "validation-error"
    assert "at least 1" in data["detail"]


@pytest.mark.api
def test_pagination_limit_too_high(client: TestClient) -> None:
    response = client.get("/test-pagination?limit=101")
    assert response.status_code == 422
    data = response.json()
    assert data["code"] == "validation-error"
    assert "cannot exceed 100" in data["detail"]


@pytest.mark.api
def test_pagination_invalid_cursor(client: TestClient) -> None:
    response = client.get("/test-pagination?cursor=")
    assert response.status_code == 422
    data = response.json()
    assert data["code"] == "validation-error"
    assert "Cursor cannot be empty" in data["detail"]
