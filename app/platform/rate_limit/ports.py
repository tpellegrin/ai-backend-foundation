from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class RateLimitDecision:
    """Result of a rate limit check."""

    allowed: bool
    remaining: int
    reset_after_s: int


@runtime_checkable
class RateLimiter(Protocol):
    """
    Cross-cutting rate limiter port.

    Provides a simple interface for checking quotas against a sliding window.
    """

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
            key: The unique identifier for the rate limit bucket (e.g., user_id:endpoint).
            quota: The maximum number of allowed actions in the window.
            window_s: The duration of the sliding window in seconds.

        Returns:
            A RateLimitDecision indicating if the action is allowed and quota status.
        """
        ...
