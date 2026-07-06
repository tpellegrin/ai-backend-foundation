from collections.abc import Generator

import pytest
from fastapi import FastAPI
from testcontainers.redis import RedisContainer  # type: ignore[import-untyped]  # no stubs

from app.core.config.settings import get_settings
from app.core.container import Container
from app.core.lifespan import lifespan
from app.infrastructure.redis.cache import RedisCache
from app.observability.health import ProbeRegistry
from app.platform.cache.ports import CacheKey


@pytest.fixture(scope="module")
def redis_container() -> Generator[RedisContainer]:
    """Start a Redis container."""
    with RedisContainer("redis:latest") as redis:
        yield redis


@pytest.mark.integration
async def test_cache_wiring_smoke(
    redis_container: RedisContainer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Smoke test to verify Cache and Redis wiring in lifespan."""
    # 1. Setup env
    redis_url = f"redis://{redis_container.get_container_host_ip()}:{redis_container.get_exposed_port(6379)}/0"
    monkeypatch.setenv("REDIS_URL", redis_url)
    monkeypatch.setenv("ARQ_REDIS_URL", redis_url)

    # 2. Setup container and app
    get_settings.cache_clear()
    settings = get_settings()

    container = Container(settings=settings, probe_registry=ProbeRegistry())
    app = FastAPI(lifespan=lifespan)
    app.state.container = container

    # 3. Execute lifespan
    async with lifespan(app):
        # Verify container fields are populated
        assert container.cache is not None  # noqa: S101
        assert isinstance(container.cache, RedisCache)  # noqa: S101

        # Verify Redis probe is registered
        probes = container.probe_registry.probes
        redis_probe = next((p for p in probes if p.name == "redis"), None)
        assert redis_probe is not None  # noqa: S101

        # Verify Redis probe works
        result = await redis_probe.check()
        assert result.status == "ok"  # noqa: S101

        # Verify Cache works
        await container.cache.set(CacheKey("test_key"), b"test_value")
        assert await container.cache.get(CacheKey("test_key")) == b"test_value"  # noqa: S101

    # 4. Verify shutdown
    # Note: we don't strictly assert on client state after aclose()
    # as redis-py behavior can vary, but the lifespan call completed.
