from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette import status

from app.main.app_factory import create_app


@pytest.fixture
def fastapi_app() -> FastAPI:
    return create_app()


@pytest.fixture
def client(fastapi_app: FastAPI) -> TestClient:
    return TestClient(fastapi_app, raise_server_exceptions=False)


@pytest.mark.api
def test_response_echoes_inbound_x_request_id(client: TestClient) -> None:
    request_id = str(uuid.uuid4())
    response = client.get("/healthz", headers={"X-Request-ID": request_id})

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["X-Request-ID"] == request_id


@pytest.mark.api
def test_response_generates_x_request_id_if_absent(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.status_code == status.HTTP_200_OK
    assert "X-Request-ID" in response.headers

    # Verify it is a valid UUID
    header_val = response.headers["X-Request-ID"]
    uuid.UUID(header_val)


@pytest.mark.api
def test_response_generates_new_id_on_invalid_inbound_id(client: TestClient) -> None:
    # Invalid UUID
    response = client.get("/healthz", headers={"X-Request-ID": "not-a-uuid"})

    assert response.status_code == status.HTTP_200_OK
    header_val = response.headers["X-Request-ID"]
    uuid.UUID(header_val)
