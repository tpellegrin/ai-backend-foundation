from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI

from app.core.config.settings import get_settings
from app.core.container import Container
from app.core.lifespan import lifespan
from app.core.wiring.storage import setup_storage
from app.infrastructure.storage.local import LocalBlobStorage
from app.observability.health import ProbeRegistry


@pytest.mark.unit
def test_setup_storage_local(tmp_path: Path) -> None:
    """Verify that local storage is wired correctly."""
    settings = MagicMock()
    settings.blob = MagicMock()
    settings.blob.backend = "local"
    settings.blob.local_dir = tmp_path

    storage = setup_storage(settings)

    assert isinstance(storage, LocalBlobStorage)  # noqa: S101
    assert storage._base_path == tmp_path.resolve()  # noqa: S101


@pytest.mark.unit
def test_setup_storage_unsupported() -> None:
    """Verify that unsupported backend raises ValueError."""

    # We need to bypass Pydantic validation for Literal if we want to test unsupported backend,
    # but the Literal itself prevents it at type level.
    # However, if we force it:
    class MockBlobSettings:
        backend = "s3"
        local_dir = Path("/nonexistent")

    class MockSettings:
        blob = MockBlobSettings()

    with pytest.raises(ValueError, match="Unsupported blob storage backend: s3"):
        setup_storage(MockSettings())  # type: ignore[arg-type]  # bypass Literal to test runtime guard


@pytest.mark.integration
async def test_storage_lifespan_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Smoke test to verify Storage wiring in lifespan."""
    # 1. Mock DB and Redis wiring to avoid needing real containers
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    monkeypatch.setattr("app.core.wiring.db.setup_db", lambda _: (mock_engine, MagicMock()))

    mock_redis = MagicMock()
    mock_redis.aclose = AsyncMock()
    monkeypatch.setattr("app.core.wiring.cache.setup_redis_client", lambda _: mock_redis)
    monkeypatch.setattr("app.core.wiring.cache.setup_cache", lambda _: MagicMock())

    # Mock probes
    monkeypatch.setattr("app.core.wiring.db.DBProbe.check", AsyncMock())
    monkeypatch.setattr("app.core.wiring.cache.RedisProbe.check", AsyncMock())

    # 2. Setup env to allow get_settings() to pass validation
    monkeypatch.setenv("BLOB_LOCAL_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost")
    monkeypatch.setenv("ARQ_REDIS_URL", "redis://localhost")
    monkeypatch.setenv("JWT_PRIVATE_KEY", "secret")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "secret")
    monkeypatch.setenv("JWT_ISSUER", "me")
    monkeypatch.setenv("JWT_AUDIENCE", "you")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_CHAT_MODEL", "gpt-4")
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002")
    monkeypatch.setenv("LLM_MONTHLY_BUDGET_USD", "10")
    monkeypatch.setenv("LLM_MODEL_ALLOWLIST", "gpt-4")

    # 3. Setup container and app
    get_settings.cache_clear()
    settings = get_settings()

    container = Container(settings=settings, probe_registry=ProbeRegistry())
    app = FastAPI(lifespan=lifespan)
    app.state.container = container

    # 4. Execute lifespan
    async with lifespan(app):
        # Verify container fields are populated
        assert container.blob_storage is not None  # noqa: S101
        assert isinstance(container.blob_storage, LocalBlobStorage)  # noqa: S101
