# ruff: noqa: S101
import pytest

from app.platform.rate_limit.ports import RateLimitDecision, RateLimiter


class InMemoryRateLimiterFake:
    """A simple in-memory fake implementation of the RateLimiter port."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    async def allow(
        self,
        key: str,
        *,
        quota: int,
        window_s: int,
    ) -> RateLimitDecision:
        current = self.counts.get(key, 0)
        if current >= quota:
            return RateLimitDecision(
                allowed=False,
                remaining=0,
                reset_after_s=window_s,
            )

        new_count = current + 1
        self.counts[key] = new_count
        return RateLimitDecision(
            allowed=True,
            remaining=quota - new_count,
            reset_after_s=window_s,
        )


@pytest.mark.unit
def test_rate_limiter_protocol_satisfiability() -> None:
    """Assert that InMemoryRateLimiterFake satisfies the RateLimiter protocol."""
    fake = InMemoryRateLimiterFake()
    assert isinstance(fake, RateLimiter)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_in_memory_rate_limiter_fake_behavior() -> None:
    """Sanity check that the fake actually works as expected."""
    fake = InMemoryRateLimiterFake()
    key = "user:123"
    quota = 2
    window = 60

    # First call
    decision1 = await fake.allow(key, quota=quota, window_s=window)
    assert decision1.allowed is True
    assert decision1.remaining == 1

    # Second call
    decision2 = await fake.allow(key, quota=quota, window_s=window)
    assert decision2.allowed is True
    assert decision2.remaining == 0

    # Third call (blocked)
    decision3 = await fake.allow(key, quota=quota, window_s=window)
    assert decision3.allowed is False
    assert decision3.remaining == 0
