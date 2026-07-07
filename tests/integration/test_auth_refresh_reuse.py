# ruff: noqa: S105, I001
import uuid
from collections.abc import AsyncGenerator, Generator

import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

from app.auth.adapters.argon2_hasher import Argon2PasswordHasher
from app.auth.adapters.jwt_signer import JwtSigner
from app.auth.domain import Credentials, RefreshReuseDetectedError, InvalidCredentialsError
from app.auth.service import AuthService
from app.core.config import get_settings
from app.core.config.settings import Argon2
from app.infrastructure.db.engine import create_engine_from, create_session_factory
from app.observability.logging import configure_logging
from app.shared.clock import SystemClock


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
async def session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


@pytest.fixture
async def session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession]:
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def rsa_keys() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem.decode(), public_pem.decode()


@pytest.fixture
def auth_service(session: AsyncSession, rsa_keys: tuple[str, str]) -> AuthService:
    argon2_settings = Argon2()
    hasher = Argon2PasswordHasher(
        time_cost=argon2_settings.time_cost,
        memory_cost=argon2_settings.memory_cost,
        parallelism=argon2_settings.parallelism,
        hash_len=argon2_settings.hash_len,
        salt_len=argon2_settings.salt_len,
    )

    private_key, public_key = rsa_keys
    signer = JwtSigner(
        private_key=private_key,
        public_key=public_key,
        issuer="test-issuer",
        audience="test-audience",
        access_ttl_seconds=900,
    )
    return AuthService(session, hasher, signer, SystemClock())


@pytest.mark.integration
async def test_refresh_token_reuse_revokes_family(
    auth_service: AuthService, alembic_config: Config
) -> None:
    # 1. Register and Login
    email = f"reuse-{uuid.uuid4()}@example.com"
    password = "password123"
    await auth_service.register(email, password)
    _, rt1 = await auth_service.login(Credentials(username=email, password=password))

    # 2. First refresh (RT1 -> RT2)
    _, rt2 = await auth_service.refresh(rt1.token)

    # 3. Reuse RT1 (Reuse detected!)
    with pytest.raises(RefreshReuseDetectedError):
        await auth_service.refresh(rt1.token)

    # 4. Verify RT2 is also revoked (RT2 is part of the same family)
    with pytest.raises(InvalidCredentialsError) as excinfo:
        await auth_service.refresh(rt2.token)
    assert "revoked" in str(excinfo.value.detail).lower()


@pytest.mark.integration
async def test_refresh_token_reuse_audit_log_format(
    auth_service: AuthService, alembic_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    # Configure logging to capture output
    configure_logging(level="INFO", json=True)

    email = f"audit-{uuid.uuid4()}@example.com"
    password = "password123"
    await auth_service.register(email, password)
    _, rt1 = await auth_service.login(Credentials(username=email, password=password))

    # First refresh
    await auth_service.refresh(rt1.token)

    # Reuse RT1
    with pytest.raises(RefreshReuseDetectedError):
        await auth_service.refresh(rt1.token)

    # Check audit log in stdout/stderr
    captured = capsys.readouterr()
    combined_output = captured.out + captured.err

    assert "refresh_token_reuse_detected" in combined_output
    assert "user_id" in combined_output
    assert "family_id" in combined_output
    assert "token_id" in combined_output
