# ruff: noqa: S101
import asyncio
import uuid

import httpx
import pytest
from starlette import status
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from app.observability.correlation import CorrelationMiddleware, request_id_var


@pytest.mark.unit
def test_correlation_middleware_echoes_id() -> None:
    async def endpoint(request: Request) -> Response:
        return JSONResponse(
            {
                "id_in_var": request_id_var.get(),
                "id_in_state": getattr(request.state, "request_id", ""),
            }
        )

    app = Starlette(routes=[Route("/", endpoint)])
    app.add_middleware(CorrelationMiddleware)

    client = TestClient(app)
    request_id = str(uuid.uuid4())
    response = client.get("/", headers={"X-Request-ID": request_id})

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["X-Request-ID"] == request_id
    body = response.json()
    assert body["id_in_var"] == request_id
    # The id must also live on scope-backed request.state so that Starlette's
    # ServerErrorMiddleware — which wraps this middleware — can recover it
    # when handling sanitized 500 responses.
    assert body["id_in_state"] == request_id


@pytest.mark.unit
def test_correlation_middleware_persists_state_across_exception() -> None:
    """CorrelationMiddleware must expose the request id on ``request.state``
    even when the downstream endpoint raises. ``request.state`` is backed by
    ``scope["state"]``, so an ``Exception`` handler running in
    ``ServerErrorMiddleware`` (outside this middleware) can still read it
    after our contextvar has been reset in the ``finally`` block."""

    seen: dict[str, str] = {}

    async def boom(request: Request) -> Response:  # pragma: no cover - not reached fully
        # Snapshot the state that the outer error handler will see.
        seen["state"] = getattr(request.state, "request_id", "")
        seen["ctx"] = request_id_var.get()
        raise RuntimeError("kaboom")

    app = Starlette(routes=[Route("/boom", boom)])
    app.add_middleware(CorrelationMiddleware)

    client = TestClient(app, raise_server_exceptions=False)
    request_id = str(uuid.uuid4())
    response = client.get("/boom", headers={"X-Request-ID": request_id})

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert seen["state"] == request_id
    assert seen["ctx"] == request_id
    # The contextvar must have been reset once the middleware unwound.
    assert request_id_var.get() == ""


@pytest.mark.unit
def test_correlation_middleware_generates_id() -> None:
    async def endpoint(request: Request) -> Response:
        return JSONResponse({"id_in_var": request_id_var.get()})

    app = Starlette(routes=[Route("/", endpoint)])
    app.add_middleware(CorrelationMiddleware)

    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == status.HTTP_200_OK
    assert "X-Request-ID" in response.headers
    generated_id = response.headers["X-Request-ID"]
    # Check if it's a valid UUID
    uuid.UUID(generated_id)
    assert response.json()["id_in_var"] == generated_id


@pytest.mark.unit
def test_correlation_middleware_malformed_id_triggers_generation() -> None:
    async def endpoint(request: Request) -> Response:
        return JSONResponse({"id_in_var": request_id_var.get()})

    app = Starlette(routes=[Route("/", endpoint)])
    app.add_middleware(CorrelationMiddleware)

    client = TestClient(app)
    response = client.get("/", headers={"X-Request-ID": "not-a-uuid"})

    assert response.status_code == status.HTTP_200_OK
    assert "X-Request-ID" in response.headers
    generated_id = response.headers["X-Request-ID"]
    assert generated_id != "not-a-uuid"
    uuid.UUID(generated_id)
    assert response.json()["id_in_var"] == generated_id


@pytest.mark.unit
@pytest.mark.asyncio
async def test_correlation_middleware_concurrency() -> None:
    async def endpoint(request: Request) -> Response:
        await asyncio.sleep(0.1)
        return JSONResponse({"id_in_var": request_id_var.get()})

    app = Starlette(routes=[Route("/", endpoint)])
    app.add_middleware(CorrelationMiddleware)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        id1 = str(uuid.uuid4())
        id2 = str(uuid.uuid4())

        # Run concurrent requests
        responses = await asyncio.gather(
            client.get("/", headers={"X-Request-ID": id1}),
            client.get("/", headers={"X-Request-ID": id2}),
        )

        assert responses[0].json()["id_in_var"] == id1
        assert responses[1].json()["id_in_var"] == id2
        assert responses[0].headers["X-Request-ID"] == id1
        assert responses[1].headers["X-Request-ID"] == id2
