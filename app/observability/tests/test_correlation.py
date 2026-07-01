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
        return JSONResponse({"id_in_var": request_id_var.get()})

    app = Starlette(routes=[Route("/", endpoint)])
    app.add_middleware(CorrelationMiddleware)

    client = TestClient(app)
    request_id = str(uuid.uuid4())
    response = client.get("/", headers={"X-Request-ID": request_id})

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["X-Request-ID"] == request_id
    assert response.json()["id_in_var"] == request_id


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
