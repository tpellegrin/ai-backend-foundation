from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette import status

from app.main.app_factory import create_app
from app.shared.errors import NotFoundError
from app.shared.problem_details import MEDIA_TYPE


@pytest.fixture
def fastapi_app() -> FastAPI:
    # Use the real create_app factory as required by T-507
    app = create_app()

    # T-507 requirement: register test-only routes directly on the app instance
    @app.get("/__test__/app-error")
    async def _raise_app_error() -> None:
        raise NotFoundError(detail="Resource X not found")

    @app.get("/__test__/unhandled")
    async def _raise_unhandled() -> None:
        raise RuntimeError("boom")

    return app


@pytest.fixture
def client(fastapi_app: FastAPI) -> TestClient:
    return TestClient(fastapi_app, raise_server_exceptions=False)


@pytest.mark.api
def test_app_error_returns_problem_details(client: TestClient) -> None:
    request_id = str(uuid.uuid4())
    response = client.get("/__test__/app-error", headers={"X-Request-ID": request_id})

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.headers["Content-Type"] == MEDIA_TYPE
    assert response.headers["X-Request-ID"] == request_id

    data = response.json()
    err = NotFoundError()
    assert data["code"] == err.code
    assert data["title"] == err.title
    assert data["status"] == status.HTTP_404_NOT_FOUND
    assert data["detail"] == "Resource X not found"
    assert data["request_id"] == request_id
    assert data["type"] == "about:blank"


@pytest.mark.api
def test_unhandled_exception_returns_sanitized_500(client: TestClient) -> None:
    request_id = str(uuid.uuid4())
    response = client.get("/__test__/unhandled", headers={"X-Request-ID": request_id})

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.headers["Content-Type"] == MEDIA_TYPE
    assert response.headers["X-Request-ID"] == request_id

    data = response.json()
    assert data["code"] == "internal-error"
    assert data["title"] == "Internal server error"
    assert data["status"] == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert data["detail"] == "An unexpected error occurred."
    assert data["request_id"] == request_id
    assert data["type"] == "about:blank"

    # Sanity check: internal details should not leak
    body = response.text
    assert "RuntimeError" not in body
    assert "boom" not in body
    assert "Traceback" not in body


@pytest.mark.api
def test_error_response_generates_x_request_id_if_absent(client: TestClient) -> None:
    response = client.get("/__test__/app-error")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "X-Request-ID" in response.headers
    request_id = response.headers["X-Request-ID"]
    uuid.UUID(request_id)

    data = response.json()
    assert data["request_id"] == request_id
