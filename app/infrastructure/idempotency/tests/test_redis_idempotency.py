# ruff: noqa: S101
import asyncio

import pytest
from redis.asyncio import Redis
from testcontainers.redis import RedisContainer  # type: ignore[import-untyped]

from app.infrastructure.idempotency.redis import RedisIdempotencyStore
from app.platform.idempotency.ports import IdempotencyStore


@pytest.fixture(scope="module")
def redis_container() -> RedisContainer:
    """Start a Redis container."""
    with RedisContainer("redis:7-alpine") as redis:
        yield redis


@pytest.mark.integration
@pytest.mark.contract
@pytest.mark.asyncio
async def test_redis_idempotency_store_contract(redis_container: RedisContainer) -> None:
    """
    Test that RedisIdempotencyStore satisfies the IdempotencyStore contract.
    """
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    url = f"redis://{host}:{port}/0"

    client: Redis = Redis.from_url(url, encoding="utf-8", decode_responses=False)
    store = RedisIdempotencyStore(client)

    try:
        # 1. Structural conformance
        assert isinstance(store, IdempotencyStore)

        key = "test-request-1"
        ttl = 10

        # 2. Begin new operation
        record1 = await store.begin(key, ttl)
        assert record1.status == "new"
        assert record1.response_hash is None

        # 3. Begin in-flight operation (same key)
        record2 = await store.begin(key, ttl)
        assert record2.status == "in_flight"
        assert record2.response_hash is None

        # 4. Get current status
        record3 = await store.get(key)
        assert record3 is not None
        assert record3.status == "in_flight"

        # 5. Complete operation
        resp_hash = "abc123hash"
        await store.complete(key, resp_hash)

        # 6. Begin completed operation
        record4 = await store.begin(key, ttl)
        assert record4.status == "done"
        assert record4.response_hash == resp_hash

        # 7. Get completed status
        record5 = await store.get(key)
        assert record5 is not None
        assert record5.status == "done"
        assert record5.response_hash == resp_hash

        # 8. Non-existent key
        assert await store.get("non-existent") is None

        # 9. TTL expiration
        short_key = "short-lived"
        await store.begin(short_key, 1)
        res = await store.get(short_key)
        assert res is not None
        assert res.status == "in_flight"

        await asyncio.sleep(1.1)
        assert await store.get(short_key) is None

        # 10. Re-begin after expiration
        record6 = await store.begin(short_key, 1)
        assert record6.status == "new"

    finally:
        await client.aclose()
