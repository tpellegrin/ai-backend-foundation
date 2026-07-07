from collections.abc import Generator

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, insert, select, text
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

from app.infrastructure.db.engine import create_engine_from, create_session_factory
from app.platform.db.types import Vector


class MockSettings:
    """Mock settings for the database."""

    def __init__(self, url: str) -> None:
        self.url = url


@pytest.fixture(scope="module")
def postgres_container() -> Generator[PostgresContainer]:
    """Start a postgres container with pgvector."""
    # Using ankane/pgvector as it comes with the extension pre-installed
    with PostgresContainer("ankane/pgvector:latest") as postgres:
        yield postgres


@pytest.mark.integration
async def test_db_pgvector_roundtrip(postgres_container: PostgresContainer) -> None:
    """Test that pgvector round-trip works using the DB session stack."""
    # 1. Setup engine and session factory
    # Replace psycopg2 with asyncpg in the URL
    db_url = postgres_container.get_connection_url().replace("psycopg2", "asyncpg")
    settings = MockSettings(url=db_url)
    engine = create_engine_from(settings)
    session_factory = create_session_factory(engine)

    # 2. Create temp table with Vector(3) column
    metadata = MetaData()
    test_table = Table(
        "test_vector_roundtrip",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("embedding", Vector(3)),
    )

    async with engine.begin() as conn:
        # Ensure vector extension is enabled (ankane image has it, but we must be sure)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(metadata.create_all)

    try:
        # 3. Insert a record with a vector
        test_vector = [0.1, 0.2, 0.3]
        async with session_factory() as session:
            async with session.begin():
                await session.execute(insert(test_table).values(id=1, embedding=test_vector))

            # 4. Read back the record
            result = await session.execute(
                select(test_table.c.embedding).where(test_table.c.id == 1)
            )
            returned_vector = result.scalar_one()

            # 5. Assert vector equality with tolerance
            assert returned_vector is not None
            assert list(returned_vector) == pytest.approx(test_vector, abs=1e-6)

    finally:
        await engine.dispose()
