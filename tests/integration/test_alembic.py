from collections.abc import Generator

import pytest
from alembic.config import Config
from testcontainers.postgres import (  # type: ignore[import-untyped]  # missing stubs
    PostgresContainer,
)

from alembic import command
from app.core.config import get_settings


@pytest.fixture(scope="module")
def postgres_container() -> Generator[PostgresContainer]:
    """Start a postgres container with pgvector."""
    # Using ankane/pgvector as it comes with the extension pre-installed
    with PostgresContainer("ankane/pgvector:latest") as postgres:
        yield postgres


@pytest.mark.integration
def test_alembic_migrations_lifecycle(
    postgres_container: PostgresContainer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that alembic upgrade head and downgrade base succeed on a real DB."""
    # 1. Setup DATABASE_URL for alembic/env.py to pick up
    # Replace psycopg2 with asyncpg in the URL
    db_url = postgres_container.get_connection_url().replace("psycopg2", "asyncpg")
    monkeypatch.setenv("DATABASE_URL", db_url)

    # 1.1 Clear settings cache to ensure the new env var is picked up
    get_settings.cache_clear()

    # 2. Setup alembic configuration
    alembic_cfg = Config("alembic.ini")

    # 3. Upgrade to head
    # Even if there are no migrations yet, this should succeed (create alembic_version table)
    command.upgrade(alembic_cfg, "head")

    # 4. Downgrade to base
    # This should also succeed and leave the DB clean
    try:
        command.downgrade(alembic_cfg, "base")
    finally:
        get_settings.cache_clear()
