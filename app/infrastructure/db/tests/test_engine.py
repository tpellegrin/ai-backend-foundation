from collections.abc import Generator

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Mapped, mapped_column
from testcontainers.postgres import (  # type: ignore[import-untyped]  # missing stubs
    PostgresContainer,
)

from app.core.config.settings import AppSettings
from app.infrastructure.db.engine import create_engine_from, create_session_factory
from app.platform.db.base import Base
from app.platform.db.types import Vector


@pytest.fixture(scope="module")
def postgres_container() -> Generator[PostgresContainer]:
    """Start a postgres container with pgvector."""
    # Using ankane/pgvector as it comes with the extension pre-installed
    with PostgresContainer("ankane/pgvector:latest") as postgres:
        yield postgres


@pytest.mark.integration
async def test_db_engine_connectivity_and_pgvector(postgres_container: PostgresContainer) -> None:
    """Test that the engine connects to Postgres and pgvector works."""
    # 1. Setup settings with container URL
    # Replace psycopg2 with asyncpg in the URL
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

    settings = AppSettings()
    # Manually override the db url in the settings object
    settings.db.url = db_url

    # 2. Create engine and session factory
    engine = create_engine_from(settings.db)
    session_factory = create_session_factory(engine)

    try:
        # 3. Test basic connectivity
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar() == 1  # noqa: S101

        # 4. Test pgvector registration and usage
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

            # Define a test-only model
            class TestVectorModel(Base):
                __tablename__ = "test_vector"
                id: Mapped[int] = mapped_column(primary_key=True)
                embedding: Mapped[Vector] = mapped_column(Vector(3))

            # Create the table
            await conn.run_sync(Base.metadata.create_all)

        # Insert a vector
        vec = [1.0, 2.0, 3.0]
        async with session_factory() as session:
            obj = TestVectorModel(id=1, embedding=vec)
            session.add(obj)
            await session.commit()

        # Retrieve the vector
        async with session_factory() as session:
            obj_retrieved = await session.get(TestVectorModel, 1)
            assert obj_retrieved is not None  # noqa: S101
            # Vector returns a numpy-like array or list
            assert list(obj_retrieved.embedding) == vec  # noqa: S101

    finally:
        await engine.dispose()
