from collections.abc import Generator

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine
from testcontainers.postgres import (  # type: ignore[import-untyped]  # missing stubs
    PostgresContainer,
)

from app.core.config.settings import get_settings
from app.core.container import Container
from app.core.lifespan import lifespan
from app.observability.health import ProbeRegistry


@pytest.fixture(scope="module")
def postgres_container() -> Generator[PostgresContainer]:
    """Start a postgres container with pgvector."""
    with PostgresContainer("ankane/pgvector:latest") as postgres:
        yield postgres


@pytest.mark.integration
async def test_db_wiring_smoke(
    postgres_container: PostgresContainer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Smoke test to verify DB wiring in lifespan."""
    # 1. Setup env
    db_url = postgres_container.get_connection_url().replace("psycopg2", "asyncpg")

    # Pre-create vector extension so register_vector doesn't fail on first connect
    import asyncpg  # type: ignore[import-untyped]  # noqa: PLC0415  # missing stubs

    # asyncpg.connect doesn't like postgresql+asyncpg://
    raw_url = postgres_container.get_connection_url().replace("postgresql+psycopg2", "postgresql")
    conn = await asyncpg.connect(raw_url)
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    finally:
        await conn.close()

    monkeypatch.setenv("DATABASE_URL", db_url)

    # 2. Setup container and app
    # Clear lru_cache for settings to pick up monkeypatched env
    get_settings.cache_clear()
    settings = get_settings()

    container = Container(settings=settings, probe_registry=ProbeRegistry())
    app = FastAPI(lifespan=lifespan)
    app.state.container = container

    # 3. Execute lifespan
    async with lifespan(app):
        # Verify container fields are populated
        assert container.db_engine is not None  # noqa: S101
        assert isinstance(container.db_engine, AsyncEngine)  # noqa: S101
        assert container.session_factory is not None  # noqa: S101

        # Verify DB probe is registered
        probes = container.probe_registry.probes
        db_probe = next((p for p in probes if p.name == "db"), None)
        assert db_probe is not None  # noqa: S101

        # Verify DB probe works
        result = await db_probe.check()
        assert result.status == "ok"  # noqa: S101
