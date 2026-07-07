# ruff: noqa: S101
import pytest
from fastapi import APIRouter, FastAPI

from app.api import build_v1_router


@pytest.mark.unit
def test_build_v1_router_returns_router_with_prefix() -> None:
    """T-503: build_v1_router() returns an APIRouter mounted at prefix /api/v1."""
    router = build_v1_router()

    assert isinstance(router, APIRouter)
    assert router.prefix == "/api/v1"


@pytest.mark.unit
def test_build_v1_router_includes_auth_routes() -> None:
    """T-907: The router now includes the /auth router routes."""
    app = FastAPI()
    app.include_router(build_v1_router())

    # We assert that the expected auth paths are resolvable in the mounted app.
    # This verifies the prefix propagation and router inclusion.
    assert str(app.url_path_for("register")) == "/api/v1/auth/register"
    assert str(app.url_path_for("login")) == "/api/v1/auth/login"
    assert str(app.url_path_for("refresh")) == "/api/v1/auth/refresh"
    assert str(app.url_path_for("logout")) == "/api/v1/auth/logout"
