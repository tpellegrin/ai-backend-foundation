import asyncio
from collections.abc import Generator

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

from alembic import command
from app.core.config import get_settings


@pytest.fixture(scope="module")
def postgres_container() -> Generator[PostgresContainer]:
    """Start a postgres container with pgvector."""
    # Using ankane/pgvector as it comes with the extension pre-installed
    with PostgresContainer("ankane/pgvector:latest") as postgres:
        yield postgres


@pytest.mark.integration
def test_vector_extension_exists_after_migration(
    postgres_container: PostgresContainer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that the 'vector' extension exists after running migrations."""
    # 1. Setup DATABASE_URL for alembic/env.py and engine
    db_url = postgres_container.get_connection_url().replace("psycopg2", "asyncpg")
    monkeypatch.setenv("DATABASE_URL", db_url)

    # 1.1 Clear settings cache to ensure the new env var is picked up
    get_settings.cache_clear()

    # 2. Run migrations
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    # 3. Verify extension existence
    async def check_extension() -> None:
        engine = create_async_engine(db_url)
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text("SELECT extname FROM pg_extension WHERE extname='vector'")
                )
                row = result.fetchone()
                assert row is not None
                assert row[0] == "vector"
        finally:
            await engine.dispose()

    asyncio.run(check_extension())

    # 4. Cleanup migrations (downgrade to base)
    command.downgrade(alembic_cfg, "base")
    get_settings.cache_clear()
