# ruff: noqa: S101, PLR2004
import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

from app.api.security_headers import SecurityHeadersMiddleware


@pytest.mark.unit
def test_security_headers_present() -> None:
    app = Starlette(
        middleware=[Middleware(SecurityHeadersMiddleware, security_headers_enabled=True)]
    )

    async def homepage(request: Request) -> JSONResponse:
        return JSONResponse({"hello": "world"})

    app.add_route("/", homepage)

    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["Strict-Transport-Security"] == "max-age=63072000; includeSubDomains"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Content-Security-Policy"] == "default-src 'none'"


@pytest.mark.unit
def test_security_headers_disabled() -> None:
    app = Starlette(
        middleware=[Middleware(SecurityHeadersMiddleware, security_headers_enabled=False)]
    )

    async def homepage(request: Request) -> JSONResponse:
        return JSONResponse({"hello": "world"})

    app.add_route("/", homepage)

    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "Strict-Transport-Security" not in response.headers
    assert "X-Content-Type-Options" not in response.headers
    assert "Referrer-Policy" not in response.headers
    assert "X-Frame-Options" not in response.headers
    assert "Content-Security-Policy" not in response.headers


@pytest.mark.unit
def test_security_headers_default_enabled() -> None:
    app = Starlette(middleware=[Middleware(SecurityHeadersMiddleware)])

    async def homepage(request: Request) -> JSONResponse:
        return JSONResponse({"hello": "world"})

    app.add_route("/", homepage)

    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["Strict-Transport-Security"] == "max-age=63072000; includeSubDomains"
