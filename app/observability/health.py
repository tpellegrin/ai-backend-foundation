import asyncio
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable

from fastapi import APIRouter, Response, status

from app.observability.logging import get_logger

logger = get_logger(__name__)

ProbeStatus = Literal["ok", "degraded", "error"]


@dataclass(frozen=True)
class ProbeResult:
    """Result of running a single probe."""

    name: str
    status: ProbeStatus
    latency_ms: int | None = None


@runtime_checkable
class Probe(Protocol):
    """Protocol for a health probe. Implementations must expose a ``name``
    attribute and an async ``check()`` returning a :class:`ProbeResult`.
    """

    name: str

    async def check(self) -> ProbeResult: ...


class ProbeRegistry:
    """Immutable, pure container that composes zero or more probes.

    The registry itself performs no I/O and holds no global state; it only
    fans out to the probes it was constructed with, in deterministic order.
    """

    __slots__ = ("_probes",)

    def __init__(self, probes: Iterable[Probe] = ()) -> None:
        self._probes: tuple[Probe, ...] = tuple(probes)

    @property
    def probes(self) -> tuple[Probe, ...]:
        return self._probes

    async def run_all(self) -> Sequence[ProbeResult]:
        """Run all probes in registration order and return their results."""
        if not self.probes:
            return ()
        return await asyncio.gather(*(_safe_check(probe) for probe in self.probes))


async def _safe_check(probe: Probe) -> ProbeResult:
    """Run a single probe safely, catching exceptions and applying a timeout."""
    try:
        return await asyncio.wait_for(probe.check(), timeout=5.0)
    except Exception:
        logger.exception("health_probe_failed", probe=probe.name)
        return ProbeResult(name=probe.name, status="error")


def _all_ok(results: Sequence[ProbeResult]) -> bool:
    return all(r.status == "ok" for r in results)


def _results_payload(results: Sequence[ProbeResult]) -> dict[str, str]:
    return {r.name: r.status for r in results}


def build_health_router(registry: ProbeRegistry, *, is_ready: Callable[[], bool]) -> APIRouter:
    """Build a health APIRouter bound to the given probe registry and readiness callable.

    Endpoints:
      * ``/livez``  — process liveness; performs no I/O and no probe evaluation.
      * ``/healthz``— runs the registry's probes; 200 if all ok, 503 otherwise.
      * ``/readyz`` — consults ``is_ready()`` and runs probes; 503 if either fails.
    """
    router = APIRouter()

    @router.get("/livez")
    async def livez() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/healthz")
    async def healthz(response: Response) -> dict[str, Any]:
        results = await registry.run_all()
        if not _all_ok(results):
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "error", "probes": _results_payload(results)}
        return {"status": "ok"}

    @router.get("/readyz")
    async def readyz(response: Response) -> dict[str, Any]:
        if not is_ready():
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "starting"}
        results = await registry.run_all()
        if not _all_ok(results):
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "error", "probes": _results_payload(results)}
        return {"status": "ok"}

    return router
