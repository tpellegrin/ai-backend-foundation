from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class BlobRef:
    """Reference to a blob in storage."""

    bucket: str
    key: str
    content_type: str | None = None
    size: int | None = None
    etag: str | None = None


@runtime_checkable
class BlobStorage(Protocol):
    """
    Cross-cutting blob storage port.

    Used by modules (like documents) to store and retrieve large binary objects.
    All methods are async and take 'bucket' as the first argument.
    """

    async def put(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str | None = None,
    ) -> BlobRef:
        """Upload a blob to the specified bucket and key."""
        ...

    def get(self, bucket: str, key: str) -> AsyncIterator[bytes]:
        """Download a blob as an async iterator of bytes."""
        ...

    async def delete(self, bucket: str, key: str) -> None:
        """Delete a blob from storage."""
        ...

    async def presign_get(self, bucket: str, key: str, ttl_s: int) -> str:
        """Generate a pre-signed URL for GET access to a blob."""
        ...
