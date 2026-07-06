from app.core.config.settings import AppSettings
from app.infrastructure.storage.local import LocalBlobStorage
from app.platform.storage.ports import BlobStorage


def setup_storage(settings: AppSettings) -> BlobStorage:
    """
    Wire storage port to adapter per settings.

    In Phase 2, only 'local' backend is supported.
    """
    if settings.blob.backend == "local":
        return LocalBlobStorage(base_path=settings.blob.local_dir)

    msg = f"Unsupported blob storage backend: {settings.blob.backend}"
    raise ValueError(msg)
