# ruff: noqa: S101, PLR2004
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from app.api.errors import register_exception_handlers
from app.observability import request_id_var
from app.shared.errors import AppError


class MockAppError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="mock-error",
            title="Mock error title",
            status=400,
            detail="Mock error detail",
            extras={"extra_key": "extra_value"},
        )


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/app-error")
    async def raise_app_error() -> None:
        raise MockAppError()

    @app.get("/validation-error")
    async def raise_validation_error() -> None:
        raise RequestValidationError(
            errors=[
                {"loc": ("body", "name"), "msg": "field required", "type": "value_error.missing"}
            ]
        )

    @app.get("/http-error")
    async def raise_http_error() -> None:
        raise HTTPException(status_code=403, detail="Forbidden detail")

    @app.get("/unhandled-error")
    async def raise_unhandled_error() -> None:
        raise ValueError("unhandled")

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.api
def test_app_error_mapping(client: TestClient) -> None:
    token = request_id_var.set("test-request-id")
    try:
        response = client.get("/app-error")

        assert response.status_code == 400
        assert response.headers["Content-Type"] == "application/problem+json"
        assert response.headers["X-Request-ID"] == "test-request-id"

        data = response.json()
        assert data["code"] == "mock-error"
        assert data["title"] == "Mock error title"
        assert data["detail"] == "Mock error detail"
        assert data["extra_key"] == "extra_value"
        assert data["request_id"] == "test-request-id"
    finally:
        request_id_var.reset(token)


@pytest.mark.api
def test_validation_error_mapping(client: TestClient) -> None:
    token = request_id_var.set("test-request-id")
    try:
        response = client.get("/validation-error")

        assert response.status_code == 422
        assert response.headers["Content-Type"] == "application/problem+json"
        assert response.headers["X-Request-ID"] == "test-request-id"

        data = response.json()
        assert data["code"] == "validation-error"
        assert data["title"] == "Validation error"
        assert "errors" in data
        assert data["request_id"] == "test-request-id"
    finally:
        request_id_var.reset(token)


@pytest.mark.api
def test_http_error_mapping(client: TestClient) -> None:
    token = request_id_var.set("test-request-id")
    try:
        response = client.get("/http-error")

        assert response.status_code == 403
        assert response.headers["Content-Type"] == "application/problem+json"
        assert response.headers["X-Request-ID"] == "test-request-id"

        data = response.json()
        assert data["code"] == "http-403"
        assert data["title"] == "Forbidden"
        assert data["detail"] == "Forbidden detail"
        assert data["request_id"] == "test-request-id"
    finally:
        request_id_var.reset(token)


@pytest.mark.api
def test_unhandled_error_mapping(client: TestClient) -> None:
    token = request_id_var.set("test-request-id")
    try:
        response = client.get("/unhandled-error")

        assert response.status_code == 500
        assert response.headers["Content-Type"] == "application/problem+json"
        assert response.headers["X-Request-ID"] == "test-request-id"

        data = response.json()
        assert data["code"] == "internal-error"
        assert data["title"] == "Internal server error"
        assert data["request_id"] == "test-request-id"
    finally:
        request_id_var.reset(token)
