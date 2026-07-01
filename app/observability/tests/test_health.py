# ruff: noqa: S101
import asyncio

import pytest
from fastapi import FastAPI
from starlette import status
from starlette.testclient import TestClient

from app.observability.health import HealthProbe, health_registry, router


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_registry() -> None:
    # Reset registry before each test to ensure isolation
    health_registry._probes = []
    health_registry._startup_complete = False


class MockProbe:
    """Mock health probe for testing."""

    def __init__(self, name: str, healthy: bool = True) -> None:
        self.name = name
        self.healthy = healthy
        self.called = False

    async def check(self) -> bool:
        self.called = True
        return self.healthy


@pytest.mark.unit
def test_livez_returns_200(client: TestClient) -> None:
    response = client.get("/livez")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}


@pytest.mark.unit
def test_healthz_no_probes_returns_200(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}


@pytest.mark.unit
def test_healthz_all_probes_passing_returns_200(client: TestClient) -> None:
    probe1 = MockProbe("db", healthy=True)
    probe2 = MockProbe("redis", healthy=True)
    health_registry.register_probe(probe1)
    health_registry.register_probe(probe2)

    response = client.get("/healthz")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}
    assert probe1.called
    assert probe2.called


@pytest.mark.unit
def test_healthz_one_probe_failing_returns_503(client: TestClient) -> None:
    probe1 = MockProbe("db", healthy=False)
    probe2 = MockProbe("redis", healthy=True)
    health_registry.register_probe(probe1)
    health_registry.register_probe(probe2)

    response = client.get("/healthz")
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    data = response.json()
    assert data["status"] == "error"
    assert data["probes"] == {"db": False, "redis": True}


@pytest.mark.unit
def test_readyz_before_startup_returns_503(client: TestClient) -> None:
    response = client.get("/readyz")
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {"status": "starting"}


@pytest.mark.unit
def test_readyz_after_startup_returns_200(client: TestClient) -> None:
    health_registry.mark_startup_complete()
    response = client.get("/readyz")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}


@pytest.mark.unit
def test_readyz_after_startup_failing_probe_returns_503(client: TestClient) -> None:
    health_registry.mark_startup_complete()
    probe1 = MockProbe("db", healthy=False)
    health_registry.register_probe(probe1)

    response = client.get("/readyz")
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["status"] == "error"


@pytest.mark.unit
def test_probe_exception_handled_as_failure(client: TestClient) -> None:
    class ExplodingProbe:
        name = "boom"

        async def check(self) -> bool:
            raise RuntimeError("Boom")

    # ExplodingProbe matches HealthProbe protocol at runtime
    health_registry.register_probe(ExplodingProbe())

    response = client.get("/healthz")
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["probes"] == {"boom": False}


@pytest.mark.unit
def test_probe_timeout_handled_as_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Use a very short timeout for testing to avoid slowing down tests

    class SlowProbe:
        name = "slow"

        async def check(self) -> bool:
            await asyncio.sleep(0.2)
            return True

    health_registry.register_probe(SlowProbe())

    # Temporarily set a shorter timeout for the registry

    async def _short_safe_check(probe: HealthProbe) -> bool:
        try:
            return await asyncio.wait_for(probe.check(), timeout=0.1)
        except Exception:
            return False

    monkeypatch.setattr(health_registry, "_safe_check", _short_safe_check)

    response = client.get("/healthz")
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["probes"] == {"slow": False}
