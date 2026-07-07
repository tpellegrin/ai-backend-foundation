# ruff: noqa: S101
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI

from app.auth.adapters.argon2_hasher import Argon2PasswordHasher
from app.auth.adapters.jwt_signer import JwtSigner
from app.auth.ports import PasswordHasher, TokenSigner
from app.core.config.settings import get_settings
from app.core.container import Container
from app.core.lifespan import _on_startup, lifespan
from app.core.wiring.auth import setup_password_hasher, setup_token_signer
from app.observability.health import ProbeRegistry


@pytest.fixture
def rsa_keys() -> tuple[str, str]:
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return private_pem, public_pem


@pytest.fixture
def valid_env_vars(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    vars_dict = {
        "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
        "REDIS_URL": "redis://localhost:6379/0",
        "ARQ_REDIS_URL": "redis://localhost:6379/1",
        "JWT_PRIVATE_KEY": "fake-private-key",
        "JWT_PUBLIC_KEY": "fake-public-key",
        "JWT_ISSUER": "ai-backend-foundation",
        "JWT_AUDIENCE": "ai-backend-foundation",
        "OPENAI_API_KEY": "sk-placeholder",
        "OPENAI_CHAT_MODEL": "gpt-4o",
        "OPENAI_EMBEDDING_MODEL": "text-embedding-3-small",
        "BLOB_STORAGE_BACKEND": "local",
        "BLOB_LOCAL_DIR": "./.storage",
        "LLM_MONTHLY_BUDGET_USD": "100.0",
        "LLM_MODEL_ALLOWLIST": "gpt-4o,gpt-4o-mini",
    }
    for k, v in vars_dict.items():
        monkeypatch.setenv(k, v)
    return vars_dict


@pytest.mark.unit
def test_setup_password_hasher(
    valid_env_vars: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARGON2_TIME_COST", "3")
    get_settings.cache_clear()
    settings = get_settings()

    hasher = setup_password_hasher(settings)

    assert isinstance(hasher, PasswordHasher)
    assert isinstance(hasher, Argon2PasswordHasher)
    # verify it works
    h = hasher.hash("password")
    assert hasher.verify("password", h)


@pytest.mark.unit
def test_setup_token_signer(
    rsa_keys: tuple[str, str], valid_env_vars: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    private_pem, public_pem = rsa_keys
    monkeypatch.setenv("JWT_PRIVATE_KEY", private_pem)
    monkeypatch.setenv("JWT_PUBLIC_KEY", public_pem)
    monkeypatch.setenv("JWT_ISSUER", "test-issuer")
    monkeypatch.setenv("JWT_AUDIENCE", "test-audience")

    get_settings.cache_clear()
    settings = get_settings()

    signer = setup_token_signer(settings)

    assert isinstance(signer, TokenSigner)
    assert isinstance(signer, JwtSigner)
    # verify it works
    token = signer.sign({"sub": "user"})
    claims = signer.verify(token)
    assert claims["sub"] == "user"


@pytest.mark.unit
async def test_on_startup_populates_auth(
    rsa_keys: tuple[str, str], valid_env_vars: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that _on_startup populates auth fields in the container."""
    private_pem, public_pem = rsa_keys
    monkeypatch.setenv("JWT_PRIVATE_KEY", private_pem)
    monkeypatch.setenv("JWT_PUBLIC_KEY", public_pem)

    get_settings.cache_clear()
    settings = get_settings()

    container = Container(settings=settings, probe_registry=ProbeRegistry())

    # Mock other setup functions to avoid I/O
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    with (
        patch("app.core.lifespan.setup_db", return_value=(mock_engine, MagicMock())),
        patch("app.core.lifespan.DBProbe", return_value=MagicMock()),
        patch("app.core.lifespan.setup_storage", return_value=MagicMock()),
    ):
        await _on_startup(container)

    assert container.password_hasher is not None
    assert container.token_signer is not None
    assert container.clock is not None
    assert isinstance(container.password_hasher, PasswordHasher)
    assert isinstance(container.token_signer, TokenSigner)


@pytest.mark.integration
async def test_auth_wiring_in_lifespan(
    rsa_keys: tuple[str, str], valid_env_vars: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that auth dependencies are wired in the container during lifespan startup."""
    private_pem, public_pem = rsa_keys
    monkeypatch.setenv("JWT_PRIVATE_KEY", private_pem)
    monkeypatch.setenv("JWT_PUBLIC_KEY", public_pem)

    get_settings.cache_clear()
    settings = get_settings()

    container = Container(settings=settings, probe_registry=ProbeRegistry())
    app = FastAPI(lifespan=lifespan)
    app.state.container = container

    # Mock all external resource setup/shutdown
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    with (
        patch("app.core.lifespan.setup_db", return_value=(mock_engine, MagicMock())),
        patch("app.core.lifespan.DBProbe", return_value=MagicMock()),
        patch("app.core.lifespan.setup_storage", return_value=MagicMock()),
        patch("app.core.lifespan.setup_redis_client", return_value=MagicMock()),
        patch("app.core.lifespan.setup_cache", return_value=MagicMock()),
        patch("app.core.lifespan.RedisProbe", return_value=MagicMock()),
        patch("app.core.lifespan.shutdown_redis", new_callable=AsyncMock),
    ):
        async with lifespan(app):
            assert container.password_hasher is not None
            assert container.token_signer is not None
            assert container.clock is not None
            assert isinstance(container.password_hasher, PasswordHasher)
            assert isinstance(container.token_signer, TokenSigner)
            assert app.state.ready is True
