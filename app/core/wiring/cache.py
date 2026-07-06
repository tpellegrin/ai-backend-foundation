from redis.asyncio import Redis

from app.core.config.settings import AppSettings
from app.infrastructure.redis.cache import RedisCache
from app.infrastructure.redis.client import build_client as build_redis_client
from app.observability.health import ProbeResult
from app.platform.cache.ports import Cache


def setup_redis_client(settings: AppSettings) -> Redis:
    """Build the shared Redis client."""
    return build_redis_client(settings.redis)


def setup_cache(client: Redis) -> Cache:
    """Wire cache port to Redis adapter."""
    return RedisCache(client)


async def shutdown_redis(client: Redis) -> None:
    """Shutdown the Redis client."""
    await client.aclose()


class RedisProbe:
    """Redis readiness probe."""

    name: str = "redis"

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def check(self) -> ProbeResult:
        """Check Redis connectivity."""
        await self._client.ping()
        return ProbeResult(name=self.name, status="ok")
