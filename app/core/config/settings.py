from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, cast

from pydantic import (
    AliasChoices,
    Field,
    HttpUrl,
    PostgresDsn,
    RedisDsn,
    SecretStr,
    field_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class AppMeta(BaseSettings):
    env: Literal["dev", "test", "staging", "prod"] = Field(
        default="dev", validation_alias=AliasChoices("APP_ENV", "app__env")
    )
    service_name: str = Field(
        default="ai-backend-foundation",
        validation_alias=AliasChoices("app__service_name"),
    )


class Logging(BaseSettings):
    level: str = Field(default="INFO", validation_alias=AliasChoices("LOG_LEVEL", "logging__level"))


class Database(BaseSettings):
    url: PostgresDsn = Field(validation_alias=AliasChoices("DATABASE_URL", "db__url"))


class Redis(BaseSettings):
    url: RedisDsn = Field(validation_alias=AliasChoices("REDIS_URL", "redis__url"))
    arq_url: RedisDsn = Field(validation_alias=AliasChoices("ARQ_REDIS_URL", "redis__arq_url"))


class Jwt(BaseSettings):
    private_key: SecretStr = Field(
        validation_alias=AliasChoices("JWT_PRIVATE_KEY", "jwt__private_key")
    )
    public_key: SecretStr = Field(
        validation_alias=AliasChoices("JWT_PUBLIC_KEY", "jwt__public_key")
    )
    issuer: str = Field(validation_alias=AliasChoices("JWT_ISSUER", "jwt__issuer"))
    audience: str = Field(validation_alias=AliasChoices("JWT_AUDIENCE", "jwt__audience"))
    access_ttl_seconds: int = Field(
        default=900, validation_alias=AliasChoices("jwt__access_ttl_seconds")
    )
    refresh_ttl_seconds: int = Field(
        default=60 * 60 * 24 * 14,
        validation_alias=AliasChoices("jwt__refresh_ttl_seconds"),
    )


class OpenAI(BaseSettings):
    api_key: SecretStr = Field(validation_alias=AliasChoices("OPENAI_API_KEY", "openai__api_key"))
    base_url: HttpUrl | None = Field(
        default=None, validation_alias=AliasChoices("OPENAI_BASE_URL", "openai__base_url")
    )
    chat_model: str = Field(
        validation_alias=AliasChoices("OPENAI_CHAT_MODEL", "openai__chat_model")
    )
    embedding_model: str = Field(
        validation_alias=AliasChoices("OPENAI_EMBEDDING_MODEL", "openai__embedding_model")
    )


class Http(BaseSettings):
    connect_timeout_s: float = Field(
        default=5.0,
        gt=0,
        validation_alias=AliasChoices("HTTP_CONNECT_TIMEOUT_S", "http__connect_timeout_s"),
    )
    read_timeout_s: float = Field(
        default=30.0,
        gt=0,
        validation_alias=AliasChoices("HTTP_READ_TIMEOUT_S", "http__read_timeout_s"),
    )
    total_timeout_s: float = Field(
        default=60.0,
        gt=0,
        validation_alias=AliasChoices("HTTP_TOTAL_TIMEOUT_S", "http__total_timeout_s"),
    )
    retry_max_attempts: int = Field(
        default=3,
        ge=1,
        validation_alias=AliasChoices("HTTP_RETRY_MAX_ATTEMPTS", "http__retry_max_attempts"),
    )
    retry_backoff_factor: float = Field(
        default=0.5,
        gt=0,
        validation_alias=AliasChoices("HTTP_RETRY_BACKOFF_FACTOR", "http__retry_backoff_factor"),
    )


class Arq(BaseSettings):
    queue_name: str = Field(
        default="default",
        validation_alias=AliasChoices("ARQ_QUEUE_NAME", "arq__queue_name"),
    )
    max_jobs: int = Field(
        default=10,
        ge=1,
        validation_alias=AliasChoices("ARQ_MAX_JOBS", "arq__max_jobs"),
    )
    job_timeout_s: int = Field(
        default=300,
        ge=1,
        validation_alias=AliasChoices("ARQ_JOB_TIMEOUT_S", "arq__job_timeout_s"),
    )
    keep_result_s: int = Field(
        default=3600,
        ge=0,
        validation_alias=AliasChoices("ARQ_KEEP_RESULT_S", "arq__keep_result_s"),
    )


def _parse_csv_tuple(v: object) -> tuple[str, ...]:
    if isinstance(v, str):
        return tuple(s.strip() for s in v.split(",") if s.strip())
    if isinstance(v, (list, tuple)):
        return tuple(v)
    return cast(tuple[str, ...], v)


class Api(BaseSettings):
    cors_allowed_origins: Annotated[tuple[str, ...], NoDecode] = Field(
        default=(),
        validation_alias=AliasChoices("API_CORS_ALLOWED_ORIGINS", "api__cors_allowed_origins"),
    )
    cors_allow_credentials: bool = Field(
        default=False,
        validation_alias=AliasChoices("API_CORS_ALLOW_CREDENTIALS", "api__cors_allow_credentials"),
    )
    cors_allowed_methods: Annotated[tuple[str, ...], NoDecode] = Field(
        default=("GET", "POST"),
        validation_alias=AliasChoices("API_CORS_ALLOWED_METHODS", "api__cors_allowed_methods"),
    )
    cors_allowed_headers: Annotated[tuple[str, ...], NoDecode] = Field(
        default=("Authorization", "Content-Type", "X-Request-ID"),
        validation_alias=AliasChoices("API_CORS_ALLOWED_HEADERS", "api__cors_allowed_headers"),
    )
    security_headers_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "API_SECURITY_HEADERS_ENABLED", "api__security_headers_enabled"
        ),
    )

    @field_validator(
        "cors_allowed_origins",
        "cors_allowed_methods",
        "cors_allowed_headers",
        mode="before",
    )
    @classmethod
    def _split_csv(cls, v: object) -> tuple[str, ...]:
        return _parse_csv_tuple(v)


class BlobStorage(BaseSettings):
    backend: Literal["local"] = Field(
        default="local", validation_alias=AliasChoices("BLOB_STORAGE_BACKEND", "blob__backend")
    )
    local_dir: Path = Field(validation_alias=AliasChoices("BLOB_LOCAL_DIR", "blob__local_dir"))


class Otel(BaseSettings):
    endpoint: HttpUrl | None = Field(
        default=None, validation_alias=AliasChoices("OTEL_EXPORTER_OTLP_ENDPOINT", "otel__endpoint")
    )


class Governance(BaseSettings):
    monthly_budget_usd: Decimal = Field(
        ge=0,
        validation_alias=AliasChoices("LLM_MONTHLY_BUDGET_USD", "governance__monthly_budget_usd"),
    )
    warning_threshold: float = Field(
        default=0.8,
        validation_alias=AliasChoices("governance__warning_threshold"),
    )
    model_allowlist: Annotated[tuple[str, ...], NoDecode] = Field(
        validation_alias=AliasChoices("LLM_MODEL_ALLOWLIST", "governance__model_allowlist")
    )

    @field_validator("model_allowlist", mode="before")
    @classmethod
    def ensure_tuple(cls, v: object) -> tuple[str, ...]:
        if isinstance(v, str):
            return tuple(s.strip() for s in v.split(",") if s.strip())
        if isinstance(v, (list, tuple)):
            return tuple(v)
        return cast(tuple[str, ...], v)


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    app: AppMeta = Field(default_factory=AppMeta)
    logging: Logging = Field(default_factory=Logging)
    db: Database = Field(default_factory=Database)
    redis: Redis = Field(default_factory=Redis)
    jwt: Jwt = Field(default_factory=Jwt)
    openai: OpenAI = Field(default_factory=OpenAI)
    blob: BlobStorage = Field(default_factory=BlobStorage)
    otel: Otel = Field(default_factory=Otel)
    governance: Governance = Field(default_factory=Governance)
    http: Http = Field(default_factory=Http)
    arq: Arq = Field(default_factory=Arq)
    api: Api = Field(default_factory=Api)


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
