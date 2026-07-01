# ruff: noqa: S101
import pytest
from pydantic import ValidationError

from app.core.config.settings import AppSettings, get_settings


@pytest.fixture
def valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sets up a minimal valid environment."""
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
        "BLOB_LOCAL_DIR": "./.storage",
        "LLM_MONTHLY_BUDGET_USD": "100.0",
        "LLM_MODEL_ALLOWLIST": "gpt-4o,gpt-4o-mini",
    }
    for k, v in vars_dict.items():
        monkeypatch.setenv(k, v)


@pytest.mark.unit
@pytest.mark.parametrize(
    "missing_var",
    [
        "DATABASE_URL",
        "REDIS_URL",
        "ARQ_REDIS_URL",
        "JWT_PRIVATE_KEY",
        "JWT_PUBLIC_KEY",
        "JWT_ISSUER",
        "JWT_AUDIENCE",
        "OPENAI_API_KEY",
        "OPENAI_CHAT_MODEL",
        "OPENAI_EMBEDDING_MODEL",
        "BLOB_LOCAL_DIR",
        "LLM_MONTHLY_BUDGET_USD",
        "LLM_MODEL_ALLOWLIST",
    ],
)
def test_settings_fails_on_missing_var(
    valid_env: None, monkeypatch: pytest.MonkeyPatch, missing_var: str
) -> None:
    """Assert startup fails on missing critical env vars."""
    get_settings.cache_clear()
    monkeypatch.delenv(missing_var, raising=False)
    with pytest.raises(ValidationError) as excinfo:
        AppSettings()

    # Verify the error message points to the missing variable
    # Pydantic errors can use the alias or the field name.
    # We check for the alias (which is the env var name) in the error string.
    assert missing_var.lower() in str(excinfo.value).lower()
