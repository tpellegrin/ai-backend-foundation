# ruff: noqa: S101
import asyncio

import pytest
from fastapi import FastAPI
from starlette import status
from starlette.testclient import TestClient

from app.observability.health import (
    ProbeRegistry,
    ProbeResult,
    build_health_router,
)


class MockProbe:
    """Mock probe implementing the Probe protocol."""

    def __init__(
        self,
        name: str,
        result_status: str = "ok",
    ) -> None:
        self.name = name
        self._status = result_status
        self.called = False

    async def check(self) -> ProbeResult:
        self.called = True
        return ProbeResult(name=self.name, status=self._status)  # type: ignore[arg-type]


class ExplodingProbe:
    """Probe that raises when evaluated. Used to assert /livez performs no I/O."""

    name = "explode"

    async def check(self) -> ProbeResult:
        msg = "probe must not be evaluated"
        raise AssertionError(msg)


def _client(registry: ProbeRegistry, is_ready: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(build_health_router(registry, is_ready=lambda: is_ready))
    return TestClient(app)


@pytest.mark.unit
def test_livez_returns_200_and_performs_no_io() -> None:
    # Probe would explode if evaluated; /livez must not touch it.
    registry = ProbeRegistry([ExplodingProbe()])
    client = _client(registry)

    response = client.get("/livez")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}


@pytest.mark.unit
def test_healthz_no_probes_returns_200() -> None:
    client = _client(ProbeRegistry())
    response = client.get("/healthz")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}


@pytest.mark.unit
def test_healthz_all_probes_ok_returns_200() -> None:
    probe1 = MockProbe("db")
    probe2 = MockProbe("redis")
    client = _client(ProbeRegistry([probe1, probe2]))

    response = client.get("/healthz")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}
    assert probe1.called
    assert probe2.called


@pytest.mark.unit
def test_healthz_one_probe_failing_returns_503() -> None:
    client = _client(ProbeRegistry([MockProbe("db", result_status="error"), MockProbe("redis")]))

    response = client.get("/healthz")
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    body = response.json()
    assert body["status"] == "error"
    assert body["probes"] == {"db": "error", "redis": "ok"}


@pytest.mark.unit
def test_readyz_returns_503_when_not_ready_even_if_probes_pass() -> None:
    client = _client(ProbeRegistry([MockProbe("db")]), is_ready=False)
    response = client.get("/readyz")
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {"status": "starting"}


@pytest.mark.unit
def test_readyz_returns_200_when_ready_and_probes_pass() -> None:
    client = _client(ProbeRegistry([MockProbe("db")]), is_ready=True)
    response = client.get("/readyz")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}


@pytest.mark.unit
def test_readyz_returns_503_when_ready_but_probe_fails() -> None:
    client = _client(
        ProbeRegistry([MockProbe("db", result_status="error")]),
        is_ready=True,
    )
    response = client.get("/readyz")
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["status"] == "error"


@pytest.mark.unit
def test_probe_exception_recorded_as_error() -> None:
    class Boom:
        name = "boom"

        async def check(self) -> ProbeResult:
            raise RuntimeError("boom")

    client = _client(ProbeRegistry([Boom()]))
    response = client.get("/healthz")
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["probes"] == {"boom": "error"}


@pytest.mark.unit
def test_registry_evaluates_probes_in_registration_order() -> None:
    order: list[str] = []

    class Tracer:
        def __init__(self, name: str) -> None:
            self.name = name

        async def check(self) -> ProbeResult:
            order.append(self.name)
            return ProbeResult(name=self.name, status="ok")

    registry = ProbeRegistry([Tracer("a"), Tracer("b"), Tracer("c")])
    results = asyncio.run(registry.run_all())
    assert [r.name for r in results] == ["a", "b", "c"]
    assert order == ["a", "b", "c"]
