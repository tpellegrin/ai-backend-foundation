# ruff: noqa: S101
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import AliasChoices, BaseModel, ValidationError

from app.core.config.settings import AppSettings, get_settings


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
def test_settings_boot_valid(valid_env_vars: dict[str, str]) -> None:
    get_settings.cache_clear()
    settings = AppSettings()
    assert settings.app.env == "dev"  # Default
    assert (
        settings.db.url.unicode_string()
        == "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
    )
    assert settings.governance.monthly_budget_usd == Decimal("100.0")
    assert settings.governance.model_allowlist == ("gpt-4o", "gpt-4o-mini")
    assert settings.blob.backend == "local"


@pytest.mark.unit
def test_settings_missing_jwt_key(
    valid_env_vars: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("JWT_PRIVATE_KEY")
    with pytest.raises(ValidationError) as excinfo:
        AppSettings()
    assert "JWT_PRIVATE_KEY" in str(excinfo.value).upper() or "jwt__private_key" in str(
        excinfo.value
    )


@pytest.mark.unit
def test_blob_storage_backend_local_only(
    valid_env_vars: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BLOB_STORAGE_BACKEND", "s3")
    with pytest.raises(ValidationError) as excinfo:
        AppSettings()
    assert "Input should be 'local'" in str(excinfo.value)


@pytest.mark.unit
def test_blob_storage_local_dir_required(
    valid_env_vars: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("BLOB_LOCAL_DIR")
    with pytest.raises(ValidationError) as excinfo:
        AppSettings()
    assert "local_dir" in str(excinfo.value).lower()


@pytest.mark.unit
def test_governance_budget_non_negative(
    valid_env_vars: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_MONTHLY_BUDGET_USD", "-1")
    with pytest.raises(ValidationError):
        AppSettings()


@pytest.mark.unit
def test_get_settings_caching(valid_env_vars: dict[str, str]) -> None:
    get_settings.cache_clear()
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


@pytest.mark.unit
def test_env_example_superset() -> None:
    env_example_path = Path(".env.example")
    assert env_example_path.exists()

    with open(env_example_path) as f:
        example_content = f.read()

    example_keys = set()
    for raw_line in example_content.splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#") and "=" in line:
            key = line.split("=")[0].strip()
            example_keys.add(key)

    def get_all_upper_aliases(model: type[BaseModel]) -> set[str]:
        aliases = set()
        for field in model.model_fields.values():
            if field.validation_alias:
                if isinstance(field.validation_alias, AliasChoices):
                    for choice in field.validation_alias.choices:
                        if isinstance(choice, str) and choice.isupper():
                            aliases.add(choice)
                elif isinstance(field.validation_alias, str) and field.validation_alias.isupper():
                    aliases.add(field.validation_alias)

            # If it's a nested model, recurse
            field_type: Any = field.annotation
            # handle Optional/Union
            types_to_check = []
            if hasattr(field_type, "__args__"):
                types_to_check.extend(field_type.__args__)
            else:
                types_to_check.append(field_type)

            for t in types_to_check:
                if isinstance(t, type) and issubclass(t, BaseModel):
                    aliases.update(get_all_upper_aliases(t))
        return aliases

    app_aliases = get_all_upper_aliases(AppSettings)

    # Some variables might be optional or have defaults, but they should still be in .env.example
    # per T-109 requirement.
    missing = app_aliases - example_keys
    assert not missing, f"Env vars {missing} are used in code but missing from .env.example"
