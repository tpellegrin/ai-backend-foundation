# ADR-0013: Config strategy — Pydantic Settings, composed

- **Status**: Accepted
- **Date**: 2026-06-29

## Context

Configuration is a source of subtle production bugs: missing env vars, silent defaults, drifting types, secrets logged by accident. Many codebases scatter `os.getenv(...)` everywhere and pay for it forever. We make config a typed, validated, observable boundary.

## Decision

- All settings are **Pydantic `BaseSettings`** subclasses, organized **by concern**:
  - `AppMetaSettings` (name, version, environment)
  - `LoggingSettings`, `ObservabilitySettings`
  - `DatabaseSettings`, `RedisSettings`, `StorageSettings`, `QueueSettings`
  - `AuthSettings`
  - `LLMSettings`, `EmbeddingSettings`, `VectorStoreSettings`, `PromptSettings`
  - `ApiSettings` (cors origins, rate limits, idempotency TTLs)
- A single composite **`AppSettings`** holds them all and is the only thing the rest of the app receives. Built once in `app.core.config.load_settings()`.
- **Sources** (in order of precedence): explicit env vars > `.env.<environment>` > defaults. Secret managers (AWS Secrets Manager, GCP Secret Manager, Vault) are integrated via env injection at deploy time; there is no SDK coupling in code.
- **`os.environ` is read only inside `app.core.config`.** Anywhere else is a lint failure.
- **No magic values.** Defaults are explicit. Production-only constraints (e.g. "secret must be set in `production`") are validated at startup via `model_validator`.
- **Fail fast.** The app refuses to boot on a configuration error and prints a structured, human-friendly diagnostic.
- **Secrets are never logged.** Settings fields holding secrets use `pydantic.SecretStr`. Logging configurations explicitly redact `SecretStr` fields.

## Consequences

**Positive**: a misconfiguration becomes a crash at boot, not a 3AM page; the type system documents what each setting is; new environments mean a new `.env.<environment>`, not code changes.
**Negative**: a few minutes of upfront definition per setting.
**Neutral**: settings classes are not free of layering — `LLMSettings` carries provider-specific subfields; we keep them flat with prefix conventions to remain readable.

## Alternatives considered

- **`os.getenv` ad-hoc**: rejected — see context.
- **Dynaconf / Hydra**: powerful but heavy and opinionated; Pydantic Settings is enough and aligns with the rest of the stack.
