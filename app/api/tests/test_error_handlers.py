# ruff: noqa: S101, PLR2004
import uuid

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from app.api.errors import register_exception_handlers
from app.observability import request_id_var
from app.observability.correlation import CorrelationMiddleware
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
        raise ValueError("secret-stacktrace-marker-should-not-leak")

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
def test_http_exception_is_not_normalized_to_problem_details(client: TestClient) -> None:
    """
    HTTPException raised from anywhere below `api.py` must not be silently
    mapped into RFC 9457 Problem Details. T-501 registers exactly three
    handlers (AppError, RequestValidationError, and the fallback Exception);
    HTTPException is intentionally not in that list. It therefore falls
    through to FastAPI/Starlette's default handler, which surfaces the
    misuse (`{"detail": ...}` in `application/json`) instead of hiding it
    behind a canonical error envelope. Domain/service code must raise
    :class:`AppError` subclasses, per AGENTS.md §12.
    """
    token = request_id_var.set("test-request-id")
    try:
        response = client.get("/http-error")

        # The default Starlette handler runs — not our Problem Details path.
        assert response.headers["Content-Type"] != "application/problem+json"

        data = response.json()
        # No Problem Details shape.
        assert "code" not in data
        assert "title" not in data
        assert "request_id" not in data
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

        # No exc.args, stack trace, or ValueError repr must leak into the body.
        body = response.text
        assert "secret-stacktrace-marker-should-not-leak" not in body
        assert "ValueError" not in body
        assert "Traceback" not in body
    finally:
        request_id_var.reset(token)


# --- Integration with CorrelationMiddleware -----------------------------------
#
# The fallback ``Exception`` handler is invoked by Starlette's
# ``ServerErrorMiddleware``, which wraps user middleware. That means it runs
# *outside* ``CorrelationMiddleware``'s contextvar scope: by the time the
# handler executes, ``request_id_var`` has already been reset in the
# middleware's ``finally`` block. These tests exercise the real middleware +
# handler stack to prove the sanitized 500 response still carries
# ``X-Request-ID`` (recovered from ``request.state.request_id``).


@pytest.fixture
def app_with_correlation() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CorrelationMiddleware)
    register_exception_handlers(app)

    @app.get("/unhandled-error")
    async def raise_unhandled_error() -> None:
        raise ValueError("secret-stacktrace-marker-should-not-leak")

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

    return app


@pytest.fixture
def correlated_client(app_with_correlation: FastAPI) -> TestClient:
    return TestClient(app_with_correlation, raise_server_exceptions=False)


@pytest.mark.api
def test_sanitized_500_echoes_inbound_request_id(correlated_client: TestClient) -> None:
    inbound = str(uuid.uuid4())
    response = correlated_client.get("/unhandled-error", headers={"X-Request-ID": inbound})

    assert response.status_code == 500
    assert response.headers["Content-Type"] == "application/problem+json"
    # The critical assertion: the sanitized 500 response carries X-Request-ID.
    assert response.headers["X-Request-ID"] == inbound

    data = response.json()
    assert data["code"] == "internal-error"
    assert data["request_id"] == inbound

    # And it must still be sanitized.
    body = response.text
    assert "secret-stacktrace-marker-should-not-leak" not in body
    assert "ValueError" not in body
    assert "Traceback" not in body


@pytest.mark.api
def test_sanitized_500_generates_request_id_when_absent(correlated_client: TestClient) -> None:
    response = correlated_client.get("/unhandled-error")

    assert response.status_code == 500
    assert "X-Request-ID" in response.headers
    generated = response.headers["X-Request-ID"]
    # Must be a valid UUID and match the body.
    uuid.UUID(generated)
    assert response.json()["request_id"] == generated


@pytest.mark.api
def test_sanitized_500_replaces_malformed_request_id(correlated_client: TestClient) -> None:
    response = correlated_client.get("/unhandled-error", headers={"X-Request-ID": "not-a-uuid"})

    assert response.status_code == 500
    assert "X-Request-ID" in response.headers
    emitted = response.headers["X-Request-ID"]
    assert emitted != "not-a-uuid"
    uuid.UUID(emitted)
    assert response.json()["request_id"] == emitted


@pytest.mark.api
def test_app_error_through_middleware_echoes_request_id(correlated_client: TestClient) -> None:
    inbound = str(uuid.uuid4())
    response = correlated_client.get("/app-error", headers={"X-Request-ID": inbound})

    assert response.status_code == 400
    assert response.headers["X-Request-ID"] == inbound
    assert response.json()["request_id"] == inbound


@pytest.mark.api
def test_validation_error_through_middleware_echoes_request_id(
    correlated_client: TestClient,
) -> None:
    inbound = str(uuid.uuid4())
    response = correlated_client.get("/validation-error", headers={"X-Request-ID": inbound})

    assert response.status_code == 422
    assert response.headers["X-Request-ID"] == inbound
    assert response.json()["request_id"] == inbound


@pytest.mark.api
def test_error_handler_generates_request_id_without_middleware(client: TestClient) -> None:
    """When the correlation middleware is not installed (e.g. isolated unit
    setups), the handler must still emit a valid ``X-Request-ID`` rather than
    dropping the header."""
    response = client.get("/unhandled-error")

    assert response.status_code == 500
    assert "X-Request-ID" in response.headers
    uuid.UUID(response.headers["X-Request-ID"])
