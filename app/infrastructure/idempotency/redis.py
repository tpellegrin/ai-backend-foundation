from redis.asyncio import Redis

from app.platform.idempotency.ports import IdempotencyRecord


class RedisIdempotencyStore:
    """
    Redis implementation of the IdempotencyStore port.

    Satisfies the IdempotencyStore protocol structurally.
    """

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def begin(self, key: str, ttl_s: int) -> IdempotencyRecord:
        """
        Attempt to start a new idempotent operation.

        Uses SET NX EX to atomically check and set the in-flight status.
        """
        redis_key = f"idem:{key}"

        # nx=True means 'set only if it does not exist' (NX)
        # ex=ttl_s means 'set expiration time in seconds' (EX)
        # Returns True if set, None otherwise.
        success = await self._client.set(
            redis_key,
            "in_flight",
            nx=True,
            ex=ttl_s,
        )

        if success:
            return IdempotencyRecord(status="new")

        # Key already exists, retrieve its current state.
        # If it expired in the microsecond between SET and GET,
        # we return "in_flight" to be safe: the caller didn't win the lock.
        return await self.get(key) or IdempotencyRecord(status="in_flight")

    async def complete(self, key: str, response_hash: str) -> None:
        """
        Mark an operation as completed with a response hash.

        Uses SET XX KEEPTTL to update the value only if it still exists,
        preserving the original TTL.
        """
        redis_key = f"idem:{key}"
        # xx=True means 'set only if it exists' (XX)
        # keepttl=True means 'preserve the existing TTL' (KEEPTTL)
        await self._client.set(
            redis_key,
            f"done:{response_hash}",
            xx=True,
            keepttl=True,
        )

    async def get(self, key: str) -> IdempotencyRecord | None:
        """
        Retrieve the current status of an operation by key.
        """
        redis_key = f"idem:{key}"
        val = await self._client.get(redis_key)
        if val is None:
            return None

        # The Redis client is configured with decode_responses=False,
        # so we get bytes and must decode them.
        val_str = val.decode("utf-8")

        if val_str == "in_flight":
            return IdempotencyRecord(status="in_flight")

        if val_str.startswith("done:"):
            return IdempotencyRecord(status="done", response_hash=val_str[5:])

        return None
