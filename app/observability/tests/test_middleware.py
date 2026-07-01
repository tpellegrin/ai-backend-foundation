# ruff: noqa: S101
import json
from uuid import uuid4

import pytest
from _pytest.capture import CaptureFixture
from starlette import status
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from app.observability.correlation import CorrelationMiddleware
from app.observability.logging import configure_logging
from app.observability.middleware import AccessLogMiddleware


@pytest.mark.unit
def test_access_log_middleware_emits_log(capsys: CaptureFixture[str]) -> None:
    # Configure logging for JSON output to capture it
    configure_logging(level="INFO", json=True)

    async def endpoint(request: Request) -> Response:
        return JSONResponse({"status": "ok"})

    app = Starlette(routes=[Route("/", endpoint)])
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(CorrelationMiddleware)

    client = TestClient(app)
    request_id = str(uuid4())
    response = client.get("/", headers={"X-Request-ID": request_id})

    assert response.status_code == status.HTTP_200_OK

    # Capture and verify log
    captured = capsys.readouterr()
    log_lines = captured.out.strip().split("\n")

    # We expect exactly one access_log event
    access_logs = [json.loads(line) for line in log_lines if line.strip()]
    access_log = next(log for log in access_logs if log.get("event") == "access_log")

    assert access_log["method"] == "GET"
    assert access_log["path"] == "/"
    assert access_log["status"] == status.HTTP_200_OK
    assert "duration_ms" in access_log
    assert access_log["request_id"] == request_id
    assert "user_id" in access_log
    assert access_log["user_id"] is None


@pytest.mark.unit
def test_access_log_middleware_with_user(capsys: CaptureFixture[str]) -> None:
    configure_logging(level="INFO", json=True)

    async def endpoint(request: Request) -> Response:
        # Simulate auth middleware setting user in scope
        request.scope["user"] = {"id": "user_123"}
        return JSONResponse({"status": "ok"})

    app = Starlette(routes=[Route("/", endpoint)])
    app.add_middleware(AccessLogMiddleware)

    client = TestClient(app)
    client.get("/")

    captured = capsys.readouterr()
    log_lines = captured.out.strip().split("\n")
    access_logs = [json.loads(line) for line in log_lines if line.strip()]
    access_log = next(log for log in access_logs if log.get("event") == "access_log")

    assert access_log["user_id"] == "user_123"


@pytest.mark.unit
def test_access_log_middleware_with_user_object(capsys: CaptureFixture[str]) -> None:
    configure_logging(level="INFO", json=True)

    class User:
        id = "user_456"

    async def endpoint(request: Request) -> Response:
        # Simulate auth middleware setting user in scope as an object
        request.scope["user"] = User()
        return JSONResponse({"status": "ok"})

    app = Starlette(routes=[Route("/", endpoint)])
    app.add_middleware(AccessLogMiddleware)

    client = TestClient(app)
    client.get("/")

    captured = capsys.readouterr()
    log_lines = captured.out.strip().split("\n")
    access_logs = [json.loads(line) for line in log_lines if line.strip()]
    access_log = next(log for log in access_logs if log.get("event") == "access_log")

    assert access_log["user_id"] == "user_456"


@pytest.mark.unit
def test_access_log_middleware_no_header_side_effects() -> None:
    async def endpoint(request: Request) -> Response:
        return JSONResponse({"status": "ok"})

    app = Starlette(routes=[Route("/", endpoint)])
    app.add_middleware(AccessLogMiddleware)

    client = TestClient(app)
    response = client.get("/")

    # Verify standard headers are present but security ones from T-502 are NOT
    assert response.headers["content-type"] == "application/json"
    assert "Content-Security-Policy" not in response.headers
    assert "X-Frame-Options" not in response.headers
    assert "X-Content-Type-Options" not in response.headers
    assert "Strict-Transport-Security" not in response.headers
