from typing import Any, Protocol, cast

from redis.asyncio import Redis


class RedisSettings(Protocol):
    """Protocol for Redis-specific settings."""

    url: Any


def build_client(settings: RedisSettings) -> Redis:
    """
    Build an async Redis client from settings.

    The client uses a connection pool internally.
    """
    return cast(
        Redis,
        Redis.from_url(
            str(settings.url),
            encoding="utf-8",
            decode_responses=False,  # We want raw bytes for the Cache adapter
        ),
    )
