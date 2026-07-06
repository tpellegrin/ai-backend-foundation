from typing import cast

from redis.asyncio import Redis

from app.platform.cache.ports import CacheKey


class RedisCache:
    """
    Redis implementation of the Cache port.

    Satisfies the Cache protocol structurally.
    """

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def get(self, key: CacheKey) -> bytes | None:
        """Retrieve a value from the cache by key."""
        result = await self._client.get(key)
        if result is None:
            return None
        return cast(bytes, result)

    async def set(
        self,
        key: CacheKey,
        value: bytes,
        ttl_s: int | None = None,
    ) -> None:
        """Store a value in the cache with an optional TTL."""
        await self._client.set(key, value, ex=ttl_s)

    async def delete(self, key: CacheKey) -> None:
        """Remove a value from the cache by key."""
        await self._client.delete(key)

    async def incr(self, key: CacheKey) -> int:
        """
        Increment an integer value stored at key.

        Returns the new value.
        """
        return cast(int, await self._client.incr(key))

    async def expire(self, key: CacheKey, ttl_s: int) -> None:
        """Set a time-to-live for a key in seconds."""
        await self._client.expire(key, ttl_s)

    async def aclose(self) -> None:
        """
        Async shutdown hook.

        Closes the underlying Redis connection pool.
        """
        await self._client.aclose()
