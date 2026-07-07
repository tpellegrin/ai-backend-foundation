# ruff: noqa: S105, PLR2004, SIM117, PLC0415
import uuid

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

from app.core.config.settings import get_settings as bootstrap_settings
from app.core.lifespan import lifespan
from app.main.app_factory import create_app


@pytest.fixture(scope="module")
def postgres_container() -> PostgresContainer:
    with PostgresContainer("ankane/pgvector:latest") as postgres:
        yield postgres


@pytest.fixture
def alembic_config(postgres_container: PostgresContainer, monkeypatch: pytest.MonkeyPatch) -> None:
    db_url = postgres_container.get_connection_url().replace("psycopg2", "asyncpg")
    monkeypatch.setenv("DATABASE_URL", db_url)
    bootstrap_settings.cache_clear()

    from alembic.config import Config

    from alembic import command

    config = Config("alembic.ini")
    command.upgrade(config, "head")


@pytest.fixture
async def app(
    alembic_config: None, postgres_container: PostgresContainer, monkeypatch: pytest.MonkeyPatch
) -> AsyncClient:
    # 1. Generate real RSA keys for JWT
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )

    monkeypatch.setenv("JWT_PRIVATE_KEY", private_pem)
    monkeypatch.setenv("JWT_PUBLIC_KEY", public_pem)
    monkeypatch.setenv("JWT_ISSUER", "ai-backend-foundation-test")
    monkeypatch.setenv("JWT_AUDIENCE", "ai-backend-foundation-test")

    # Reload settings to pick up new env vars
    bootstrap_settings.cache_clear()

    app = create_app()

    async with lifespan(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client


@pytest.mark.integration
async def test_refresh_token_rotation_integration(app: AsyncClient) -> None:
    # 1. Register
    email = f"test-{uuid.uuid4()}@example.com"
    password = "password12345"
    reg_resp = await app.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert reg_resp.status_code == 201

    # 2. Login
    login_resp = await app.post(
        "/api/v1/auth/login", json={"username": email, "password": password}
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    refresh_token = tokens["refresh_token"]

    # 3. Refresh (Rotation)
    # This is the critical part that tests T-906B:
    # It involves a DB transaction that updates the old token and inserts a new one.
    refresh_resp = await app.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 200
    new_tokens = refresh_resp.json()
    new_refresh_token = new_tokens["refresh_token"]
    assert new_refresh_token != refresh_token

    # 4. Attempt to use old refresh token (Reuse detection)
    reuse_resp = await app.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    # T-908/T-906B: reuse should revoke the family and return 401
    assert reuse_resp.status_code == 401

    # 5. Verify that the NEW refresh token is also revoked due to reuse detection
    second_refresh_resp = await app.post(
        "/api/v1/auth/refresh", json={"refresh_token": new_refresh_token}
    )
    assert second_refresh_resp.status_code == 401
