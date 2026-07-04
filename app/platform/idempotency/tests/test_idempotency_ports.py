# ruff: noqa: S101
import pytest

from app.platform.idempotency.ports import IdempotencyRecord, IdempotencyStore


class IdempotencyStoreFake:
    """In-memory fake implementation of IdempotencyStore."""

    def __init__(self) -> None:
        self.data: dict[str, IdempotencyRecord] = {}

    async def begin(self, key: str, ttl_s: int) -> IdempotencyRecord:
        if key in self.data:
            return self.data[key]

        # Store in-flight but return new
        self.data[key] = IdempotencyRecord(status="in_flight")
        return IdempotencyRecord(status="new")

    async def complete(self, key: str, response_hash: str) -> None:
        self.data[key] = IdempotencyRecord(status="done", response_hash=response_hash)

    async def get(self, key: str) -> IdempotencyRecord | None:
        return self.data.get(key)


@pytest.mark.unit
def test_idempotency_protocol_satisfiability() -> None:
    """Assert that IdempotencyStoreFake satisfies the IdempotencyStore protocol."""
    fake = IdempotencyStoreFake()
    assert isinstance(fake, IdempotencyStore)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_idempotency_fake_behavior() -> None:
    """Sanity check that the fake actually works as expected."""
    fake = IdempotencyStoreFake()
    key = "test-key"

    # First attempt: returns new
    res1 = await fake.begin(key, 60)
    assert res1.status == "new"
    assert res1.response_hash is None

    # Second attempt (same key): returns in_flight
    res2 = await fake.begin(key, 60)
    assert res2.status == "in_flight"

    # Get status
    res_get = await fake.get(key)
    assert res_get is not None
    assert res_get.status == "in_flight"

    # Complete the operation
    await fake.complete(key, "resp-hash-123")

    # Get status again
    res_get_done = await fake.get(key)
    assert res_get_done is not None
    assert res_get_done.status == "done"
    assert res_get_done.response_hash == "resp-hash-123"

    # Subsequent begin returns done
    res3 = await fake.begin(key, 60)
    assert res3.status == "done"
    assert res3.response_hash == "resp-hash-123"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_idempotency_get_missing_key() -> None:
    """get() returns None for missing keys."""
    fake = IdempotencyStoreFake()
    assert await fake.get("non-existent") is None
