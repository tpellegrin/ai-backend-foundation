# ruff: noqa: S101, PLR2004
import pytest

from app.platform.cache.ports import Cache, CacheKey


class DictCacheFake:
    """A simple dict-backed fake implementation of the Cache port."""

    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key: CacheKey) -> bytes | None:
        return self.data.get(str(key))

    async def set(
        self,
        key: CacheKey,
        value: bytes,
        ttl_s: int | None = None,
    ) -> None:
        self.data[str(key)] = value
        if ttl_s is not None:
            self.ttls[str(key)] = ttl_s

    async def delete(self, key: CacheKey) -> None:
        self.data.pop(str(key), None)
        self.ttls.pop(str(key), None)

    async def incr(self, key: CacheKey) -> int:
        current = self.data.get(str(key), b"0")
        try:
            new_val = int(current.decode()) + 1
        except (ValueError, UnicodeDecodeError):
            new_val = 1
        self.data[str(key)] = str(new_val).encode()
        return new_val

    async def expire(self, key: CacheKey, ttl_s: int) -> None:
        if str(key) in self.data:
            self.ttls[str(key)] = ttl_s


@pytest.mark.unit
def test_cache_protocol_satisfiability() -> None:
    """Assert that DictCacheFake satisfies the Cache protocol."""
    fake = DictCacheFake()
    assert isinstance(fake, Cache)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_dict_cache_fake_behavior() -> None:
    """Sanity check that the fake actually works as expected."""
    fake = DictCacheFake()
    key = CacheKey("test-key")

    await fake.set(key, b"value")
    assert await fake.get(key) == b"value"

    await fake.delete(key)
    assert await fake.get(key) is None

    await fake.incr(CacheKey("counter"))
    assert await fake.get(CacheKey("counter")) == b"1"

    val = await fake.incr(CacheKey("counter"))
    assert val == 2
    assert await fake.get(CacheKey("counter")) == b"2"
