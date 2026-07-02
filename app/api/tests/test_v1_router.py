# ruff: noqa: S101
import pytest
from fastapi import APIRouter

from app.api import build_v1_router


@pytest.mark.unit
def test_build_v1_router_returns_empty_router_with_prefix() -> None:
    """
    T-503: build_v1_router() returns an empty APIRouter mounted at prefix /api/v1.
    """
    router = build_v1_router()

    assert isinstance(router, APIRouter)
    assert router.prefix == "/api/v1"
    assert len(router.routes) == 0
