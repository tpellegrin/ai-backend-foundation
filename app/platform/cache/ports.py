from typing import NewType, Protocol, runtime_checkable

CacheKey = NewType("CacheKey", str)


@runtime_checkable
class Cache(Protocol):
    """
    Cross-cutting cache port.

    Provides a simple async interface for key-value caching.
    """

    async def get(self, key: CacheKey) -> bytes | None:
        """Retrieve a value from the cache by key."""
        ...

    async def set(
        self,
        key: CacheKey,
        value: bytes,
        ttl_s: int | None = None,
    ) -> None:
        """Store a value in the cache with an optional TTL."""
        ...

    async def delete(self, key: CacheKey) -> None:
        """Remove a value from the cache by key."""
        ...

    async def incr(self, key: CacheKey) -> int:
        """
        Increment an integer value stored at key.

        If the key does not exist, it is set to 0 before performing the operation.
        Returns the new value.
        """
        ...

    async def expire(self, key: CacheKey, ttl_s: int) -> None:
        """Set a time-to-live for a key in seconds."""
        ...
