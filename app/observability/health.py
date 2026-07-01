import asyncio
from typing import Any, Protocol, runtime_checkable

from fastapi import APIRouter, Response, status

from app.observability.logging import get_logger

logger = get_logger(__name__)


@runtime_checkable
class HealthProbe(Protocol):
    """
    Protocol for a health probe.
    Each probe must have a name and a check method.
    """

    name: str

    async def check(self) -> bool:
        """
        Perform the health check.
        Returns True if healthy, False otherwise.
        """
        ...


class HealthRegistry:
    """
    Registry for health probes and app startup state.
    """

    def __init__(self) -> None:
        self._probes: list[HealthProbe] = []
        self._startup_complete: bool = False

    def register_probe(self, probe: HealthProbe) -> None:
        """Register a new health probe."""
        self._probes.append(probe)

    def mark_startup_complete(self) -> None:
        """Mark the application startup as complete."""
        self._startup_complete = True

    @property
    def is_startup_complete(self) -> bool:
        """Return True if application startup is complete."""
        return self._startup_complete

    async def check_all(self) -> dict[str, bool]:
        """
        Run all registered probes and return their results.
        Returns an empty dict if no probes are registered.
        """
        if not self._probes:
            return {}

        results = await asyncio.gather(*(self._safe_check(probe) for probe in self._probes))

        return {probe.name: res for probe, res in zip(self._probes, results, strict=True)}

    async def _safe_check(self, probe: HealthProbe) -> bool:
        """
        Run a single probe safely, catching any exceptions and applying a timeout.
        """
        try:
            # Default 5 second timeout for probes to avoid blocking
            return await asyncio.wait_for(probe.check(), timeout=5.0)
        except Exception:
            # Any failure or timeout is considered unhealthy
            logger.exception("health_probe_failed", probe=probe.name)
            return False


# Global instance to be used by the app and core.wiring
health_registry = HealthRegistry()

router = APIRouter()


@router.get("/livez")
async def livez() -> dict[str, str]:
    """
    Liveness probe.
    Returns 200 as long as the process is running.
    Does NOT perform any I/O.
    """
    return {"status": "ok"}


@router.get("/healthz")
async def healthz(response: Response) -> dict[str, Any]:
    """
    Health probe.
    Returns 200 if all registered probes (DB, Redis, etc.) pass.
    Returns 503 if any probe fails.
    """
    probe_results = await health_registry.check_all()
    all_ok = all(probe_results.values())

    if not all_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error", "probes": probe_results}

    return {"status": "ok"}


@router.get("/readyz")
async def readyz(response: Response) -> dict[str, Any]:
    """
    Readiness probe.
    Returns 200 if startup is complete AND all health probes pass.
    Returns 503 otherwise.
    """
    if not health_registry.is_startup_complete:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "starting"}

    probe_results = await health_registry.check_all()
    all_ok = all(probe_results.values())

    if not all_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error", "probes": probe_results}

    return {"status": "ok"}
