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
    get_refresh_token_family_state,
    get_user_by_email,
    get_user_by_id,
    insert_refresh_token,
    insert_user,
    mark_refresh_token_replaced,
    revoke_refresh_token,
    revoke_refresh_token_family,
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


@pytest.mark.integration
async def test_mark_refresh_token_replaced(session: AsyncSession, alembic_config: Config) -> None:
    user_id = uuid.uuid4()
    await insert_user(
        session,
        id=user_id,
        email=f"replace-{user_id}@example.com",
        password_hash="hash",
        created_at=datetime.now(UTC),
        tenant_id=None,
        disabled=False,
    )

    token1_id = uuid.uuid4()
    token2_id = uuid.uuid4()
    revoked_at = datetime.now(UTC)

    # We must insert token2 first if it is to replace token1 (because of FK)
    # OR we can just use token1_id as replaced_by for testing purposes if FK allows self-ref
    # Actually, let's insert token2.
    await insert_refresh_token(
        session,
        id=token2_id,
        user_id=user_id,
        family_id=uuid.uuid4(),
        hash="hash-2",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC),
        revoked_at=None,
        replaced_by=None,
    )

    await insert_refresh_token(
        session,
        id=token1_id,
        user_id=user_id,
        family_id=uuid.uuid4(),
        hash="hash-1",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC),
        revoked_at=None,
        replaced_by=None,
    )

    # Act
    record = await mark_refresh_token_replaced(
        session,
        token_id=token1_id,
        replaced_by=token2_id,
        revoked_at=revoked_at,
    )

    # Assert
    assert record is not None
    assert record.id == token1_id
    assert record.replaced_by == token2_id
    assert record.revoked_at == revoked_at

    # Verify in DB
    found = await get_refresh_token_by_id(session, token1_id)
    assert found is not None
    assert found.replaced_by == token2_id
    assert found.revoked_at == revoked_at


@pytest.mark.integration
async def test_revoke_refresh_token(session: AsyncSession, alembic_config: Config) -> None:
    user_id = uuid.uuid4()
    await insert_user(
        session,
        id=user_id,
        email=f"revoke-{user_id}@example.com",
        password_hash="hash",
        created_at=datetime.now(UTC),
        tenant_id=None,
        disabled=False,
    )

    token_id = uuid.uuid4()
    revoked_at = datetime.now(UTC)

    await insert_refresh_token(
        session,
        id=token_id,
        user_id=user_id,
        family_id=uuid.uuid4(),
        hash="hash-1",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC),
        revoked_at=None,
        replaced_by=None,
    )

    # Act
    record = await revoke_refresh_token(
        session,
        token_id=token_id,
        revoked_at=revoked_at,
    )

    # Assert
    assert record is not None
    assert record.id == token_id
    assert record.revoked_at == revoked_at

    # Verify in DB
    found = await get_refresh_token_by_id(session, token_id)
    assert found is not None
    assert found.revoked_at == revoked_at


@pytest.mark.integration
async def test_revoke_refresh_token_family(session: AsyncSession, alembic_config: Config) -> None:
    user_id = uuid.uuid4()
    await insert_user(
        session,
        id=user_id,
        email=f"family-rev-{user_id}@example.com",
        password_hash="hash",
        created_at=datetime.now(UTC),
        tenant_id=None,
        disabled=False,
    )

    family_id = uuid.uuid4()
    revoked_at = datetime.now(UTC)

    # Insert 3 tokens in family: t2 replaces t1, t3 is already revoked and replaces t2.
    # We must insert in reverse order of replacement to satisfy FK if we use immediate FKs.
    # Actually, SQLAlchemy with asyncpg might not care about order if we don't commit,
    # but the DB enforces it on flush if the constraint is not DEFERRABLE.
    # Let's just insert them with replaced_by=None first and then update, or insert in order.

    t3_id = uuid.uuid4()
    already_revoked_at = datetime.now(UTC) - timedelta(hours=1)
    await insert_refresh_token(
        session,
        id=t3_id,
        user_id=user_id,
        family_id=family_id,
        hash="h3",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC),
        revoked_at=already_revoked_at,
        replaced_by=None,
    )

    t2_id = uuid.uuid4()
    await insert_refresh_token(
        session,
        id=t2_id,
        user_id=user_id,
        family_id=family_id,
        hash="h2",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC),
        revoked_at=None,
        replaced_by=t3_id,  # t3 replaces t2
    )

    t1_id = uuid.uuid4()
    await insert_refresh_token(
        session,
        id=t1_id,
        user_id=user_id,
        family_id=family_id,
        hash="h1",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC),
        revoked_at=None,
        replaced_by=t2_id,  # t2 replaces t1
    )

    # Act
    count = await revoke_refresh_token_family(
        session,
        family_id=family_id,
        revoked_at=revoked_at,
    )

    # Assert
    assert count == 2  # noqa: PLR2004  # t1 and t2 should be revoked. t3 was already revoked.

    # Verify in DB
    state = await get_refresh_token_family_state(session, family_id=family_id)
    assert len(state) == 3  # noqa: PLR2004
    for rec in state:
        if rec.id == t3_id:
            assert rec.revoked_at == already_revoked_at
        else:
            assert rec.revoked_at == revoked_at


@pytest.mark.integration
async def test_get_refresh_token_family_state(
    session: AsyncSession, alembic_config: Config
) -> None:
    user_id = uuid.uuid4()
    await insert_user(
        session,
        id=user_id,
        email=f"family-state-{user_id}@example.com",
        password_hash="hash",
        created_at=datetime.now(UTC),
        tenant_id=None,
        disabled=False,
    )

    family_id = uuid.uuid4()
    t1_id = uuid.uuid4()
    await insert_refresh_token(
        session,
        id=t1_id,
        user_id=user_id,
        family_id=family_id,
        hash="h1",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC),
        revoked_at=None,
        replaced_by=None,
    )

    # Act
    state = await get_refresh_token_family_state(session, family_id=family_id)

    # Assert
    assert len(state) == 1
    assert isinstance(state[0], RefreshTokenRecord)
    assert state[0].id == t1_id
