# ruff: noqa: PLR2004, SIM117, PLC0415, S105
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
async def client(
    alembic_config: None, postgres_container: PostgresContainer, monkeypatch: pytest.MonkeyPatch
) -> AsyncClient:
    # Generate RSA keys for JWT
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

    bootstrap_settings.cache_clear()
    app = create_app()

    async with lifespan(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client


@pytest.mark.integration
async def test_get_users_me_lazy_creation(client: AsyncClient) -> None:
    # 1. Register a new user
    email = f"test-{uuid.uuid4()}@example.com"
    password = "password12345"
    reg_resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": password}
    )
    assert reg_resp.status_code == 201

    # 2. Login to get tokens
    login_resp = await client.post(
        "/api/v1/auth/login", json={"username": email, "password": password}
    )
    assert login_resp.status_code == 200
    access_token = login_resp.json()["access_token"]

    # 3. Get /users/me for the first time (triggers lazy creation)
    request_id = str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Request-ID": request_id,
    }
    me_resp1 = await client.get("/api/v1/users/me", headers=headers)
    assert me_resp1.status_code == 200
    assert me_resp1.headers["X-Request-ID"] == request_id
    profile1 = me_resp1.json()
    assert profile1["email"] == email

    # 4. Get /users/me again (should return same row)
    me_resp2 = await client.get("/api/v1/users/me", headers=headers)
    assert me_resp2.status_code == 200
    assert me_resp2.headers["X-Request-ID"] == request_id
    profile2 = me_resp2.json()
    assert profile2["id"] == profile1["id"]
    assert profile2["email"] == profile1["email"]


@pytest.mark.integration
async def test_get_users_me_unauthenticated(client: AsyncClient) -> None:
    request_id = str(uuid.uuid4())
    response = await client.get("/api/v1/users/me", headers={"X-Request-ID": request_id})
    assert response.status_code == 401
    assert response.headers["X-Request-ID"] == request_id

    data = response.json()
    assert data["code"] == "authentication-error"
    assert data["status"] == 401
    assert data["request_id"] == request_id
    assert "type" in data
    assert "title" in data
    assert "detail" in data
