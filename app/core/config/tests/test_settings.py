# ruff: noqa: S101, PLR2004
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
def test_http_defaults(valid_env_vars: dict[str, str]) -> None:
    get_settings.cache_clear()
    settings = AppSettings()
    assert settings.http.connect_timeout_s == 5.0
    assert settings.http.read_timeout_s == 30.0
    assert settings.http.total_timeout_s == 60.0
    assert settings.http.retry_max_attempts == 3
    assert settings.http.retry_backoff_factor == 0.5


@pytest.mark.unit
def test_http_env_parsing(valid_env_vars: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTP_CONNECT_TIMEOUT_S", "2.5")
    monkeypatch.setenv("HTTP_READ_TIMEOUT_S", "10.0")
    monkeypatch.setenv("HTTP_TOTAL_TIMEOUT_S", "15.0")
    monkeypatch.setenv("HTTP_RETRY_MAX_ATTEMPTS", "5")
    monkeypatch.setenv("HTTP_RETRY_BACKOFF_FACTOR", "1.5")
    settings = AppSettings()
    assert settings.http.connect_timeout_s == 2.5
    assert settings.http.read_timeout_s == 10.0
    assert settings.http.total_timeout_s == 15.0
    assert settings.http.retry_max_attempts == 5
    assert settings.http.retry_backoff_factor == 1.5


@pytest.mark.unit
@pytest.mark.parametrize(
    "env_var",
    [
        "HTTP_CONNECT_TIMEOUT_S",
        "HTTP_READ_TIMEOUT_S",
        "HTTP_TOTAL_TIMEOUT_S",
        "HTTP_RETRY_BACKOFF_FACTOR",
    ],
)
@pytest.mark.parametrize("bad_value", ["0", "-1", "-0.5"])
def test_http_positive_floats_reject_zero_and_negative(
    valid_env_vars: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    env_var: str,
    bad_value: str,
) -> None:
    monkeypatch.setenv(env_var, bad_value)
    with pytest.raises(ValidationError):
        AppSettings()


@pytest.mark.unit
@pytest.mark.parametrize("bad_value", ["0", "-1"])
def test_http_retry_max_attempts_min_one(
    valid_env_vars: dict[str, str], monkeypatch: pytest.MonkeyPatch, bad_value: str
) -> None:
    monkeypatch.setenv("HTTP_RETRY_MAX_ATTEMPTS", bad_value)
    with pytest.raises(ValidationError):
        AppSettings()


@pytest.mark.unit
def test_arq_defaults(valid_env_vars: dict[str, str]) -> None:
    get_settings.cache_clear()
    settings = AppSettings()
    assert settings.arq.queue_name == "default"
    assert settings.arq.max_jobs == 10
    assert settings.arq.job_timeout_s == 300
    assert settings.arq.keep_result_s == 3600


@pytest.mark.unit
def test_arq_env_parsing(valid_env_vars: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARQ_QUEUE_NAME", "docs")
    monkeypatch.setenv("ARQ_MAX_JOBS", "25")
    monkeypatch.setenv("ARQ_JOB_TIMEOUT_S", "120")
    monkeypatch.setenv("ARQ_KEEP_RESULT_S", "0")
    settings = AppSettings()
    assert settings.arq.queue_name == "docs"
    assert settings.arq.max_jobs == 25
    assert settings.arq.job_timeout_s == 120
    assert settings.arq.keep_result_s == 0


@pytest.mark.unit
@pytest.mark.parametrize(
    ("env_var", "bad_value"),
    [
        ("ARQ_MAX_JOBS", "0"),
        ("ARQ_MAX_JOBS", "-1"),
        ("ARQ_JOB_TIMEOUT_S", "0"),
        ("ARQ_JOB_TIMEOUT_S", "-1"),
        ("ARQ_KEEP_RESULT_S", "-1"),
    ],
)
def test_arq_rejects_bad_values(
    valid_env_vars: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    env_var: str,
    bad_value: str,
) -> None:
    monkeypatch.setenv(env_var, bad_value)
    with pytest.raises(ValidationError):
        AppSettings()


@pytest.mark.unit
def test_api_defaults_deny_by_default(valid_env_vars: dict[str, str]) -> None:
    get_settings.cache_clear()
    settings = AppSettings()
    assert settings.api.cors_allowed_origins == ()
    assert settings.api.cors_allow_credentials is False
    assert settings.api.cors_allowed_methods == ("GET", "POST")
    assert settings.api.cors_allowed_headers == (
        "Authorization",
        "Content-Type",
        "X-Request-ID",
    )
    assert settings.api.security_headers_enabled is True


@pytest.mark.unit
def test_api_cors_allowed_origins_parses_csv(
    valid_env_vars: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("API_CORS_ALLOWED_ORIGINS", "https://a.example.com, https://b.example.com")
    settings = AppSettings()
    assert settings.api.cors_allowed_origins == (
        "https://a.example.com",
        "https://b.example.com",
    )


@pytest.mark.unit
def test_api_cors_methods_and_headers_env(
    valid_env_vars: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("API_CORS_ALLOWED_METHODS", "GET,POST,PUT")
    monkeypatch.setenv("API_CORS_ALLOWED_HEADERS", "Authorization,X-Custom")
    monkeypatch.setenv("API_CORS_ALLOW_CREDENTIALS", "true")
    monkeypatch.setenv("API_SECURITY_HEADERS_ENABLED", "false")
    settings = AppSettings()
    assert settings.api.cors_allowed_methods == ("GET", "POST", "PUT")
    assert settings.api.cors_allowed_headers == ("Authorization", "X-Custom")
    assert settings.api.cors_allow_credentials is True
    assert settings.api.security_headers_enabled is False


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


@pytest.mark.unit
def test_argon2_defaults(valid_env_vars: dict[str, str]) -> None:
    get_settings.cache_clear()
    settings = AppSettings()
    assert settings.argon2.time_cost == 2
    assert settings.argon2.memory_cost == 19456
    assert settings.argon2.parallelism == 1
    assert settings.argon2.hash_len == 32
    assert settings.argon2.salt_len == 16


@pytest.mark.unit
def test_argon2_env_parsing(
    valid_env_vars: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARGON2_TIME_COST", "3")
    monkeypatch.setenv("ARGON2_MEMORY_COST", "65536")
    monkeypatch.setenv("ARGON2_PARALLELISM", "4")
    monkeypatch.setenv("ARGON2_HASH_LEN", "64")
    monkeypatch.setenv("ARGON2_SALT_LEN", "32")
    settings = AppSettings()
    assert settings.argon2.time_cost == 3
    assert settings.argon2.memory_cost == 65536
    assert settings.argon2.parallelism == 4
    assert settings.argon2.hash_len == 64
    assert settings.argon2.salt_len == 32


@pytest.mark.unit
def test_argon2_nested_env_parsing(
    valid_env_vars: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARGON2__TIME_COST", "4")
    settings = AppSettings()
    assert settings.argon2.time_cost == 4


@pytest.mark.unit
@pytest.mark.parametrize(
    "env_var",
    [
        "ARGON2_TIME_COST",
        "ARGON2_MEMORY_COST",
        "ARGON2_PARALLELISM",
        "ARGON2_HASH_LEN",
        "ARGON2_SALT_LEN",
    ],
)
@pytest.mark.parametrize("bad_value", ["0", "-1"])
def test_argon2_rejects_non_positive_integers(
    valid_env_vars: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    env_var: str,
    bad_value: str,
) -> None:
    monkeypatch.setenv(env_var, bad_value)
    with pytest.raises(ValidationError):
        AppSettings()
