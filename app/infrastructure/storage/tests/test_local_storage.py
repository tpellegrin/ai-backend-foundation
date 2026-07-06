# ruff: noqa: S101
from pathlib import Path

import pytest

from app.infrastructure.storage.local import LocalBlobStorage
from app.platform.storage.ports import BlobRef, BlobStorage


@pytest.fixture
def storage_root(tmp_path: Path) -> Path:
    return tmp_path / "storage"


@pytest.fixture
def storage(storage_root: Path) -> LocalBlobStorage:
    storage_root.mkdir()
    return LocalBlobStorage(storage_root)


@pytest.mark.unit
@pytest.mark.asyncio
class TestLocalBlobStorageSafety:
    """Unit tests for key/bucket safety validation."""

    async def test_reject_empty_bucket(self, storage: LocalBlobStorage) -> None:
        with pytest.raises(ValueError, match="bucket cannot be empty"):
            await storage.put("", "key", b"data")

    async def test_reject_empty_key(self, storage: LocalBlobStorage) -> None:
        with pytest.raises(ValueError, match="key cannot be empty"):
            await storage.put("bucket", "", b"data")

    async def test_reject_nul_byte(self, storage: LocalBlobStorage) -> None:
        with pytest.raises(ValueError, match="bucket cannot contain NUL bytes"):
            await storage.put("buck\0et", "key", b"data")
        with pytest.raises(ValueError, match="key cannot contain NUL bytes"):
            await storage.put("bucket", "k\0ey", b"data")

    async def test_reject_backslash(self, storage: LocalBlobStorage) -> None:
        with pytest.raises(ValueError, match="bucket cannot contain backslashes"):
            await storage.put("buck\\et", "key", b"data")
        with pytest.raises(ValueError, match="key cannot contain backslashes"):
            await storage.put("bucket", "k\\ey", b"data")

    async def test_reject_traversal_segments(self, storage: LocalBlobStorage) -> None:
        cases = ["..", "a/../b", "../b", "a/.."]
        for case in cases:
            with pytest.raises(ValueError, match=r"cannot contain '\.\.' segments"):
                await storage.put(case, "key", b"data")
            with pytest.raises(ValueError, match=r"cannot contain '\.\.' segments"):
                await storage.put("bucket", case, b"data")

    async def test_reject_dot_segments(self, storage: LocalBlobStorage) -> None:
        cases = [".", "a/./b", "./b", "a/."]
        for case in cases:
            with pytest.raises(ValueError, match=r"cannot contain '\.' segments"):
                await storage.put(case, "key", b"data")
            with pytest.raises(ValueError, match=r"cannot contain '\.' segments"):
                await storage.put("bucket", case, b"data")

    async def test_reject_empty_segments(self, storage: LocalBlobStorage) -> None:
        # Note: /a and a/ might be caught by startswith or split
        # but let's test specific ones
        with pytest.raises(ValueError, match="cannot contain empty segments"):
            await storage.put("a//b", "key", b"data")
        with pytest.raises(ValueError, match="cannot contain empty segments"):
            await storage.put("bucket", "a//b", b"data")

    async def test_reject_absolute_paths(self, storage: LocalBlobStorage) -> None:
        with pytest.raises(ValueError, match="bucket cannot be an absolute path"):
            await storage.put("/etc/passwd", "key", b"data")
        with pytest.raises(ValueError, match="key cannot be an absolute path"):
            await storage.put("bucket", "/etc/passwd", b"data")

    async def test_reject_windows_drive_prefixes(self, storage: LocalBlobStorage) -> None:
        # Our implementation rejects ':' anywhere which covers C:/
        with pytest.raises(ValueError, match="contains forbidden character ':'"):
            await storage.put("C:/bucket", "key", b"data")
        with pytest.raises(ValueError, match="contains forbidden character ':'"):
            await storage.put("bucket", "C:/key", b"data")

    async def test_final_containment_check(
        self, storage: LocalBlobStorage, storage_root: Path
    ) -> None:
        # Create a directory outside storage_root
        outside = storage_root.parent / "outside"
        outside.mkdir()

        # Create a symlink inside storage_root pointing outside
        symlink_path = storage_root / "escape"
        symlink_path.symlink_to(outside)

        # Now try to use 'escape' as a bucket.
        with pytest.raises(ValueError, match="Path traversal detected"):
            await storage.put("escape", "key", b"data")


@pytest.mark.contract
@pytest.mark.asyncio
async def test_local_blob_storage_contract(storage: LocalBlobStorage) -> None:
    """Test that LocalBlobStorage satisfies the BlobStorage contract."""
    # 1. Structural compliance
    assert isinstance(storage, BlobStorage)

    bucket = "test-bucket"
    key = "test-key.txt"
    data = b"hello world"
    content_type = "text/plain"

    # 2. Put
    ref = await storage.put(bucket, key, data, content_type=content_type)
    assert isinstance(ref, BlobRef)
    assert ref.bucket == bucket
    assert ref.key == key
    assert ref.content_type == content_type
    assert ref.size == len(data)

    # 3. Get
    chunks = []
    stream = storage.get(bucket, key)
    async for chunk in stream:
        chunks.append(chunk)
    assert b"".join(chunks) == data

    # 4. Delete
    await storage.delete(bucket, key)

    # 5. Get after delete should raise FileNotFoundError
    with pytest.raises(FileNotFoundError):
        storage.get(bucket, key)

    # 6. Delete should be idempotent
    await storage.delete(bucket, key)  # Should not raise

    # 7. Presign GET
    url = await storage.presign_get(bucket, key, ttl_s=3600)
    assert url.startswith("file://")
    assert key in url


@pytest.mark.unit
@pytest.mark.asyncio
async def test_put_creates_directories(storage: LocalBlobStorage, storage_root: Path) -> None:
    bucket = "nested/bucket"
    key = "deep/path/to/file.dat"
    data = b"binary data"

    await storage.put(bucket, key, data)

    expected_path = storage_root / bucket / key
    assert expected_path.exists()
    assert expected_path.read_bytes() == data
