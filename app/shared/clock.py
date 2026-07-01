from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Return the current time as a timezone-aware UTC datetime."""
        ...


class SystemClock:
    def now(self) -> datetime:
        """Return the current system time in UTC."""
        return datetime.now(UTC)


class FixedClock:
    """A clock that always returns a fixed time, useful for testing."""

    def __init__(self, fixed_now: datetime) -> None:
        if fixed_now.tzinfo is None:
            # If naive, assume UTC as per project rules requiring tz-aware UTC
            self._now = fixed_now.replace(tzinfo=UTC)
        else:
            self._now = fixed_now.astimezone(UTC)

    def now(self) -> datetime:
        return self._now
