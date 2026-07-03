# ruff: noqa: S101
from collections.abc import AsyncIterator

import pytest

from app.platform.storage.ports import BlobRef, BlobStorage


class FakeBlobStorage(BlobStorage):
    """In-memory fake for static type-check fixture."""

    async def put(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str | None = None,
    ) -> BlobRef:
        return BlobRef(bucket=bucket, key=key, content_type=content_type, size=len(data))

    async def get(self, bucket: str, key: str) -> AsyncIterator[bytes]:
        yield b""

    async def delete(self, bucket: str, key: str) -> None:
        pass

    async def presign_get(self, bucket: str, key: str, ttl_s: int) -> str:
        return f"https://fake.storage/{bucket}/{key}?ttl={ttl_s}"


@pytest.mark.unit
def test_blob_storage_protocol_compliance() -> None:
    """Assert that the fake implementation satisfies the BlobStorage Protocol."""
    fake = FakeBlobStorage()
    assert isinstance(fake, BlobStorage)
