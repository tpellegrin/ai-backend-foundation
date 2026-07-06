# ruff: noqa: S101
import asyncio

import pytest
from testcontainers.redis import RedisContainer  # type: ignore[import-untyped]

from app.infrastructure.rate_limit.redis import RedisRateLimiter
from app.infrastructure.redis.client import build_client
from app.platform.rate_limit.ports import RateLimiter


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
async def test_redis_rate_limiter_contract(redis_container: RedisContainer) -> None:
    """
    Test that RedisRateLimiter satisfies the RateLimiter contract using a real Redis.
    """
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    url = f"redis://{host}:{port}/0"

    settings = SimpleRedisSettings(url=url)
    client = build_client(settings)
    limiter = RedisRateLimiter(client)

    try:
        # 1. Structural conformance
        assert isinstance(limiter, RateLimiter)

        key = "test-user"
        quota = 2
        window = 60

        # 2. Basic behavior: allowed within quota
        decision1 = await limiter.allow(key, quota=quota, window_s=window)
        assert decision1.allowed is True
        assert decision1.remaining == 1

        decision2 = await limiter.allow(key, quota=quota, window_s=window)
        assert decision2.allowed is True
        assert decision2.remaining == 0

        # 3. Basic behavior: blocked outside quota
        decision3 = await limiter.allow(key, quota=quota, window_s=window)
        assert decision3.allowed is False
        assert decision3.remaining == 0

        # 4. Token bucket refill (short window for testing)
        short_key = "short-window-user"
        short_quota = 1
        short_window = 1

        # First one allowed
        await limiter.allow(short_key, quota=short_quota, window_s=short_window)

        # Second one immediately blocked
        blocked = await limiter.allow(short_key, quota=short_quota, window_s=short_window)
        assert blocked.allowed is False

        # Wait for refill
        await asyncio.sleep(1.1)

        # Should be allowed again
        refilled = await limiter.allow(short_key, quota=short_quota, window_s=short_window)
        assert refilled.allowed is True

    finally:
        await client.aclose()
