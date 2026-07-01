# ruff: noqa: S101
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.shared.clock import FixedClock, SystemClock


@pytest.mark.unit
def test_system_clock_now_is_tz_aware_utc() -> None:
    clock = SystemClock()
    now = clock.now()
    assert now.tzinfo == UTC


@pytest.mark.unit
def test_fixed_clock_returns_fixed_time() -> None:
    fixed_now = datetime(2024, 1, 1, tzinfo=UTC)
    clock = FixedClock(fixed_now)
    assert clock.now() == fixed_now


@pytest.mark.unit
def test_fixed_clock_handles_naive_datetime() -> None:
    naive_now = datetime(2024, 1, 1)
    clock = FixedClock(naive_now)
    assert clock.now().tzinfo == UTC
    assert clock.now().replace(tzinfo=None) == naive_now


@pytest.mark.unit
def test_fixed_clock_converts_to_utc() -> None:
    # Some other timezone
    other_tz = datetime.now(timezone(timedelta(hours=1))).tzinfo
    if other_tz is None:
        # Fallback if somehow tzinfo is None
        other_tz = timezone(timedelta(hours=1))

    tz_now = datetime(2024, 1, 1, 1, 0, tzinfo=other_tz)
    clock = FixedClock(tz_now)
    assert clock.now().tzinfo == UTC
    assert clock.now().hour == 0
