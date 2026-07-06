import contextlib
from collections.abc import AsyncIterator
from pathlib import Path

from app.platform.storage.ports import BlobRef


class LocalBlobStorage:
    """
    Local filesystem adapter for BlobStorage.
    Used for development and local testing.
    """

    def __init__(self, base_path: Path) -> None:
        self._base_path = base_path.resolve()

    def _validate_path(self, bucket: str, key: str) -> Path:
        """
        Validate bucket and key for safety and return the full path.
        Raises ValueError if validation fails.
        """
        for part_name, value in [("bucket", bucket), ("key", key)]:
            if not value:
                raise ValueError(f"{part_name} cannot be empty")  # noqa: TRY003
            if "\0" in value:
                raise ValueError(f"{part_name} cannot contain NUL bytes")  # noqa: TRY003
            if "\\" in value:
                raise ValueError(f"{part_name} cannot contain backslashes")  # noqa: TRY003
            if value.startswith("/"):
                raise ValueError(f"{part_name} cannot be an absolute path")  # noqa: TRY003

            # Reject Windows drive prefixes (e.g. C:/)
            # Even on POSIX, we reject them to satisfy the requirement.
            if ":" in value:
                raise ValueError(f"{part_name} contains forbidden character ':'")  # noqa: TRY003

            # Split by / and check segments
            segments = value.split("/")
            for segment in segments:
                if segment == "..":
                    raise ValueError(f"{part_name} cannot contain '..' segments")  # noqa: TRY003
                if segment == ".":
                    raise ValueError(f"{part_name} cannot contain '.' segments")  # noqa: TRY003
                if not segment:
                    # This happens for e.g. "a//b"
                    raise ValueError(f"{part_name} cannot contain empty segments")  # noqa: TRY003

        # Join and resolve
        try:
            # We use joinpath to avoid any accidental absolute path interpretation
            full_path = (self._base_path / bucket / key).resolve()
        except Exception as e:
            raise ValueError(f"Invalid path: {e}") from e  # noqa: TRY003

        # Final containment check
        try:
            full_path.relative_to(self._base_path)
        except ValueError:
            msg = "Path traversal detected: resolved path is outside base_path"
            raise ValueError(msg) from None

        return full_path

    async def put(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str | None = None,
    ) -> BlobRef:
        target_path = self._validate_path(bucket, key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(data)

        return BlobRef(
            bucket=bucket,
            key=key,
            content_type=content_type,
            size=len(data),
        )

    def get(self, bucket: str, key: str) -> AsyncIterator[bytes]:
        target_path = self._validate_path(bucket, key)
        if not target_path.exists():
            msg = f"Blob {bucket}/{key} not found"
            raise FileNotFoundError(msg)

        async def _stream() -> AsyncIterator[bytes]:
            with target_path.open("rb") as f:
                while chunk := f.read(64 * 1024):
                    yield chunk

        return _stream()

    async def delete(self, bucket: str, key: str) -> None:
        target_path = self._validate_path(bucket, key)
        with contextlib.suppress(FileNotFoundError):
            target_path.unlink()

    async def presign_get(self, bucket: str, key: str, ttl_s: int) -> str:
        target_path = self._validate_path(bucket, key)
        # ttl_s is ignored as per requirements
        return target_path.as_uri()
