from typing import cast

from redis.asyncio import Redis

from app.platform.rate_limit.ports import RateLimitDecision


class RedisRateLimiter:
    """
    Redis implementation of the RateLimiter port using a token-bucket algorithm.

    Satisfies the RateLimiter protocol structurally.
    """

    _LUA_SCRIPT = """
local key = KEYS[1]
local quota = tonumber(ARGV[1])
local window_s = tonumber(ARGV[2])

local time_res = redis.call('TIME')
local now = tonumber(time_res[1]) + (tonumber(time_res[2]) / 1000000)

local res = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(res[1])
local ts = tonumber(res[2])

if tokens == nil then
    tokens = quota
    ts = now
else
    local elapsed = math.max(0, now - ts)
    local refill = elapsed * (quota / window_s)
    tokens = math.min(quota, tokens + refill)
    ts = now
end

local allowed = 0
if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
end

redis.call('HMSET', key, 'tokens', tokens, 'ts', ts)
redis.call('EXPIRE', key, math.ceil(window_s))

return {allowed, math.floor(tokens)}
"""

    def __init__(self, client: Redis) -> None:
        self._client = client
        self._script = client.register_script(self._LUA_SCRIPT)

    async def allow(
        self,
        key: str,
        *,
        quota: int,
        window_s: int,
    ) -> RateLimitDecision:
        """
        Check if an action identified by 'key' is allowed within the quota.

        Args:
            key: The unique identifier for the rate limit bucket.
            quota: The maximum number of allowed actions in the window.
            window_s: The duration of the sliding window in seconds.

        Returns:
            A RateLimitDecision indicating if the action is allowed and quota status.
        """
        redis_key = f"rl:{key}"

        # result is [allowed_int, remaining_int]
        result = await self._script(
            keys=[redis_key],
            args=[quota, window_s],
        )

        allowed_int, remaining = cast(list[int], result)

        return RateLimitDecision(
            allowed=bool(allowed_int),
            remaining=remaining,
            reset_after_s=window_s,
        )
