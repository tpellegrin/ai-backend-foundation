# ruff: noqa: S101, PLR2004
import asyncio

import pytest
from testcontainers.redis import RedisContainer  # type: ignore[import-untyped]  # missing stubs

from app.infrastructure.redis.cache import RedisCache
from app.infrastructure.redis.client import build_client
from app.platform.cache.ports import Cache, CacheKey


class SimpleRedisSettings:
    """Simple settings object for testing."""

    def __init__(self, url: str) -> None:
        self.url = url


@pytest.fixture(scope="module")
def redis_container() -> RedisContainer:
    """Start a Redis container."""
    with RedisContainer("redis:7-alpine") as redis:
        yield redis


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_cache_contract(redis_container: RedisContainer) -> None:
    """
    Test that RedisCache satisfies the Cache contract using a real Redis.
    """
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    url = f"redis://{host}:{port}/0"

    settings = SimpleRedisSettings(url=url)
    client = build_client(settings)
    cache = RedisCache(client)

    try:
        # 1. Structural conformance
        assert isinstance(cache, Cache)

        # 2. Basic get/set/delete
        key = CacheKey("test-key")
        value = b"test-value"

        await cache.set(key, value)
        assert await cache.get(key) == value

        await cache.delete(key)
        assert await cache.get(key) is None

        # 3. TTL (short)
        await cache.set(key, value, ttl_s=1)
        assert await cache.get(key) == value
        await asyncio.sleep(1.1)
        assert await cache.get(key) is None

        # 4. Increment
        counter_key = CacheKey("counter")
        # Ensure it starts fresh
        await cache.delete(counter_key)

        val1 = await cache.incr(counter_key)
        assert val1 == 1
        assert await cache.get(counter_key) == b"1"

        val2 = await cache.incr(counter_key)
        assert val2 == 2
        assert await cache.get(counter_key) == b"2"

        # 5. Expire
        await cache.set(key, b"expiring")
        await cache.expire(key, 1)
        assert await cache.get(key) == b"expiring"
        await asyncio.sleep(1.1)
        assert await cache.get(key) is None

    finally:
        await cache.aclose()
