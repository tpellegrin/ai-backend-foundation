# ruff: noqa: S106
import inspect
import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime, timedelta

import pytest
from alembic.config import Config
from sqlalchemy import text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

import app.auth.persistence
from alembic import command
from app.auth.domain import RefreshTokenRecord, UserAuthRecord
from app.auth.persistence import (
    RefreshTokenRow,
    get_active_refresh_token_by_family,
    get_refresh_token_by_hash,
    get_refresh_token_by_id,
    get_user_by_email,
    get_user_by_id,
    insert_refresh_token,
    insert_user,
)
from app.core.config import get_settings
from app.infrastructure.db.engine import create_engine_from, create_session_factory


class _SettingsStub:
    def __init__(self, url: str) -> None:
        self.url = url


@pytest.fixture(scope="module")
def postgres_container() -> Generator[PostgresContainer]:
    with PostgresContainer("ankane/pgvector:latest") as postgres:
        yield postgres


@pytest.fixture
def alembic_config(
    postgres_container: PostgresContainer, monkeypatch: pytest.MonkeyPatch
) -> Config:
    db_url = postgres_container.get_connection_url().replace("psycopg2", "asyncpg")
    monkeypatch.setenv("DATABASE_URL", db_url)
    get_settings.cache_clear()

    config = Config("alembic.ini")
    command.upgrade(config, "head")
    return config


@pytest.fixture
async def engine(postgres_container: PostgresContainer) -> AsyncGenerator:
    db_url = postgres_container.get_connection_url().replace("psycopg2", "asyncpg")
    settings = _SettingsStub(url=db_url)
    engine = create_engine_from(settings)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(engine):
    return create_session_factory(engine)


@pytest.fixture
async def session(session_factory) -> AsyncGenerator[AsyncSession]:
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.mark.integration
async def test_migration_created_tables(session: AsyncSession, alembic_config: Config) -> None:
    # Verify tables exist
    for table in ["users", "refresh_tokens"]:
        result = await session.execute(
            text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :table)"
            ).bindparams(table=table)
        )
        assert result.scalar() is True, f"Table {table} does not exist"


@pytest.mark.integration
async def test_user_persistence_roundtrip(session: AsyncSession, alembic_config: Config) -> None:
    user_id = uuid.uuid4()
    email = f"test-{user_id}@example.com"
    now = datetime.now(UTC)

    # 1. Insert
    record = await insert_user(
        session,
        id=user_id,
        email=email,
        password_hash="hashed_password",
        created_at=now,
        tenant_id=None,
        disabled=False,
    )

    assert isinstance(record, UserAuthRecord)
    assert record.id == user_id
    assert record.email == email

    # 2. Lookup by email
    found_by_email = await get_user_by_email(session, email)
    assert found_by_email == record

    # 3. Lookup by id
    found_by_id = await get_user_by_id(session, user_id)
    assert found_by_id == record


@pytest.mark.integration
async def test_refresh_token_persistence_roundtrip(
    session: AsyncSession, alembic_config: Config
) -> None:
    user_id = uuid.uuid4()
    await insert_user(
        session,
        id=user_id,
        email=f"token-user-{user_id}@example.com",
        password_hash="hash",
        created_at=datetime.now(UTC),
        tenant_id=None,
        disabled=False,
    )

    token_id = uuid.uuid4()
    family_id = uuid.uuid4()
    token_hash = f"hash-{token_id}"
    now = datetime.now(UTC)
    expires = now + timedelta(days=7)

    # 1. Insert
    record = await insert_refresh_token(
        session,
        id=token_id,
        user_id=user_id,
        family_id=family_id,
        hash=token_hash,
        issued_at=now,
        expires_at=expires,
        revoked_at=None,
        replaced_by=None,
    )

    assert isinstance(record, RefreshTokenRecord)
    assert record.id == token_id
    assert record.hash == token_hash

    # 2. Lookup by hash
    found = await get_refresh_token_by_hash(session, token_hash)
    assert found == record

    # 2b. Lookup by id
    found_by_id = await get_refresh_token_by_id(session, token_id)
    assert found_by_id == record

    # 3. Lookup active by family
    active = await get_active_refresh_token_by_family(session, family_id)
    assert active == record


@pytest.mark.integration
async def test_family_active_uniqueness(session: AsyncSession, alembic_config: Config) -> None:
    user_id = uuid.uuid4()
    await insert_user(
        session,
        id=user_id,
        email=f"family-user-{user_id}@example.com",
        password_hash="hash",
        created_at=datetime.now(UTC),
        tenant_id=None,
        disabled=False,
    )

    family_id = uuid.uuid4()

    # 1. Insert first active token
    token1_id = uuid.uuid4()
    await insert_refresh_token(
        session,
        id=token1_id,
        user_id=user_id,
        family_id=family_id,
        hash="hash-1",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC),
        revoked_at=None,
        replaced_by=None,
    )

    # 2. Try to insert second active token in same family -> should fail
    async with session.begin_nested():
        with pytest.raises(IntegrityError):
            await insert_refresh_token(
                session,
                id=uuid.uuid4(),
                user_id=user_id,
                family_id=family_id,
                hash="hash-2",
                issued_at=datetime.now(UTC),
                expires_at=datetime.now(UTC),
                revoked_at=None,
                replaced_by=None,
            )

    # 3. Mark token 1 as replaced (using self-reference to satisfy FK and deactivate active index)
    async with session.begin_nested():
        await session.execute(
            update(RefreshTokenRow)
            .where(RefreshTokenRow.id == token1_id)
            .values(replaced_by=token1_id)
        )

    # 4. Now we should be able to insert token2 (the new active one)
    token2_id = uuid.uuid4()
    await insert_refresh_token(
        session,
        id=token2_id,
        user_id=user_id,
        family_id=family_id,
        hash="hash-4",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC),
        revoked_at=None,
        replaced_by=None,
    )

    # Verify we can find token2 as the active one
    active = await get_active_refresh_token_by_family(session, family_id)
    assert active is not None
    assert active.id == token2_id


@pytest.mark.integration
async def test_boundary_checks(session: AsyncSession, alembic_config: Config) -> None:
    # Verify that persistence helpers do not return ORM rows
    user_id = uuid.uuid4()
    email = f"boundary-{user_id}@example.com"

    await insert_user(
        session,
        id=user_id,
        email=email,
        password_hash="hash",
        created_at=datetime.now(UTC),
        tenant_id=None,
        disabled=False,
    )

    user = await get_user_by_email(session, email)
    assert isinstance(user, UserAuthRecord)

    # Check that we can't access session-related state on the domain object
    with pytest.raises(AttributeError):
        _ = user._sa_instance_state  # type: ignore[attr-defined]

    # T-905 §Tests required 6: Boundary checks
    source = inspect.getsource(app.auth.persistence)
    # 1. Imports Base from app.platform.db.base
    assert "from app.platform.db.base import Base" in source
    # 2. Does not import from app.infrastructure.db
    assert "app.infrastructure.db" not in source
    # 3. Does not import app.infrastructure (broader requirement from Finding 2)
    assert "app.infrastructure" not in source
