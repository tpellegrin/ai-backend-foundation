# IMPLEMENTATION_PLAN.md — Phase 2 of `ai-backend-foundation`

> Authoritative, sequential, file-scoped, test-driven task list for implementing Phase 2.
> This document is binding for the implementing model. It must not be re-interpreted or re-designed.
> Source of architectural truth: `AGENTS.md`, `docs/phase-2-revision/02..07`, `docs/adr/0018..0022`.

---

## 1. Overview

`ai-backend-foundation` Phase 2 delivers the production substrate plus **one** end-to-end golden-path vertical slice:

```
POST /api/v1/documents
   → store metadata + blob
   → enqueue ingestion job (Arq)
   → parse → chunk → embed (OpenAI) → store vectors (pgvector)
   → document status becomes "ready"

POST /api/v1/rag/ask
   → embed query → retrieve top-k → attach citations
   → ai_governance.check_call_allowed
   → ChatModel.complete(prompt=rag_answer_v1)
   → record LLMCallObservation
   → return { answer, citations[] } with X-Request-ID echo
```

Phase 2 is **complete** only when every acceptance criterion in `docs/phase-2-revision/04-phase-2-scope.md §8` holds and `make check` passes on a clean checkout.

### 1.1. Known unresolved conflict to call out before implementation

None blocking. The revision pack (`01-contradictions.md`) resolved C-1..C-10 already. Two clarifications the implementing model must honor:

- **C-2 clarification**: OTel exporters and providers are constructed inside `app/core/wiring/`. `app/observability/` only exposes config types, middleware factories, and the `request_id_var` context var. Do not import OTel exporters from `app/observability/`.
- **C-4 clarification**: One type per role per module. `domain.py` → frozen dataclasses (Pydantic only for validation-heavy value objects). `api.py` → Pydantic v2 request/response. `persistence.py` → SQLAlchemy mapped. **Never** mix.
- **S3 storage adapter is Phase 3.** Phase 2 ships **only** the local-FS `BlobStorage` adapter. Settings, `.env.example`, docker-compose, and wiring must not assume S3 in Phase 2. Task T-705 is removed; `aioboto3` does not enter Phase 2.
- **Container is incremental.** `app/core/container.py` (T-504) starts with the **minimal** set of fields wired by tasks already completed. Each later wiring task (T-708, T-1212, T-1402, T-1503) **appends** its field. A task may not reference a Container field that has not yet been added.
- **Makefile arrives in T-103.** Tasks T-101 and T-102 must not invoke `make ...` in their `Commands` block; they use the equivalent `uv run` commands directly. Every later task may use `make ...`.
- **`importlinter` runs at every phase.** Contracts in T-107 validate cleanly against an empty/skeleton `app/` package (T-107 creates a minimal `app/__init__.py` so `lint-imports` has a target). The same contracts continue to apply unchanged after every later task adds modules.
- **ai_governance domain/ports precede `app.llm.service`.** A standalone task T-1100 (ai_governance domain + ports only) executes before T-1102. The remaining ai_governance tasks (T-1201..T-1206) stay in S12 as scheduled.

---

## 2. Global rules (apply to every task; no exceptions)

These rules are enforced by `import-linter`, `ruff`, `mypy --strict`, and human review. A task is **not done** if it violates any of them.

1. Do not redesign architecture. If a task seems to require redesign, **stop and report unresolved issue**.
2. Do not introduce new top-level folders. Top-level forbidden folder names: `models/`, `schemas/`, `routers/`, `services/`, `repositories/`, `utils/`, `common/`, `helpers/`.
3. Do not introduce new third-party dependencies unless the current task explicitly authorizes it.
4. **`from app.infrastructure.* import ...` is forbidden everywhere except inside `app/core/wiring/`.**
5. Provider SDKs (`openai`, `anthropic`, `google.generativeai`, `cohere`, `voyageai`, `qdrant_client`, `boto3`/`aioboto3`, `redis`, `arq`, `pydantic_ai`) may be imported **only** in their dedicated adapter file. `pydantic_ai` is reserved for `app/ai/agent_runner.py` (Phase 3 — skeleton only in Phase 2).
6. Do not create generic `Repository<T>` abstractions.
7. Do not return SQLAlchemy mapped objects from `service.py` or `api.py`. Translate to domain or API types at the boundary.
8. `os.environ` / `os.getenv` may be read only inside `app/core/config/`.
9. No inline prompt strings in `service.py`/`pipeline.py`. All prompts live in `app/prompts/library/<id>_v<n>.yaml`.
10. No direct LLM provider calls outside `app/infrastructure/llm_providers/`. All LLM calls flow through `app.llm.service`, which **must** call `app.ai_governance.service.check_call_allowed` first and emit `LLMCallObservation`.
11. No `except Exception: pass`, no bare `except:`, no swallowed errors. Re-raise or record.
12. No hardcoded secrets, model ids, prompt strings, or URLs in business logic.
13. No `print(` in `app/`. Use `structlog` via `app.observability.logging`.
14. No `requests`, `urllib.request`, `psycopg2`, or `time.sleep` in `app/`. Use `httpx`, `asyncpg`, `asyncio.sleep`.
15. Every `# type: ignore` must carry a rule code and a one-line reason: `# type: ignore[<rule>]  # <reason>`.
16. Every API error response is RFC 9457 Problem Details produced by `app/api/errors.py`. Never raise `HTTPException` below `api.py`. Never include stack traces, SQL, secrets, or raw provider responses in error bodies.
17. Every API response carries `X-Request-ID` (echo of inbound header, otherwise newly generated UUIDv4).
18. Every external HTTP call goes through `app/infrastructure/http/`.
19. Coverage gate: `--cov-fail-under=80` on `app/`. Tests must not be skipped or weakened to pass.
20. Do not fake pgvector in tests that claim to validate retrieval. Use Testcontainers Postgres + pgvector.
21. Do not add TODO comments as substitutes for implementation.
22. A module's public surface is **only** what its `__init__.py` re-exports. Other modules must import from `__init__.py`, not from internal files (except `api.py` for the API mounting layer and `persistence.py` mapped classes only within the same module).
23. Each task must update `importlinter.toml` if it introduces a new allowed edge. Each task must keep `make check` passing.
24. **"Allowed files" includes the test files named in "Tests required".** Whenever a task's `Allowed files` says `tests` (shorthand) or omits an explicit test path, the implementer is **required** (and thereby authorized) to create the test files listed in that same task's `Tests required` block under the canonical locations: co-located unit/contract tests at `app/<module>/tests/test_<name>.py`, API tests at `tests/api/test_<name>.py`, integration tests at `tests/integration/test_<name>.py`. No other files may be created.
25. **The "standard four" Commands block** referenced by many tasks is exactly:
    ```
    make fmt
    make lint
    make typecheck
    make test
    ```
    This block is only valid for tasks that depend (transitively) on T-103 (Makefile). T-101 and T-102 use the `uv run ...` equivalents listed in their own Commands block.

---

## 3. Phase 2 dependency map

Tasks are grouped into 18 sections; each section may only begin once its declared upstream sections are complete. Within a section, tasks are also sequential unless explicitly marked parallelizable.

```
S01 Foundation/tooling
   └─► S02 Shared primitives
         └─► S03 Configuration
               └─► S04 Observability
                     └─► S05 App factory + API edge (errors, middleware, healthchecks)
                           ├─► S06 Platform ports
                           │     └─► S07 Infrastructure base (db, redis, http)
                           │           └─► S08 Persistence + migrations (Alembic init, pgvector ext)
                           │                 ├─► S09 Auth + users (minimal)
                           │                 ├─► S10 Prompts registry (+ rag_answer_v1.yaml)
                           │                 ├─► S11 LLM + embeddings ports + fakes
                           │                 │     └─► S12 ai_governance
                           │                 │           └─► (OpenAI adapters)
                           │                 ├─► S13 Documents (domain, persistence, API skeleton)
                           │                 ├─► S14 Queue port + Arq adapter + worker entrypoint
                           │                 ├─► S15 Vector store (pgvector adapter, rag.ports)
                           │                 └─► S16 RAG pipeline + /ask endpoint
                           │                       └─► S17 Golden-path integration test
                           │                             └─► S18 Documentation + final hardening
```

Hard ordering rules (do not violate):

- OpenAI LLM/embedding adapters (S11) require: `app.llm.domain`, `app.embeddings.domain`, settings (S03), HTTP client (S07), observability (S04).
- Document ingestion (S13–S15) requires: documents persistence (S13), blob storage (S07), queue (S14), embeddings (S11), vector store (S15).
- RAG (S16) requires: settings (S03), DB (S07), platform ports (S06), prompts (S10), embeddings port (S11), vector store (S15), `ai_governance` (S12).
- Tests of any LLM-touching code default to **fake** `ChatModel` / `EmbeddingModel` adapters introduced in S11; OpenAI adapters are tested by their own contract suite only.

---

## 4. Task index

Legend: `M` = mandatory for Phase 2 acceptance; `S` = skeleton-only (do not over-build).

| ID    | Section                          | Title                                                              | Kind |
| ----- | -------------------------------- | ------------------------------------------------------------------ | ---- |
| T-101 | S01 Foundation/tooling           | Initialize `pyproject.toml` (uv, py3.13, deps groups)              | M    |
| T-102 | S01                              | Add Ruff + Mypy + Pytest config                                    | M    |
| T-103 | S01                              | Create `Makefile` with all targets                                 | M    |
| T-104 | S01                              | Create `Dockerfile` (multi-stage, non-root, uv)                    | M    |
| T-105 | S01                              | Create `docker-compose.yml` + `docker-compose.override.yml`        | M    |
| T-106 | S01                              | Create `.pre-commit-config.yaml`                                   | M    |
| T-107 | S01                              | Create `importlinter.toml` with Phase 2 contracts                  | M    |
| T-108 | S01                              | Create `.github/workflows/ci.yml`                                  | M    |
| T-109 | S01                              | Create `.env.example`, `.gitignore`, `.editorconfig`               | M    |
| T-201 | S02 Shared primitives            | `app/shared/errors.py` (`AppError` hierarchy)                      | M    |
| T-202 | S02                              | `app/shared/problem_details.py` (RFC 9457 model + factory)         | M    |
| T-203 | S02                              | `app/shared/ids.py`, `clock.py`, `pagination.py`, `result.py`, `types.py`, `pydantic.py` | M |
| T-301 | S03 Configuration                | `app/core/config/__init__.py` Pydantic Settings hierarchy          | M    |
| T-302 | S03                              | Settings validation test (bad env → startup fail)                  | M    |
| T-401 | S04 Observability                | `app/observability/logging.py` structlog config                    | M    |
| T-402 | S04                              | `app/observability/correlation.py` `request_id_var` + middleware  | M    |
| T-403 | S04                              | `app/observability/tracing.py`, `metrics.py` config holders        | M    |
| T-404 | S04                              | `app/observability/middleware.py` access log + X-Request-ID echo   | M    |
| T-405 | S04                              | `app/observability/health.py` `/healthz`, `/readyz`, `/livez`      | M    |
| T-501 | S05 App factory + API edge       | `app/api/errors.py` AppError → Problem Details handler             | M    |
| T-502 | S05                              | `app/api/security_headers.py`, `pagination.py`                     | M    |
| T-503 | S05                              | `app/api/v1.py` router mount point                                 | M    |
| T-504 | S05                              | `app/core/container.py`, `di.py`, `lifespan.py`                    | M    |
| T-505 | S05                              | `app/core/app_factory.py` `create_app()`                           | M    |
| T-506 | S05                              | `app/main.py` ASGI entrypoint                                      | M    |
| T-507 | S05                              | API error/correlation tests (Problem Details, X-Request-ID echo)   | M    |
| T-601 | S06 Platform ports               | `app/platform/storage/ports.py` (BlobStorage)                       | M    |
| T-602 | S06                              | `app/platform/cache/ports.py` (Cache)                              | M    |
| T-603 | S06                              | `app/platform/queue/ports.py` (TaskQueue + Job)                    | M    |
| T-604 | S06                              | `app/platform/rate_limit/ports.py` (RateLimiter)                   | M    |
| T-605 | S06                              | `app/platform/idempotency/ports.py` (IdempotencyStore)             | M    |
| T-701 | S07 Infrastructure base          | `app/infrastructure/db/` async engine + sessionmaker + pgvector type | M  |
| T-702 | S07                              | `app/infrastructure/redis/` async client + Cache adapter           | M    |
| T-703 | S07                              | `app/infrastructure/http/` shared httpx + tenacity + OTel          | M    |
| T-704 | S07                              | `app/infrastructure/storage/local.py` BlobStorage local adapter    | M    |
| T-706 | S07                              | `app/infrastructure/rate_limit/redis.py`                           | M    |
| T-707 | S07                              | `app/infrastructure/idempotency/redis.py`                          | M    |
| T-708 | S07                              | `app/core/wiring/storage.py`, `cache.py`                           | M    |
| T-801 | S08 Persistence + migrations     | Alembic init + `alembic/env.py` async config                       | M    |
| T-802 | S08                              | Initial migration: pgvector extension + base metadata              | M    |
| T-803 | S08                              | Integration test: DB session + pgvector type round-trip            | M    |
| T-901 | S09 Auth                         | `app/auth/domain.py`                                               | M    |
| T-902 | S09                              | `app/auth/ports.py` (IdentityProvider, TokenSigner, PasswordHasher)| M    |
| T-903 | S09                              | `app/auth/adapters/argon2_hasher.py`                               | M    |
| T-904 | S09                              | `app/auth/adapters/jwt_signer.py`                                  | M    |
| T-905 | S09                              | `app/auth/persistence.py` (users, refresh_tokens) + migration      | M    |
| T-906 | S09                              | `app/auth/service.py` + `policies.py` + `deps.py`                  | M    |
| T-907 | S09                              | `app/auth/api.py` (register/login/refresh/logout)                  | M    |
| T-908 | S09                              | Auth API tests + refresh-reuse detection test                      | M    |
| T-910 | S09 Users                        | `app/users/{domain,persistence,service,api,deps}.py` GET /users/me | M    |
| T-1001| S10 Prompts                      | `app/prompts/{domain,ports,registry}.py` + `__init__.py`           | M    |
| T-1002| S10                              | `app/prompts/library/rag_answer_v1.yaml` + IO schemas              | M    |
| T-1003| S10                              | `app/prompts/api.py` (read-only inspection)                        | M    |
| T-1004| S10                              | Prompt registry render + schema-validation tests                   | M    |
| T-1100| S11 LLM + embeddings ports       | `app/ai_governance/{domain,ports}.py` (pre-llm interface only)     | M    |
| T-1101| S11                              | `app/llm/{domain,ports,observability,router}.py`                   | M    |
| T-1102| S11                              | `app/llm/service.py` (governance gate + observation)               | M    |
| T-1103| S11                              | `app/embeddings/{domain,ports,service}.py`                         | M    |
| T-1104| S11                              | Fake `ChatModel` + fake `EmbeddingModel` test doubles              | M    |
| T-1105| S11                              | ChatModel contract test suite (parameterized)                      | M    |
| T-1106| S11                              | EmbeddingModel contract test suite (parameterized)                 | M    |
| T-1202| S12                              | `app/ai_governance/persistence.py` (3 tables) + migration          | M    |
| T-1203| S12                              | `app/ai_governance/service.py` (check_call_allowed, record_usage)  | M    |
| T-1204| S12                              | `app/ai_governance/events.py` + audit emit                         | M    |
| T-1205| S12                              | `app/ai_governance/api.py` (read-only) + wiring                    | M    |
| T-1206| S12                              | Budget-deny + 80% warning + audit tests                            | M    |
| T-1210| S12+S11                          | `app/infrastructure/llm_providers/openai.py` (ChatModel adapter)    | M    |
| T-1211| S12+S11                          | `app/infrastructure/embedding_providers/openai.py`                  | M    |
| T-1212| S12+S11                          | `app/core/wiring/llm.py`, `embeddings.py`, `governance.py`         | M    |
| T-1301| S13 Documents (domain + API)     | `app/documents/{domain,ports}.py`                                  | M    |
| T-1302| S13                              | `app/documents/parsers/` (txt, md, html, pdf via pypdf)            | M    |
| T-1303| S13                              | `app/documents/chunkers/` (recursive token-aware, tiktoken)        | M    |
| T-1304| S13                              | `app/documents/persistence.py` (documents, chunks) + migration     | M    |
| T-1305| S13                              | `app/documents/api.py` POST/GET endpoints                          | M    |
| T-1401| S14 Queue + worker               | `app/infrastructure/queue/arq.py` TaskQueue adapter                | M    |
| T-1402| S14                              | `app/core/wiring/queue.py` + worker entrypoint sharing wiring      | M    |
| T-1403| S14                              | `app/documents/ingestion.py` job + `app/documents/service.py`      | M    |
| T-1404| S14                              | Integration test: enqueue → run → status transitions               | M    |
| T-1501| S15 Vector store                 | `app/rag/ports.py` (VectorStore)                                   | M    |
| T-1502| S15                              | `app/infrastructure/vector_stores/pgvector.py` adapter             | M    |
| T-1503| S15                              | `app/core/wiring/vector_store.py`                                  | M    |
| T-1504| S15                              | Integration test: real pgvector similarity round-trip              | M    |
| T-1601| S16 RAG                          | `app/rag/{domain,pipeline,service}.py`                             | M    |
| T-1602| S16                              | `app/rag/api.py` POST `/rag/ask`                                   | M    |
| T-1603| S16                              | RAG unit + API tests (citations always present)                    | M    |
| T-1701| S17 Golden-path integration      | End-to-end test: upload → ingest → ask → answer + citation         | M    |
| T-1702| S17                              | LLMCallObservation field-completeness assertion                    | M    |
| T-1703| S17                              | Continuous-trace assertion (POST /ask → embed → search → chat)     | M    |
| T-1801| S18 Docs + hardening             | Update `docs/architecture.md`, `docs/folder-structure.md`, `docs/dependency-graph.md` | M |
| T-1802| S18                              | Update `README.md` quickstart + golden-path walkthrough            | M    |
| T-1803| S18                              | Mark ADR-0009 Superseded; ensure ADRs 0018–0022 cross-linked       | M    |
| T-1804| S18                              | Final `make check` on clean checkout                               | M    |

---

## 5. Detailed tasks

For every task use the schema declared in the issue. **Implementation requirements** must be followed literally. **Tests required** must be added in the same PR. A task is not done until all **Acceptance criteria** hold and all **Commands** pass.

### Section S01 — Foundation & tooling

#### Task : T-101 — Initialize `pyproject.toml` with uv

Purpose

- Lock the toolchain (Python 3.13, uv) and declare dependency groups so every later task installs into a deterministic environment.

Depends on

- (none)

Allowed files

- `pyproject.toml`
- `uv.lock`
- `.python-version`

Forbidden

- Do not add `app/**` files in this task.
- Do not add `requirements*.txt` files.
- Do not pin to Python ≠ 3.13.
- Do not add provider SDKs in this task (they enter only with their adapter task).

Implementation requirements

- `[project]`: `name = "ai-backend-foundation"`, `requires-python = ">=3.13,<3.14"`.
- Dependency groups (PEP 735) named `main`, `dev`, `test`.
- `main` includes: `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pgvector`, `redis`, `arq`, `httpx`, `tenacity`, `structlog`, `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-httpx`, `opentelemetry-instrumentation-sqlalchemy`, `opentelemetry-instrumentation-redis`, `opentelemetry-exporter-otlp`, `argon2-cffi`, `pyjwt[crypto]`, `jinja2`, `pyyaml`, `python-multipart`.
- `test` adds: `pytest`, `pytest-asyncio`, `pytest-cov`, `httpx`, `testcontainers[postgresql,redis]`, `respx`, `freezegun`, `dirty-equals`.
- `dev` adds: `ruff`, `mypy`, `import-linter`, `pre-commit`, `types-pyyaml`.
- Commit `uv.lock`.

Tests required

- None for this task. Validation is `uv sync` succeeding.

Acceptance criteria

- `uv sync --all-groups` succeeds on a clean checkout.
- `uv run python -c "import sys; assert sys.version_info[:2] == (3, 13)"` exits 0.
- `uv.lock` is committed.

Commands

```
uv sync --all-groups
```

Common failure modes

- Mixing `requirements.txt` and `pyproject.toml`.
- Adding `openai`, `aioboto3`, `pypdf`, `tiktoken` here. Those enter with their adapter task.

Review checklist

- Python 3.13 pinned, uv groups defined, lock committed, no SDKs leaked in.

#### Task : T-102 — Ruff + Mypy + Pytest config

Purpose

- Enforce code style, type discipline, and test discoverability from the first commit.

Depends on

- T-101

Allowed files

- `pyproject.toml` (extend with `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]`, `[tool.coverage.*]` sections)

Forbidden

- Do not place tool configs in separate files (`ruff.toml`, `mypy.ini`, `pytest.ini`). All config consolidated in `pyproject.toml`.
- Do not relax `mypy` strictness for `app/`.

Implementation requirements

- Ruff: `line-length = 100`, `target-version = "py313"`, enable rule sets `E, F, W, I, B, UP, N, S, ANN, ASYNC, RUF, C4, SIM, PL, PT, TRY, T20` (no inline disabling without reason). Per-folder ignores: `tests/**` may ignore `S101, ANN`. `alembic/**` may ignore `INP001`. Ruff format enabled.
- Mypy: `strict = true`, `python_version = "3.13"`, `files = ["app"]`, `plugins = ["pydantic.mypy"]`, `follow_imports = "normal"`. Override for `tests/**`: `disallow_untyped_defs = false`.
- Pytest: `asyncio_mode = "auto"`, `markers = ["unit", "integration", "api", "contract", "slow"]`, `addopts = "--strict-markers --cov=app --cov-report=term-missing --cov-fail-under=80"`.
- Coverage: `source = ["app"]`, `branch = true`, omit `app/**/__init__.py` only when empty re-exports.

Tests required

- `tests/test_tooling.py::test_ruff_config_present` (asserts `[tool.ruff]` block present and parses).
- `tests/test_tooling.py::test_mypy_strict_on_app` (parses `pyproject.toml` and asserts `strict = true`).

Acceptance criteria

- `uv run ruff check app tests`, `uv run mypy app`, and `uv run pytest` all execute (even on an empty `app/`). Makefile equivalents arrive in T-103.

Commands

```
uv run ruff format app tests
uv run ruff check app tests
uv run mypy app
uv run pytest
```

Common failure modes

- Disabling rules globally to silence early noise — use per-folder ignores instead.
- Setting `pytest-cov` fail-under below 80.
- Invoking `make ...` here: the Makefile does not exist yet (lands in T-103).

Review checklist

- 100-char lines, target py313, strict mypy, markers registered, coverage gate ≥80.

#### Task : T-103 — `Makefile` with all targets

Purpose

- Provide a single, stable command surface for developers and CI.

Depends on: T-101, T-102.

Allowed files: `Makefile`.

Forbidden: do not invoke `pip`, `poetry`, or `python -m` directly inside targets — all Python invocations go through `uv run`. Do not silently swallow errors with `-`.

Implementation requirements

- Targets (each one-line, declared `.PHONY`): `fmt`, `lint`, `typecheck`, `test`, `test-int`, `migrate`, `revision`, `worker`, `up`, `down`, `logs`, `check`.
- `fmt` → `uv run ruff format app tests`.
- `lint` → `uv run ruff check app tests`.
- `typecheck` → `uv run mypy app`.
- `test` → `uv run pytest -m "unit or api or contract"`.
- `test-int` → `uv run pytest -m "integration"`.
- `migrate` → `uv run alembic upgrade head`.
- `revision` → `uv run alembic revision --autogenerate -m "$(msg)"`.
- `worker` → `uv run arq app.core.wiring.queue.WorkerSettings`.
- `up` / `down` → `docker compose up -d` / `docker compose down -v`.
- `check` → `make fmt && make lint && make typecheck && uv run lint-imports && make test && make test-int`.

Tests required

- `tests/test_tooling.py::test_makefile_targets` parses `Makefile` and asserts every required target exists.

Acceptance criteria: `make check` is the single command CI runs; it fails fast on the first error.

Commands

```
make fmt
make lint
make typecheck
make test
```

Common failure modes: forgetting `.PHONY`, hardcoding venv paths, omitting `lint-imports`.

Review checklist: all 12 targets present, `check` runs the full quality bar, no shell-specific bashisms beyond POSIX.

#### Task : T-104 — `Dockerfile` (multi-stage, non-root, uv)

Purpose: produce a reproducible, secure runtime image used by both API and worker.

Depends on: T-101.

Allowed files: `Dockerfile`, `.dockerignore`.

Forbidden: do not `pip install` outside `uv`. Do not run as root in the final stage. Do not bake secrets or `.env` files into the image.

Implementation requirements

- Stage 1 (`builder`): `python:3.13-slim`; install `uv`; `COPY pyproject.toml uv.lock ./`; `uv sync --frozen --no-dev --group main`.
- Stage 2 (`runtime`): same base, copy resolved virtualenv from builder; `COPY app /app/app`, `COPY alembic /app/alembic`, `COPY alembic.ini /app/`.
- Create a non-root user `app` (uid 10001) and `USER app`.
- `HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD ["python", "-c", "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/livez', timeout=3); sys.exit(0)"]`. Do **not** rely on `curl`; it is not installed in `python:3.13-slim`.
- `ENTRYPOINT ["uv","run","uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]`.

Tests required: integration smoke (Phase 2 acceptance) — `docker build . && docker run ...` returns 200 on `/livez`.

Acceptance criteria: image builds reproducibly, runs as non-root, healthcheck green.

Commands

```
docker build -t ai-backend-foundation:dev .
```

Common failure modes: building with `--no-cache` missing, running as root, missing `uv.lock` causing non-reproducible builds.

Review checklist: multi-stage, non-root, uv-driven, healthcheck present, no secrets.

#### Task : T-105 — `docker-compose.yml` + override

Purpose: dev orchestration of api, worker, postgres+pgvector, redis, otel-collector.

Depends on: T-104.

Allowed files: `docker-compose.yml`, `docker-compose.override.yml`, `deploy/otel-collector-config.yaml`.

Forbidden: do not hardcode secrets — read from `.env`. Do not omit healthchecks.

Implementation requirements

- Services: `api`, `worker` (same image, command `arq app.core.wiring.queue.WorkerSettings`), `postgres` (`pgvector/pgvector:pg16`), `redis` (`redis:7-alpine`), `otel-collector` (`otel/opentelemetry-collector-contrib:latest`, mounting `deploy/otel-collector-config.yaml`).
- Healthchecks for every service. `api` and `worker` `depends_on` postgres+redis with `condition: service_healthy`.
- `docker-compose.override.yml` mounts `./app:/app/app` for live reload and exposes ports.

Tests required: `docker compose up -d` on a clean checkout reaches `/healthz` 200 within 60s (covered by `make up` once T-103 lands).

Acceptance criteria: `docker compose ps` shows all five healthy.

Commands

```
docker compose config
docker compose up -d
```

Common failure modes: using stock `postgres` image (no pgvector), missing healthcheck, depending on a non-existent service name.

Review checklist: pgvector image, healthchecks present, otel collector config mounted.

#### Task : T-106 — `.pre-commit-config.yaml`

Purpose: catch violations before commit.

Depends on: T-102.

Allowed files: `.pre-commit-config.yaml`.

Forbidden: do not include style hooks that conflict with Ruff.

Implementation requirements: hooks for `ruff` (lint + format), `mypy` (against `app/`), `end-of-file-fixer`, `trailing-whitespace`, `check-merge-conflict`, `detect-secrets`, `import-linter` (`lint-imports`). Pin versions.

Tests required: `uv run pre-commit run --all-files` passes on a clean checkout.

Acceptance criteria: every hook configured, version-pinned, runs locally.

Commands

```
uv run pre-commit run --all-files
```

Common failure modes: floating hook versions; running mypy on `tests/` with strict mode.

Review checklist: ruff format+lint, mypy strict, import-linter, detect-secrets.

#### Task : T-107 — `importlinter.toml` with Phase 2 contracts

Purpose: encode the Phase 2 dependency graph (§03 of revision pack) into machine-checked contracts before any module exists, so future tasks cannot drift.

Depends on: T-102.

Allowed files: `importlinter.toml`, `app/__init__.py`, `tests/__init__.py`, `tests/test_imports.py`.

Forbidden: do not weaken or remove a contract to make a future task pass. Do not add `ignore_imports` patterns beyond those explicitly enumerated in §03.

Note: `lint-imports` needs at least one importable package at `app/` to evaluate contracts. This task creates an empty `app/__init__.py` (and `tests/__init__.py`) so contracts pass cleanly on the skeleton and continue to apply unchanged after every later task adds modules.

Implementation requirements

- `root_packages = ["app"]`.
- Contract "Layers" with exact layer order from `docs/phase-2-revision/03-revised-dependency-graph.md §5`.
- Contract "Capabilities are independent" (`independence` over `app.llm`, `app.embeddings`, `app.prompts`).
- Contract "ai and rag are independent" (`independence` over `app.ai`, `app.rag`).
- Contract "auth does not import users" (`forbidden`).
- Contract "Only core.wiring imports infrastructure" (`forbidden`) — sources include every module except `app.core.wiring`; forbidden module = `app.infrastructure`.
- Contract "Platform is below everything except shared" (`forbidden`) — sources = `app.platform`; forbidden = listed in §03.
- Contract "No cross-module persistence/adapters imports" — `forbidden` with the exact `ignore_imports` whitelist from §03.

Tests required

- `tests/test_imports.py::test_import_linter_passes` shells out to `uv run lint-imports` and asserts exit 0.

Acceptance criteria: `lint-imports` reports zero violations on the empty skeleton (`app/__init__.py` only) and remains zero after every later task.

Commands

```
uv run lint-imports
```

Common failure modes: silencing a contract with broad `ignore_imports` instead of fixing the offending edge; renaming `app.infrastructure` to dodge the contract.

Review checklist: 7 contracts present, names match §03, no extra `ignore_imports` beyond the whitelist.

#### Task : T-108 — `.github/workflows/ci.yml`

Purpose: CI must run the same `make check` as developers.

Depends on: T-103, T-107.

Allowed files: `.github/workflows/ci.yml`.

Forbidden: do not run tests against real OpenAI in CI. Do not skip `lint-imports`.

Implementation requirements

- Triggers: `pull_request`, `push` to `main`.
- Job `quality`: ubuntu-latest, Python 3.13, install uv, `uv sync --all-groups`, `make lint typecheck test`, `uv run lint-imports`.
- Job `integration`: needs docker, `make test-int` (Testcontainers brings up postgres+pgvector and redis).
- Job `image`: `docker build .` (no push in Phase 2).
- All jobs required for merge.

Tests required: workflow runs successfully on the first green PR.

Acceptance criteria: PR cannot merge unless every job passes.

Commands: n/a (validated in CI).

Common failure modes: defaulting to Python 3.11; not exporting `OPENAI_API_KEY=test-stub` for tests that import settings.

Review checklist: three required jobs, uv-driven, lint-imports gated.

#### Task : T-109 — `.env.example`, `.gitignore`, `.editorconfig`

Purpose: declare every env var the app expects, with safe defaults; prevent secret commits.

Depends on: T-101.

Allowed files: `.env.example`, `.gitignore`, `.editorconfig`.

Forbidden: do not commit a real `.env`. Do not commit secrets.

Implementation requirements

- `.env.example` documents (with placeholder values): `APP_ENV`, `LOG_LEVEL`, `DATABASE_URL`, `REDIS_URL`, `JWT_PRIVATE_KEY`, `JWT_PUBLIC_KEY`, `JWT_ISSUER`, `JWT_AUDIENCE`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_CHAT_MODEL`, `OPENAI_EMBEDDING_MODEL`, `BLOB_STORAGE_BACKEND` (`local` only in Phase 2), `BLOB_LOCAL_DIR`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `ARQ_REDIS_URL`, `LLM_MONTHLY_BUDGET_USD`, `LLM_MODEL_ALLOWLIST`. Do **not** include `AWS_*` keys — S3 is Phase 3.
- `.gitignore`: standard Python + `/.venv`, `/.env`, `/.coverage*`, `/htmlcov`, `/.mypy_cache`, `/.pytest_cache`, `/.ruff_cache`, `/dist`, `/build`.
- `.editorconfig`: `indent_style = space`, `indent_size = 4` for `.py`, `2` for YAML/TOML/JSON, `end_of_line = lf`, `insert_final_newline = true`, `trim_trailing_whitespace = true`.

Tests required: `tests/test_tooling.py::test_env_example_keys` asserts that the set of keys declared by `app.core.config` is a subset of keys in `.env.example` (run **after** T-301).

Acceptance criteria: `.env.example` is the single source of documented env vars.

Commands: n/a.

Common failure modes: forgetting to update `.env.example` when a new setting is added in later tasks (test in T-301 enforces this).

Review checklist: example present for every setting, no real secrets, gitignore complete.

### Section S02 — Shared primitives

#### Task : T-201 — `app/shared/errors.py` AppError hierarchy

Purpose: provide the only base for raisable domain/service errors so the API edge can translate them uniformly to Problem Details.

Depends on: T-101..T-109.

Allowed files: `app/shared/__init__.py`, `app/shared/errors.py`, `app/shared/tests/test_errors.py`.

Forbidden: do not import FastAPI, SQLAlchemy, or `app.infrastructure.*`. Do not subclass `HTTPException`.

Implementation requirements

- Base class `AppError(Exception)` with attributes: `code: str`, `title: str`, `status: int = 400`, `detail: str | None = None`, `extras: Mapping[str, Any] = {}`. Frozen-style: set in `__init__`, no mutation.
- Subclasses (minimum): `NotFoundError(404)`, `ConflictError(409)`, `ValidationError(422)`, `AuthenticationError(401)`, `AuthorizationError(403)`, `BudgetExceededError(409, code="budget-exceeded")`, `UpstreamProviderError(502)`, `RateLimitedError(429)`.
- Errors carry `code` slugs (kebab-case) that match the Problem Details `code` field. No localization in Phase 2.

Tests required (unit): instantiate each subclass; assert `status`, `code`, `title`; assert subclass of `AppError`.

Acceptance criteria: every service/domain error in Phase 2 ultimately subclasses `AppError`.

Commands

```
make fmt
make lint
make typecheck
make test
```

Common failure modes: raising bare `Exception`; storing mutable state on the instance.

Review checklist: pure stdlib, no FastAPI/SQLAlchemy import, kebab-case codes.

#### Task : T-202 — `app/shared/problem_details.py`

Purpose: ship the RFC 9457 model and a `from_app_error()` factory.

Depends on: T-201.

Allowed files: `app/shared/problem_details.py`, `app/shared/tests/test_problem_details.py`.

Forbidden: do not import FastAPI here. Do not include stack traces, SQL, or provider raw bodies in the model.

Implementation requirements

- Pydantic v2 `ProblemDetails` model with fields: `type: str = "about:blank"`, `title: str`, `status: int`, `detail: str | None = None`, `instance: str | None = None`, `code: str`, `request_id: str | None = None`, plus arbitrary extras via `model_config = ConfigDict(extra="allow")`.
- Factory `from_app_error(err: AppError, *, request_id: str | None) -> ProblemDetails` mapping the AppError fields.
- `MEDIA_TYPE = "application/problem+json"`.

Tests required: round-trip serialization; factory produces the expected JSON shape; no field leaks for unknown errors.

Acceptance criteria: every API error response uses this model (enforced by T-501 + T-507).

Commands: standard four.

Common failure modes: leaking `extras` containing secrets; using `application/json` content type.

Review checklist: media type correct, no FastAPI import, request_id wired.

#### Task : T-203 — Shared leaves: `ids`, `clock`, `pagination`, `result`, `types`, `pydantic`

Purpose: stable primitives used by every module.

Depends on: T-101.

Allowed files: `app/shared/{ids,clock,pagination,result,types,pydantic}.py`, plus tests under `app/shared/tests/`.

Forbidden: do not import any other `app.*` module here. Do not call `datetime.utcnow()` (deprecated). Do not import `pydantic_settings`.

Implementation requirements

- `ids.py`: `new_id() -> str` (UUIDv7 preferred; fall back to UUIDv4 if stdlib lacks v7), `new_request_id() -> str`.
- `clock.py`: `Clock` Protocol with `now() -> datetime` (tz-aware, UTC); `SystemClock` impl; `FixedClock(now: datetime)` for tests.
- `pagination.py`: `Page[T]` dataclass with `items`, `total`, `cursor`; `CursorParams`.
- `result.py`: `Ok[T]` / `Err[E]` discriminated dataclasses with `.unwrap()` etc.
- `types.py`: type aliases `TenantId`, `UserId`, `DocumentId`, `ChunkId`, `RequestId` (NewType over `str`).
- `pydantic.py`: a shared `BaseSchema(BaseModel)` with `model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)`.

Tests required: unit tests for each module — clock returns tz-aware UTC; `Page` invariants; `Result.unwrap` raises on Err; ids are unique.

Acceptance criteria: every later module imports from these without circular issues.

Commands: standard four.

Common failure modes: naive datetimes; mutable default args; importing pydantic-settings here.

Review checklist: no `app.*` imports; tz-aware times; frozen base schema.

### Section S03 — Configuration

#### Task : T-301 — `app/core/config/` Pydantic Settings

Purpose: single, validated place where env vars enter the app.

Depends on: T-203.

Allowed files: `app/core/__init__.py`, `app/core/config/__init__.py`, `app/core/config/settings.py`, `app/core/config/tests/test_settings.py`.

Forbidden: **the only place in `app/` allowed to call `os.environ` / `os.getenv`.** Do not import anything from `app.infrastructure.*` or domain modules. Do not place defaults containing secrets.

Implementation requirements

- One `AppSettings(BaseSettings)` aggregating nested settings groups: `AppMeta` (`env: Literal["dev","test","staging","prod"]`, `service_name`), `Logging` (`level`), `Database` (`url: PostgresDsn`), `Redis` (`url: RedisDsn`, `arq_url: RedisDsn`), `Jwt` (`private_key: SecretStr`, `public_key: SecretStr`, `issuer: str`, `audience: str`, `access_ttl_seconds: int = 900`, `refresh_ttl_seconds: int = 60*60*24*14`), `OpenAI` (`api_key: SecretStr`, `base_url: HttpUrl | None`, `chat_model: str`, `embedding_model: str`), `BlobStorage` (`backend: Literal["local"]`, `local_dir: Path`) — Phase 2 supports only `"local"`; S3 lands in Phase 3, `Otel` (`endpoint: HttpUrl | None`), `Governance` (`monthly_budget_usd: Decimal`, `warning_threshold: float = 0.8`, `model_allowlist: tuple[str, ...]`).
- Conditional validator: `backend == "local"` requires `local_dir`.
- `env_file = ".env"`, `env_nested_delimiter = "__"`.
- Public function `get_settings() -> AppSettings` with `lru_cache(maxsize=1)`; tests reset the cache.

Tests required (unit, listed under S03)

- Boot with valid env → success.
- Missing `JWT_PRIVATE_KEY` → `ValidationError` at instantiation.
- `BLOB_STORAGE_BACKEND` accepts only `"local"` in Phase 2 (other values → fails).
- `LLM_MONTHLY_BUDGET_USD=-1` → fails (Decimal ≥ 0).
- `.env.example` superset test from T-109 wired here.

Acceptance criteria: app refuses to start on bad config; secrets always typed as `SecretStr`; settings cached.

Commands: standard four.

Common failure modes: calling `os.getenv` in a domain module; using `str` for secrets; instantiating settings at import time outside `core.config`.

Review checklist: SecretStr for secrets, lru_cache, no domain imports, validators present.

#### Task : T-302 — Settings validation test

Purpose: assert startup fails on invalid env.

Depends on: T-301.

Allowed files: `app/core/config/tests/test_settings_startup.py`.

Forbidden: do not patch `os.environ` outside the test; use `monkeypatch`.

Implementation requirements: parameterized test that wipes critical vars one at a time and asserts `AppSettings()` raises `ValidationError`.

Tests required: see above.

Acceptance criteria: each removal yields a clear error message.

Commands: `make test`.

Common failure modes: leaking env vars from the host; not resetting `get_settings.cache_clear()`.

Review checklist: parameterized, isolated, no host leak.

### Section S04 — Observability

(Observability leaves; no `app.infrastructure.*` imports. Exporters live in `core.wiring` and are passed in as configured objects.)

#### Task : T-401 — `app/observability/logging.py` structlog

Purpose: single, structured logging entrypoint.

Depends on: T-203, T-301.

Allowed files: `app/observability/__init__.py`, `app/observability/logging.py`, `app/observability/tests/test_logging.py`.

Forbidden: no `print`, no `logging.getLogger` ad hoc, no OTel exporter imports.

Implementation requirements

- `configure_logging(level: str, json: bool) -> None` configures structlog processors: `add_log_level`, `TimeStamper(fmt="iso", utc=True)`, request id from `correlation.request_id_var`, `EventRenamer`, JSON renderer (prod) or console (dev).
- `get_logger(name: str | None = None) -> structlog.BoundLogger`.

Tests required: captured log line is a parseable JSON with `event`, `timestamp`, `level`, `request_id` (when present).

Acceptance criteria: every later module uses `get_logger`.

Commands: standard four.

Common failure modes: configuring stdlib logging twice; missing request id propagation.

Review checklist: JSON output in prod, ISO+UTC timestamps, request id present.

#### Task : T-402 — `correlation.py` request_id_var + middleware

Purpose: end-to-end request correlation.

Depends on: T-401.

Allowed files: `app/observability/correlation.py`, `app/observability/tests/test_correlation.py`.

Implementation requirements

- `request_id_var: ContextVar[str] = ContextVar("request_id", default="")`.
- ASGI middleware `CorrelationMiddleware` that:
  - reads inbound `X-Request-ID`; if absent or malformed, generates a new UUIDv4;
  - sets `request_id_var`;
  - injects the value into the response header `X-Request-ID`.

Forbidden: do not import FastAPI types beyond `Starlette` BaseHTTPMiddleware; do not store the id on `request.state` alone.

Tests required: inbound id is echoed; absent id triggers generation; concurrent requests do not leak ids.

Acceptance criteria: every API response carries `X-Request-ID` (final test in T-507).

Commands: standard four.

Common failure modes: forgetting to reset the ContextVar token; trusting arbitrary inbound strings without validation.

Review checklist: validation, echo, ContextVar reset.

#### Task : T-403 — `tracing.py` + `metrics.py` config holders

Purpose: declare the OTel resource and tracer/meter shape; **do not** construct exporters here.

Depends on: T-301.

Allowed files: `app/observability/tracing.py`, `app/observability/metrics.py`.

Forbidden: no `*Exporter` imports here.

Implementation requirements: helpers `build_resource(service_name, env) -> Resource`; `get_tracer(name) -> Tracer`; `get_meter(name) -> Meter`. Exporter providers are installed by `app/core/wiring/observability.py` (added implicitly during T-504/T-505 wiring).

Tests required: resource attributes contain `service.name` and `deployment.environment`.

Acceptance criteria: leaf module compiles without OTel SDK exporter import.

Commands: standard four.

Common failure modes: instantiating providers at import time.

Review checklist: no exporter imports here; pure config helpers.

#### Task : T-404 — `middleware.py` access log + headers

Purpose: emit a single structured access log per request and apply security headers globally.

Depends on: T-401, T-402.

Allowed files: `app/observability/middleware.py`.

Implementation requirements: `AccessLogMiddleware` logs method, path, status, duration_ms, request_id, user_id (if available). Reads no app state directly.

Tests required: middleware emits one event per request with required keys.

Acceptance criteria: zero ad-hoc logging in route handlers for access-style events.

Commands: standard four.

Common failure modes: logging twice; reading `request.body` (consumes the stream).

Review checklist: single emission, no body reads.

#### Task : T-405 — Health endpoints `/healthz` `/readyz` `/livez`

Purpose: liveness/readiness probes wired into the app.

Depends on: T-404.

Allowed files: `app/observability/health.py`.

Implementation requirements

- `/livez`: process check; returns `{"status":"ok"}`.
- `/healthz`: composite of registered probes (DB ping, Redis ping). Probes injected from `core.wiring`.
- `/readyz`: same as `/healthz` plus app-startup-complete flag from lifespan.

Tests required: `/livez` returns 200 even before DB is up; `/readyz` returns 503 before startup completes.

Acceptance criteria: docker-compose healthchecks pass against `/healthz`.

Commands: standard four.

Common failure modes: doing real I/O in `/livez`; long-blocking probes.

Review checklist: three endpoints, probes injected, 503 semantics correct.

### Section S05 — App factory + API edge

#### Task : T-501 — `app/api/errors.py` AppError → Problem Details handler

Purpose: single mapping from `AppError` (and `RequestValidationError`, `HTTPException` raised by FastAPI internals) to RFC 9457 Problem Details.

Depends on: T-202, T-402.

Allowed files: `app/api/__init__.py`, `app/api/errors.py`, `app/api/tests/test_errors.py`.

Forbidden: do not catch broad `Exception` and silence; do not include stack traces, SQL, or provider raw bodies; do not register ad-hoc handlers in route files.

Implementation requirements

- `register_exception_handlers(app: FastAPI) -> None` installs handlers for `AppError`, `RequestValidationError` (→ 422 Problem Details), and a fallback for `Exception` that:
  - logs structurally with `exc_info` and `request_id`;
  - marks the active OTel span as errored;
  - returns a generic 500 Problem Details (`code="internal-error"`).
- All handlers produce `application/problem+json` and set `X-Request-ID` from `request_id_var`.

Tests required: each error class maps to expected status/code/title; 422 carries validation extras (sanitized); unknown exception → 500 generic body.

Acceptance criteria: route files raise `AppError` subclasses only; the central handler is the single conversion point.

Commands: standard four.

Common failure modes: serializing raw `exc.args`; missing `X-Request-ID` on error responses.

Review checklist: three handlers, sanitized payloads, X-Request-ID present.

#### Task : T-502 — `security_headers.py` + `pagination.py`

Purpose: global hardening and cursor pagination helpers.

Depends on: T-203.

Allowed files: `app/api/security_headers.py`, `app/api/pagination.py`.

Implementation requirements

- Security headers middleware sets: `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, `Content-Security-Policy: default-src 'none'`.
- CORS: deny by default (whitelist via settings; empty in dev).
- `pagination.py` exposes a FastAPI dependency producing a `CursorParams` object from query string.

Tests required: headers present on every response; CORS denies unknown origin.

Acceptance criteria: middleware registered once in `app_factory`.

Commands: standard four.

Common failure modes: permissive CORS; missing CSP.

Review checklist: deny-by-default, all headers, registered once.

#### Task : T-503 — `app/api/v1.py` router mount point

Purpose: a single place that mounts each module's router under `/api/v1`.

Depends on: T-501.

Allowed files: `app/api/v1.py`.

Forbidden: do not put business logic here; do not import `app.<module>.service`.

Implementation requirements: `def build_v1_router() -> APIRouter:` returns a router that includes each module's API router (each added in its own task with explicit prefix and tags). Phase 2 mounts: `auth`, `users`, `prompts`, `governance`, `documents`, `rag`.

Tests required: router exposes the expected paths once all modules are added (regression test in T-507).

Acceptance criteria: adding a module router requires only an edit here + the module's `api.py`.

Commands: standard four.

Common failure modes: importing services or persistence here.

Review checklist: imports limited to per-module `api`, single mount point.

#### Task : T-504 — `app/core/container.py`, `di.py`, `lifespan.py`

Purpose: composition root: build adapters from settings and expose typed providers; manage startup/shutdown.

Depends on: T-301, T-401–T-405.

Allowed files: `app/core/container.py`, `app/core/di.py`, `app/core/lifespan.py`.

Forbidden: business logic; provider SDK imports outside `app/infrastructure/`.

Implementation requirements

- `Container` is an **incremental** dataclass. In T-504 it declares **only** the fields whose wiring tasks have already completed at this point: `settings: AppSettings`, `db_engine: AsyncEngine | None = None`, `session_factory: async_sessionmaker[AsyncSession] | None = None`. Every later wiring task (T-708 storage+cache, T-1212 llm+embeddings+governance, T-1402 queue, T-1503 vector_store) **adds** its own field to this dataclass in the same PR. Do **not** declare placeholders for components whose wiring task has not yet run — fields land only when their adapter exists.
- All non-bootstrap fields are typed `Optional[<Protocol>]` and default to `None`; the lifespan asserts non-None after startup for the subset required by the current Phase 2 scope.
- `di.py` declares `Depends`-style providers that return entries from the `Container` stored on `app.state.container`.
- `lifespan.py` is an `asynccontextmanager` that initializes the container, runs `await on_startup()` hooks, and tears down cleanly. Sets `app.state.ready = True` only after success.

Tests required: lifespan integration test — startup populates container; shutdown closes connections; `/readyz` flips to 200.

Acceptance criteria: only `core.wiring.*` imports `app.infrastructure.*`; `Container` is the only object that knows about adapters.

Commands: standard four.

Common failure modes: importing wiring modules at top-level of `di.py` (must be inside lifespan); leaving Redis connections un-closed.

Review checklist: Container typed, lifespan idempotent, no infra imports outside wiring.

#### Task : T-505 — `app/core/app_factory.py` `create_app()`

Purpose: produce a configured FastAPI app for serving and for tests.

Depends on: T-501..T-504.

Allowed files: `app/core/app_factory.py`.

Implementation requirements

- `create_app(settings: AppSettings | None = None) -> FastAPI`:
  - configures logging,
  - installs `CorrelationMiddleware`, `AccessLogMiddleware`, security headers, CORS,
  - mounts `/api/v1` router and health endpoints,
  - registers exception handlers,
  - sets the lifespan from `core.lifespan`.

Tests required: app boots in-process with a stubbed container; routes are registered.

Acceptance criteria: `app.main:app = create_app()`.

Commands: standard four.

Common failure modes: building two `FastAPI` instances; middleware order wrong (correlation must wrap access log).

Review checklist: middleware order, lifespan attached, no duplicate handlers.

#### Task : T-506 — `app/main.py`

Purpose: ASGI entrypoint.

Depends on: T-505.

Allowed files: `app/main.py`.

Implementation requirements: `from app.core.app_factory import create_app` then `app = create_app()`. Nothing else.

Tests required: `import app.main` works without side effects beyond app construction.

Acceptance criteria: `uvicorn app.main:app` serves.

Commands: standard four.

Common failure modes: putting routes here; reading env directly.

Review checklist: 2–3 lines only.

#### Task : T-507 — API error & correlation tests

Purpose: enforce Problem Details and X-Request-ID echo at the edge.

Depends on: T-501, T-505.

Allowed files: `tests/api/test_problem_details.py`, `tests/api/test_correlation.py`.

Implementation requirements

- Boot the app with a stub container (no DB) and assert:
  - Triggering a known `AppError` returns a 4xx Problem Details with all required fields.
  - An unhandled exception returns a sanitized 500.
  - Each response echoes inbound `X-Request-ID`; absent → generated.
  - Content-Type is `application/problem+json` on errors.

Tests required: see above.

Acceptance criteria: tests pass against an empty domain set.

Commands: `make test`.

Common failure modes: relying on a real DB; using TestClient default headers.

Review checklist: assertions cover type/title/status/detail/code/request_id and content type.

### Section S06 — Platform ports

> Five port modules. Pure Protocols + value types. No SDK imports. Each task creates `__init__.py` re-exporting only the Protocol(s) and value types listed.

#### Task : T-601 — `app/platform/storage/ports.py` (`BlobStorage`)

Purpose: define the cross-cutting blob storage port used by `documents` (and later `ai`).

Depends on: T-203.

Allowed files: `app/platform/__init__.py`, `app/platform/storage/__init__.py`, `app/platform/storage/ports.py`, `app/platform/storage/tests/test_ports.py`.

Forbidden: do not import `boto3`/`aioboto3`; do not import from `app.infrastructure.*`.

Implementation requirements: `BlobRef` dataclass (`bucket: str, key: str, content_type: str | None, size: int | None, etag: str | None`); `BlobStorage(Protocol)` async methods `put(key, data, content_type) -> BlobRef`, `get(key) -> AsyncIterator[bytes]`, `delete(key) -> None`, `presign_get(key, ttl_s) -> str`. Mark Protocol `@runtime_checkable`.

Tests required: a static type-check fixture (an in-memory fake) asserts `isinstance(fake, BlobStorage)`.

Acceptance criteria: `lint-imports` shows no `app.platform.storage` → `app.infrastructure` edge.

Commands: standard four.

Common failure modes: returning provider-specific objects from `put`.

Review checklist: pure Protocol, no SDK imports, async-only.

#### Task : T-602 — `app/platform/cache/ports.py` (`Cache`)

Purpose / Depends / Allowed / Forbidden: analogous to T-601.

Implementation requirements: `Cache(Protocol)` async `get(key) -> bytes | None`, `set(key, value, ttl_s) -> None`, `delete(key) -> None`, `incr(key) -> int`, `expire(key, ttl_s) -> None`. Add `CacheKey` `NewType` alias.

Tests required: Protocol satisfiability test against a dict-backed fake.

Acceptance, Commands, Failures, Review: analogous.

#### Task : T-603 — `app/platform/queue/ports.py` (`TaskQueue` + `Job`)

Purpose: queue port; consumed by `documents` (ingestion job) and later `rag/ai`.

Depends on: T-203.

Allowed files: `app/platform/queue/{__init__,ports}.py`.

Forbidden: do not import `arq`.

Implementation requirements: `JobId = NewType("JobId", str)`; `JobStatus = Literal["queued","running","done","failed"]`; `EnqueueOptions` dataclass (`queue_name: str | None, delay_s: int | None, max_retries: int = 3, idempotency_key: str | None`). `TaskQueue(Protocol)` async `enqueue(name: str, payload: Mapping[str, Any], *, options: EnqueueOptions | None) -> JobId`, `status(job_id: JobId) -> JobStatus`.

Tests required: Protocol satisfiability via in-memory fake.

Acceptance / Commands / Failures / Review: analogous.

#### Task : T-604 — `app/platform/rate_limit/ports.py` (`RateLimiter`)

Implementation requirements: `RateLimitDecision` (`allowed: bool, remaining: int, reset_after_s: int`); `RateLimiter.allow(key: str, *, quota: int, window_s: int) -> RateLimitDecision`.

Otherwise analogous to T-601/602.

#### Task : T-605 — `app/platform/idempotency/ports.py` (`IdempotencyStore`)

Implementation requirements: `IdempotencyRecord` (`status: Literal["new","in_flight","done"], response_hash: str | None`). `IdempotencyStore.begin(key: str, ttl_s: int) -> IdempotencyRecord`; `complete(key, response_hash) -> None`; `get(key) -> IdempotencyRecord | None`.

Otherwise analogous.

### Section S07 — Infrastructure base

> All adapters live under `app/infrastructure/*`. They may import `app.platform.*` to implement the ports and `app.shared`/`app.observability`. They must not be imported anywhere except `app.core.wiring.*`.

#### Task : T-701 — `app/infrastructure/db/`

Purpose: async SQLAlchemy engine, sessionmaker, declarative `Base`, pgvector type registration.

Depends on: T-301, T-203.

Allowed files: `app/infrastructure/__init__.py`, `app/infrastructure/db/__init__.py`, `app/infrastructure/db/engine.py`, `app/infrastructure/db/base.py`, `app/infrastructure/db/types.py`, `app/infrastructure/db/tests/test_engine.py`.

Forbidden: do not import `psycopg2`; do not create sessions outside this package (rule 4 §7 of AGENTS.md). No business logic.

Implementation requirements: `create_engine_from(settings) -> AsyncEngine`; `async_sessionmaker[AsyncSession]`; `Base = DeclarativeBase`; `types.py` registers `pgvector.sqlalchemy.Vector`. Session-per-request helper for use in `core.di`.

Tests required (integration): connect to Testcontainers Postgres+pgvector and `SELECT 1`.

Acceptance criteria: domain modules never construct `AsyncSession` themselves.

Commands: standard four + `make test-int`.

Common failure modes: synchronous engine; missing pgvector extension before type usage.

Review checklist: async engine, Base provided, pgvector registered.

#### Task : T-702 — `app/infrastructure/redis/` (+ Cache adapter)

Purpose: async Redis client + `Cache` adapter implementing `app.platform.cache.ports.Cache`.

Depends on: T-602, T-301.

Allowed files: `app/infrastructure/redis/{__init__,client,cache}.py`, `app/infrastructure/redis/tests/test_cache.py`.

Forbidden: do not import `redis` outside this package.

Implementation requirements: `build_client(settings) -> Redis`; `RedisCache(Cache)` implements every method; serialization keeps payloads as bytes; TTL respected.

Tests required (integration): contract test for `Cache` runs against real Redis (Testcontainers).

Acceptance: `lint-imports` clean; only `core.wiring.cache` imports this.

Commands: standard four + `make test-int`.

Common failure modes: leaking `Redis` object outside; missing `await client.aclose()` on shutdown.

Review checklist: implements full port; cleanup wired in lifespan.

#### Task : T-703 — `app/infrastructure/http/` shared httpx

Purpose: one configured `AsyncClient` for every external HTTP call (rule §7 of AGENTS.md).

Depends on: T-301.

Allowed files: `app/infrastructure/http/{__init__,client}.py`, `app/infrastructure/http/tests/test_client.py`.

Forbidden: do not import `requests` or `urllib.request`.

Implementation requirements: factory `build_http_client(settings) -> AsyncClient` with: connect/read timeouts from settings, `tenacity` retry policy on 5xx/connect-errors with jitter, OTel instrumentation enabled (`HTTPXClientInstrumentor`). Provide a typed helper `request_json` returning parsed JSON or raising `UpstreamProviderError`.

Tests required: respx-backed test asserts retries on 503 and surfaces `UpstreamProviderError` for 4xx that should not retry.

Acceptance: every provider adapter (S07/S12) uses this client; no direct `httpx.AsyncClient()` elsewhere.

Commands: standard four.

Common failure modes: retrying non-idempotent verbs; swallowing 4xx.

Review checklist: timeouts, retries, OTel, error wrapper.

#### Task : T-704 — `infrastructure/storage/local.py` (BlobStorage local)

Purpose: dev-only file-system adapter implementing `BlobStorage`.

Depends on: T-601, T-301.

Allowed files: `app/infrastructure/storage/{__init__,local}.py`, `app/infrastructure/storage/tests/test_local.py`.

Implementation requirements: writes to `settings.blob_storage.local_dir/<bucket>/<key>`; `presign_get` returns a `file://` URI (dev only); enforces path traversal protection.

Tests required: unit + contract suite for `BlobStorage` runs against the local adapter.

Acceptance: passes the BlobStorage contract suite (added next to ports tests).

Commands: standard four.

Common failure modes: path traversal via `../`; missing dir creation.

Review checklist: sanitized keys, contract test green.

#### Task : T-705 — *(REMOVED — deferred to Phase 3)*

The S3 `BlobStorage` adapter is **not** part of Phase 2. Reasoning: Phase 2 ships exactly the local-FS adapter (T-704). `aioboto3`, `moto`, and S3-specific settings/env keys do not enter Phase 2. When Phase 3 reintroduces this work, the task will be re-numbered and accompanied by an ADR.

#### Task : T-706 — `infrastructure/rate_limit/redis.py`

Purpose: Redis token-bucket adapter implementing `RateLimiter`.

Depends on: T-604, T-702.

Allowed files: `app/infrastructure/rate_limit/{__init__,redis}.py`, tests.

Implementation requirements: Lua script for atomic decrement; deterministic key namespace `rl:{key}`.

Tests required (integration): contract test for `RateLimiter`.

Otherwise analogous.

#### Task : T-707 — `infrastructure/idempotency/redis.py`

Purpose: Redis-backed `IdempotencyStore`.

Depends on: T-605, T-702.

Implementation requirements: SETNX with TTL; response-hash recorded on completion.

Otherwise analogous.

#### Task : T-708 — `core/wiring/storage.py`, `cache.py`

Purpose: bind ports to adapters per settings.

Depends on: T-704, T-702.

Allowed files: `app/core/wiring/__init__.py`, `app/core/wiring/storage.py`, `app/core/wiring/cache.py`, `app/core/wiring/tests/test_wiring_storage.py`, `app/core/wiring/tests/test_wiring_cache.py`.

Forbidden: this is the only place allowed to import `app.infrastructure.storage.*` and `app.infrastructure.redis.*`. Do not branch on `backend == "s3"` — S3 is Phase 3.

Implementation requirements: in Phase 2 only the local-FS adapter is wired (`settings.blob_storage.backend` must equal `"local"`); the wiring function returns a Protocol-typed `BlobStorage` (not the concrete class). A future Phase 3 task introduces the `"s3"` branch.

Tests required: wiring picks correct adapter per backend value.

Acceptance: container fields populated.

Commands: standard four.

Common failure modes: returning the concrete adapter type as the field type.

Review checklist: typed by Protocol, no leak.

### Section S08 — Persistence & migrations

#### Task : T-801 — Alembic init (async)

Purpose: schema migrations infrastructure with a single head.

Depends on: T-701.

Allowed files: `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/.gitkeep`.

Forbidden: do not run Alembic against sync drivers; do not import domain modules from `env.py` other than `Base.metadata`.

Implementation requirements: `env.py` uses async engine from `app/infrastructure/db/engine.py`; reads `DATABASE_URL` via `core.config.get_settings()`; `target_metadata = Base.metadata` (collects all `persistence.py` mapped classes via explicit imports listed in `env.py`).

Tests required: `alembic upgrade head` on empty DB succeeds; `alembic downgrade base` cleans up.

Acceptance: `make migrate` is the only way to apply schema.

Commands: standard four + `make test-int`.

Common failure modes: divergent heads; importing service code from env.

Review checklist: single head, async run, explicit metadata imports.

#### Task : T-802 — Initial migration (pgvector + base)

Purpose: create the `vector` extension and any base meta tables.

Depends on: T-801.

Allowed files: `alembic/versions/0001_init.py`.

Implementation requirements: `op.execute("CREATE EXTENSION IF NOT EXISTS vector")`; no domain tables in this migration (those land in their module tasks).

Tests required (integration): after upgrade, `SELECT extname FROM pg_extension WHERE extname='vector'` returns one row.

Acceptance: subsequent module migrations can declare `Vector` columns.

Commands: standard four + `make test-int`.

Common failure modes: relying on superuser-only extensions in CI; missing `IF NOT EXISTS`.

Review checklist: idempotent, no domain coupling.

#### Task : T-803 — DB session + pgvector round-trip integration test

Purpose: prove the DB stack works end-to-end before any module uses it.

Depends on: T-802.

Allowed files: `tests/integration/test_db_pgvector.py`.

Implementation requirements: temp table with a `Vector(3)` column; insert and read back; assert vector equality with tolerance.

Tests required: see above; marked `@pytest.mark.integration`.

Acceptance: green against Testcontainers Postgres+pgvector.

Commands: `make test-int`.

Common failure modes: missing extension; converting via numpy in production code (allowed only in test).

Review checklist: integration marker, no app-level fakes.

### Section S09 — Auth & Users

#### Task : T-901 — `app/auth/domain.py`

Purpose: pure domain types for auth.

Depends on: T-203.

Allowed files: `app/auth/__init__.py`, `app/auth/domain.py`, `app/auth/tests/test_domain.py`.

Forbidden: no FastAPI, SQLAlchemy, JWT, or Argon2 imports.

Implementation requirements: frozen dataclasses `Credentials`, `AuthenticatedUser` (`user_id: UserId, tenant_id: TenantId, scopes: frozenset[str]`), `AccessToken`/`RefreshToken` (`token: SecretStr-equivalent str`, `expires_at: datetime`). Domain errors `InvalidCredentialsError`, `RefreshReuseDetectedError` subclassing `AppError`.

Tests required: dataclass invariants; reuse-detection error has expected code.

Acceptance / Commands / Failures / Review: pure, frozen, no SDKs.

#### Task : T-902 — `app/auth/ports.py`

Purpose: declare outbound ports for identity, hashing, signing.

Depends on: T-901.

Allowed files: `app/auth/ports.py`.

Implementation requirements: `PasswordHasher.hash(plaintext)`, `verify(hash, plaintext)`; `TokenSigner.sign(claims) -> str`, `verify(token) -> Mapping[str, Any]`; `IdentityProvider.authenticate(creds) -> AuthenticatedUser` (placeholder for future external IdP). All Protocols.

Tests required: Protocol satisfiability against in-test fakes.

Otherwise standard.

#### Task : T-903 — `app/auth/adapters/argon2_hasher.py`

Purpose: implement `PasswordHasher` with Argon2id.

Depends on: T-902, T-301.

Allowed files: `app/auth/adapters/__init__.py`, `app/auth/adapters/argon2_hasher.py`, tests.

Forbidden: `argon2` imports anywhere else.

Implementation requirements: Argon2id with parameters from settings (`time_cost`, `memory_cost`, `parallelism`); `needs_rehash` exposed; raises `InvalidCredentialsError` on mismatch (do not leak `argon2.exceptions.*`).

Tests required: round-trip hash/verify; rehash flagged on parameter bump.

Otherwise standard.

#### Task : T-904 — `app/auth/adapters/jwt_signer.py`

Purpose: JWT signer with asymmetric keys.

Depends on: T-902, T-301.

Allowed files: `app/auth/adapters/jwt_signer.py`, tests.

Forbidden: `jwt`/`pyjwt` outside this file.

Implementation requirements: RS256 (or EdDSA) using `JwtSettings.private_key/public_key`; claims include `iss`, `aud`, `sub`, `tid` (tenant), `scope`, `iat`, `exp`, `jti`; clock-skew tolerance 30s; raises `AuthenticationError` on invalid token.

Tests required: sign-verify roundtrip; tampered token rejected; expired token rejected.

Otherwise standard.

#### Task : T-905 — `app/auth/persistence.py` + migration

Purpose: `users` (auth fragment), `refresh_tokens` tables.

Depends on: T-801, T-901.

Allowed files: `app/auth/persistence.py`, `alembic/versions/0002_auth.py`.

Forbidden: ORM types must not leave the module.

Implementation requirements: `UserRow` mapped class (`id`, `email`, `password_hash`, `created_at`, `tenant_id`, `disabled`); `RefreshTokenRow` (`id`, `user_id`, `family_id`, `hash`, `issued_at`, `expires_at`, `revoked_at`, `replaced_by`). Queries return **domain** types (`AuthenticatedUser`, etc.). Family-based rotation indexes.

Tests required (integration): migration creates tables; refresh insert + lookup round-trip.

Acceptance: zero `Row` types leaked outside.

Commands: standard four + `make test-int`.

Failures: leaking ORM rows; missing unique on `(family_id, replaced_by IS NULL)`.

Review: domain return types, indexes correct.

#### Task : T-906 — `app/auth/service.py` + `policies.py` + `deps.py`

Purpose: use-cases (register, login, refresh, logout) + FastAPI dependencies.

Depends on: T-902..T-905.

Allowed files: `app/auth/{service,policies,deps}.py`, tests.

Forbidden: FastAPI imports in `service.py`; SDK imports anywhere.

Implementation requirements

- `service.register(email, password) -> AuthenticatedUser` (idempotent on duplicate by raising `ConflictError`).
- `service.login(creds) -> tuple[AccessToken, RefreshToken]`.
- `service.refresh(refresh_token) -> tuple[AccessToken, RefreshToken]` — rotates and detects reuse. On detection: revoke the entire `family_id` chain, raise `RefreshReuseDetectedError`, emit audit log.
- `service.logout(refresh_token) -> None`.
- `policies.require_authenticated`, `require_scope(...)` callables for `Depends`.
- `deps.get_current_user(token) -> AuthenticatedUser` (FastAPI dep wrapping `policies`).

Tests required (unit): hashing, refresh rotation invariants, reuse detection.

Acceptance / Commands / Failures / Review: per AGENTS.md §11.

#### Task : T-907 — `app/auth/api.py`

Purpose: endpoints `register`, `login`, `refresh`, `logout`.

Depends on: T-906, T-501.

Allowed files: `app/auth/api.py`, `app/users` is unaffected.

Implementation requirements: Pydantic v2 request/response models in this file; raise `AppError` subclasses only; `responses=` declares Problem Details shapes; route prefix `/api/v1/auth`.

Tests required (api): see T-908.

#### Task : T-908 — Auth API tests + refresh-reuse detection

Purpose: enforce auth contract.

Depends on: T-907.

Allowed files: `app/auth/tests/test_api.py`, `tests/integration/test_auth_refresh_reuse.py`.

Implementation requirements: happy path register→login→refresh→logout; 401 on missing token; 422 on bad payload; Problem Details shape; `X-Request-ID` echo; refresh-reuse → entire family revoked + audit log emitted.

Acceptance: Phase 2 acceptance criterion #7 holds.

Otherwise standard.

#### Task : T-910 — `app/users/` minimal

Purpose: `GET /api/v1/users/me`.

Depends on: T-906.

Allowed files: `app/users/{__init__,domain,persistence,service,api,deps}.py` + tests + migration `0003_users.py` (profile columns separate from `users` auth fragment; or share table if your migration in T-905 already covers it — choose **share**, owning the table from `users` since auth only references `user_id`).

Forbidden: `app.users` must not import `app.auth.persistence` or `app.auth.adapters` (rule §3). Read-only domain types from `app.auth` only.

Implementation requirements: `User` profile dataclass; `GET /api/v1/users/me` returns the current user's profile; creation hook from auth.register emits a user-domain event that `users.service` consumes (in-process for Phase 2). Decision: in Phase 2, `auth.service.register` directly calls `users.service.create_profile(...)` via a port `UserProfileWriter` declared in `app.users.ports` and injected — keeping the dependency `auth → users` forbidden in the other direction.

> Re-evaluation: the dep-graph forbids `auth → users`. Therefore, profile creation must be driven from **users** side via an event subscriber, **not** by `auth.service` calling users. Implement an in-process pub/sub primitive in `app.shared.events` (added here if not yet present) and have `users.service` subscribe to `UserRegistered`. If introducing `app.shared.events` is too much for this task, **defer** profile auto-creation to a follow-up step but still expose `GET /users/me` reading from the `users` table populated lazily on first access (acceptable Phase 2 shortcut, documented).

Tests required: 401 unauthenticated; 200 with profile when authenticated.

Acceptance: dep-graph contract still passes (`auth → users` forbidden).

Otherwise standard.

### Section S10 — Prompts

#### Task : T-1001 — `app/prompts/{domain,ports,registry}.py`

Purpose: filesystem-backed versioned prompt registry.

Depends on: T-203.

Allowed files: `app/prompts/{__init__,domain,ports,registry}.py`, tests.

Forbidden: no `app.llm`/`app.embeddings` imports; no inline prompt strings.

Implementation requirements

- `Prompt` dataclass: `id: str, version: str (semver), description, owner, template: str (Jinja2 source), input_schema: type[BaseModel], output_schema: type[BaseModel] | None`.
- `PromptRegistry(Protocol)`: `get(id, version) -> Prompt`; `render(id, version, inputs: BaseModel) -> str` (validates with `input_schema`, renders Jinja2 with `StrictUndefined`).
- `FsPromptRegistry` default impl: scans `app/prompts/library/*.yaml`, resolves `input_schema` / `output_schema` via dotted paths.
- A YAML missing required fields raises `AppError` at startup.

Tests required: registry loads, validates, renders; missing input field raises `ValidationError`.

Otherwise standard.

#### Task : T-1002 — `library/rag_answer_v1.yaml` + IO schemas

Purpose: ship the only prompt Phase 2 needs.

Depends on: T-1001.

Allowed files: `app/prompts/library/rag_answer_v1.yaml`, `app/prompts/library/rag_answer_v1_schemas.py`.

Forbidden: do not put prompt text anywhere else.

Implementation requirements

- YAML declares: `id: rag_answer`, `version: 1.0.0`, `description`, `owner`, `template` (system+user messages, with placeholders `{{question}}` and a loop over `{{citations}}` exposing `{document_id, chunk_id, source, text}`), `input_schema: app.prompts.library.rag_answer_v1_schemas:RagAnswerInput`, `output_schema: app.prompts.library.rag_answer_v1_schemas:RagAnswerOutput`.
- Pydantic models: `RagAnswerInput { question: str, citations: list[CitationInput] }`, `RagAnswerOutput { answer: str }`.

Tests required: render with sample input; assert that the rendered prompt contains question and citation tokens; output schema validates a sample answer.

Otherwise standard.

#### Task : T-1003 — `app/prompts/api.py` (read-only)

Purpose: admin read-only inspection.

Depends on: T-1001, T-906.

Allowed files: `app/prompts/api.py`, tests.

Implementation requirements: `GET /api/v1/prompts` lists `{id, versions[]}`; `GET /api/v1/prompts/{id}/{version}` returns metadata only (no template body if a `confidential: true` flag is set in YAML; not used in Phase 2 but recognized). Requires authenticated admin scope (`prompts:read`).

Tests required: 401 unauth; 200 with admin scope; not present in OpenAPI for anonymous.

Otherwise standard.

#### Task : T-1004 — Registry render + schema-validation tests

Already partially covered by T-1001/T-1002. This task is the consolidated test file `app/prompts/tests/test_registry.py` with parameterized cases for all prompts present in the library.

Acceptance: any new prompt added later is auto-tested.

### Section S11 — LLM + embeddings ports (with fakes and contract tests)

#### Task : T-1100 — `app/ai_governance/{domain,ports}.py` (pre-llm interface only)

Purpose

- Land the **interface surface** of `ai_governance` (domain types + outbound ports + `GovernanceGate` Protocol) **before** `app.llm.service` (T-1102) can be implemented, so the LLM service can type its DI without a cyclic or forward dependency. The persistence/service/api/wiring of governance still live in S12.

Depends on: T-201, T-203.

Allowed files: `app/ai_governance/__init__.py`, `app/ai_governance/domain.py`, `app/ai_governance/ports.py`, `app/ai_governance/tests/test_domain.py`, `app/ai_governance/tests/test_ports.py`.

Forbidden

- No FastAPI, SQLAlchemy, provider SDKs, or `app.infrastructure.*` imports.
- Do **not** implement `service.py`, `persistence.py`, `events.py`, or `api.py` here — those land in S12 (T-1202..T-1205).
- Do not depend on `app.llm.*` or `app.embeddings.*`.

Implementation requirements

- `domain.py`: `BudgetPolicy(tenant_id, monthly_usd: Decimal, warning_threshold: float, model_allowlist: tuple[str, ...])`; `UsageEntry(tenant_id, model, tokens_in, tokens_out, cost_usd, occurred_at, request_id)`; `AllowDecision(allowed: bool, reason: str | None, warning: bool)`; `BudgetExceededError(code="budget-exceeded", status=409)`, `ModelNotAllowedError(code="model-not-allowed", status=403)` — both subclass `AppError`.
- `ports.py`: `UsageRepository(Protocol)` async `record(entry) -> None`, `monthly_usage_usd(tenant_id) -> Decimal`; `BudgetPolicyStore(Protocol)` async `get(tenant_id) -> BudgetPolicy`; `GovernanceGate(Protocol)` async `check_call_allowed(*, tenant_id, model, est_tokens) -> AllowDecision`.
- `__init__.py` re-exports **only** `BudgetPolicy`, `UsageEntry`, `AllowDecision`, `BudgetExceededError`, `ModelNotAllowedError`, `UsageRepository`, `BudgetPolicyStore`, `GovernanceGate`.

Tests required

- Dataclass invariants (immutability, value ranges).
- `AllowDecision` constructor combinations (allowed/denied × warning/no-warning).
- Protocol satisfiability of `GovernanceGate` against an in-test fake that always allows.

Acceptance criteria

- `app.llm.service` (T-1102) can import `from app.ai_governance.ports import GovernanceGate` without pulling persistence or service code.
- `lint-imports` remains clean.

Commands

```
make fmt
make lint
make typecheck
make test
```

Common failure modes

- Importing SQLAlchemy or FastAPI here.
- Implementing `service.py` or `persistence.py` prematurely.
- Forgetting to re-export the ports through `__init__.py`.

Review checklist

- Pure domain + Protocols only; no I/O imports; `__init__.py` is the public surface; `lint-imports` green.

#### Task : T-1101 — `app/llm/{domain,ports,observability,router}.py`

Purpose: domain types, ports, observation record, router.

Depends on: T-203, T-401.

Allowed files: `app/llm/__init__.py`, `app/llm/{domain,ports,observability,router}.py`, tests.

Forbidden: any provider SDK import; any HTTP call. No knowledge of OpenAI.

Implementation requirements

- `domain.py`: `ChatMessage(role: Literal["system","user","assistant","tool"], content: str)`; `ChatRequest(model: str, messages: tuple[ChatMessage, ...], temperature: float = 0.0, max_tokens: int | None, response_format: Literal["text","json"] = "text")`; `ChatResponse(content: str, tokens_in: int, tokens_out: int, finish_reason: str, raw_id: str)`; `UpstreamError(AppError)`.
- `ports.py`: `ChatModel(Protocol)` async `complete(req) -> ChatResponse`, `stream(req) -> AsyncIterator[str]`; `ModelRouter(Protocol)` `pick(intent: str) -> str` (returns model id).
- `observability.py`: `LLMCallObservation` frozen dataclass with the **11 mandatory fields** (provider, model, prompt_id, prompt_version, tokens_in, tokens_out, latency_ms, cost_usd, status, request_id, tenant_id). `record(observation)` writes structlog event `llm.call` and attaches the same attributes to the active OTel span (span name `llm.chat`).
- `router.py`: `DefaultModelRouter(intent_map: Mapping[str, str])` returning the configured model.

Tests required: ChatRequest immutability; observation serializes with all 11 fields; router picks expected model.

Acceptance: no SDK imports anywhere in `app/llm/`.

Otherwise standard.

#### Task : T-1102 — `app/llm/service.py` (governance + observation gate)

Purpose: single entrypoint for any LLM call.

Depends on: T-1101, T-1100 (governance domain + ports interface only; service stubs governance via DI port import from `app.ai_governance.ports`).

Allowed files: `app/llm/service.py`, tests.

Forbidden: provider SDK imports; bypassing governance.

Implementation requirements

- `LlmService(chat_model: ChatModel, router: ModelRouter, governance: GovernanceGate, prompts: PromptRegistry, clock: Clock, cost_calculator: CostCalculator)`. `GovernanceGate` is a typing alias imported from `app.ai_governance.ports` to keep the cyclic import legal (dep-graph allows `app.llm → app.ai_governance.ports`).
- `call_chat(*, intent: str, prompt_id: str, prompt_version: str, inputs: BaseModel, tenant_id: TenantId) -> ChatResponse`:
  1. resolve model via router.
  2. estimate tokens (use `prompts.render` + heuristic tokenizer in `app.llm.tokens` helper module created here).
  3. `decision = await governance.check_call_allowed(tenant_id=..., model=..., est_tokens=...)`; if denied, raise `BudgetExceededError` (no LLM call made).
  4. open OTel span `llm.chat` with attrs.
  5. call `chat_model.complete(req)`; on success, `record_usage(...)`; on failure, mark span error, record observation with `status="error"`, re-raise as `UpstreamProviderError`.
  6. emit `LLMCallObservation` with all 11 fields.
  7. attach soft `X-Budget-Warning` header via a returned `headers` field on the response (the API layer reads and sets it).
- `call_structured(...)` similar but `response_format="json"` and result validated against `output_schema` from prompt.

Tests required (unit, using fakes from T-1104): every code path emits an observation; budget-denied path makes zero provider calls; failure path records `status="error"` and re-raises sanitized.

Acceptance: rule §10 satisfied — all callers go through this service. Acceptance criterion #4 of Phase 2 has its source here.

Commands: standard four.

Common failure modes: forgetting governance check on the failure path (it must still happen before the call); leaking provider exception types.

Review checklist: 11 observation fields, governance call before provider call, sanitized errors.

#### Task : T-1103 — `app/embeddings/{domain,ports,service}.py`

Purpose: embedding domain types, port, batching service.

Depends on: T-203.

Allowed files: `app/embeddings/{__init__,domain,ports,service}.py`, tests.

Forbidden: provider SDK imports anywhere here.

Implementation requirements

- `Vector = NewType("Vector", tuple[float, ...])`; `EmbeddingRequest(model: str, inputs: tuple[str, ...])`; `EmbeddingResponse(vectors: tuple[Vector, ...], tokens: int)`.
- `EmbeddingModel(Protocol)` async `embed(req) -> EmbeddingResponse`.
- `EmbeddingsService.embed_batch(model: str, texts: Iterable[str], *, batch_size: int = 96) -> tuple[Vector, ...]` with retry-aware chunking.
- Note: embeddings do not currently flow through `ai_governance` in Phase 2 (per scope), but cost is still recorded via observability span `embeddings.embed`.

Tests required: batching boundary cases; retries via fake.

Otherwise standard.

#### Task : T-1104 — Fake `ChatModel` + fake `EmbeddingModel`

Purpose: provide test doubles used by every LLM-touching test in Phase 2. **Mandatory before OpenAI adapters.**

Depends on: T-1101, T-1103.

Allowed files: `app/llm/testing/fakes.py`, `app/embeddings/testing/fakes.py`, `app/llm/tests/test_fakes.py`, `app/embeddings/tests/test_fakes.py`.

Forbidden: do not place fakes outside the `testing/` subpackages of their respective modules; do not import these from production code.

Implementation requirements

- `FakeChatModel(ChatModel)`: in-memory, scripted responses by request matcher; deterministic token counts; configurable failure injection.
- `FakeEmbeddingModel(EmbeddingModel)`: deterministic vectors derived from text hash with configurable dimension.

Tests required: contract tests (T-1105/T-1106) run against these fakes by default.

Acceptance: any later test that needs to "call an LLM" uses these fakes unless explicitly an `@pytest.mark.contract_openai` test.

Commands: standard four.

Failures: importing fakes from production; non-deterministic behavior.

Review checklist: testing subpackage, deterministic, no SDK imports.

#### Task : T-1105 — ChatModel contract test suite

Purpose: parameterized test suite every `ChatModel` adapter must pass.

Depends on: T-1101, T-1104.

Allowed files: `app/llm/tests/contract.py` (importable test base), `app/llm/tests/test_contract_fake.py`.

Implementation requirements: tests cover: happy path; error mapping (provider 5xx → `UpstreamProviderError`); empty messages rejected; `response_format="json"` returns parseable JSON. The OpenAI adapter test reuses this base.

Acceptance: every adapter parameterizes this suite. Failing the suite blocks merge.

Otherwise standard.

#### Task : T-1106 — EmbeddingModel contract test suite

Same shape as T-1105 for embeddings. Includes: dimension consistency across calls; batching equivalence to single-call results within tolerance for fakes; provider error mapping.

### Section S12 — ai_governance persistence/service/api + OpenAI adapters

> The `domain.py` + `ports.py` of `ai_governance` already landed in T-1100 (S11). S12 fills in persistence, service, events, API, and the OpenAI provider adapters.

#### Task : T-1202 — `app/ai_governance/persistence.py` + migration

Purpose: tables `usage_entries`, `budget_policies`, `model_allowlists`; queries returning domain types.

Depends on: T-1100, T-801.

Allowed files: `app/ai_governance/persistence.py`, `alembic/versions/0004_ai_governance.py`, tests.

Implementation requirements: indexes for `(tenant_id, occurred_at)`; `cost_usd` stored as `Numeric(12,6)`; sum query for monthly usage.

Tests required (integration): insert/sum round-trip with Decimal precision.

Otherwise standard.

#### Task : T-1203 — `app/ai_governance/service.py`

Purpose: implement `GovernanceGate` and `record_usage`.

Depends on: T-1100, T-1202.

Allowed files: `app/ai_governance/service.py`, tests.

Implementation requirements

- `check_call_allowed(*, tenant_id, model, est_tokens)`:
  - load policy; if `model not in policy.model_allowlist`, deny with `ModelNotAllowedError`.
  - `current = await repo.monthly_usage_usd(tenant_id)`.
  - estimate incremental cost from `CostCalculator` (small helper module here using a static price table loaded from settings — no inline hardcoding outside the table file).
  - if `current + est_cost >= policy.monthly_usd`: deny → `BudgetExceededError` (code `"budget-exceeded"`).
  - if `current + est_cost >= 0.8 * policy.monthly_usd`: allow with `warning=True`.
- `record_usage(*, tenant_id, model, tokens_in, tokens_out, cost_usd, request_id) -> None`: persists entry **and** emits `AIUsageAuditEvent` via T-1204.
- `pick_fallback(model) -> str | None` consulting allowlist.

Tests required: 0-budget → deny; under-budget → allow without warning; 80% → allow with warning; over-budget → deny + no call made; not-allowlisted model → deny.

Acceptance: Phase 2 acceptance criterion #6 holds when wired to `app.llm.service`.

Otherwise standard.

#### Task : T-1204 — `events.py` + audit emit

Purpose: structured audit events.

Depends on: T-1203.

Allowed files: `app/ai_governance/events.py`, tests.

Implementation requirements: `AIUsageAuditEvent` dataclass; emitter logs via structlog with `event="ai.usage.audit"`, request_id, tenant_id, model, tokens, cost, timestamp. No external sink in Phase 2; structlog only.

Tests required: emitting event produces a log record with all fields.

Otherwise standard.

#### Task : T-1205 — `app/ai_governance/api.py` (read-only)

Purpose: admin visibility.

Depends on: T-1203, T-906.

Allowed files: `app/ai_governance/api.py`, tests.

Implementation requirements: `GET /api/v1/governance/budgets` and `GET /api/v1/governance/usage` (per current tenant); admin-only scope (`governance:read`).

Otherwise standard.

#### Task : T-1206 — Budget tests (deny / warning / audit)

Purpose: focused tests for Phase 2 acceptance criterion #6 and audit emit.

Allowed files: `tests/integration/test_governance.py`.

Implementation requirements: integration test using fake `ChatModel` to assert that `LLM_MONTHLY_BUDGET_USD=0` causes `POST /rag/ask` to return Problem Details `409 budget-exceeded` **without** invoking the chat model. (This test depends on later S16; mark it `xfail` until T-1602 lands or place under S17.)

#### Task : T-1210 — `infrastructure/llm_providers/openai.py` (ChatModel adapter)

Purpose: the **only** file allowed to import `openai`. Implements `ChatModel` via the OpenAI SDK using the shared HTTP client where possible; otherwise the SDK's own client configured with the same timeouts.

Depends on: T-1101, T-1105, T-703, T-301.

Allowed files: `app/infrastructure/llm_providers/__init__.py`, `app/infrastructure/llm_providers/openai.py`, `app/infrastructure/llm_providers/tests/test_openai_chat.py`. `pyproject.toml` (add `openai`).

Forbidden: importing `openai` anywhere else. Returning SDK types from any method. Logging full prompt content at INFO.

Implementation requirements

- Translate `ChatRequest` to OpenAI Chat Completions params; translate response to `ChatResponse`.
- Map SDK errors: timeouts/5xx → `UpstreamProviderError` (status 502); 401/403 → `AuthenticationError` (do not leak key); 429 → `RateLimitedError`.
- Token counts from response usage; latency measured around the SDK call only.
- Respect `OPENAI_BASE_URL` (for OpenAI-compatible endpoints).

Tests required: contract suite from T-1105 parameterized over the OpenAI adapter, using `respx` to fake the HTTP layer. **No real OpenAI calls in CI.**

Acceptance: T-1105 contract suite passes; type stubs ok; no SDK leak.

Commands: standard four.

Failures: SDK type leaks; missing key handling; logging prompts.

Review checklist: SDK confined, error mapping, contract green.

#### Task : T-1211 — `infrastructure/embedding_providers/openai.py`

Purpose: embeddings adapter. Same shape as T-1210, implementing `EmbeddingModel`.

Depends on: T-1103, T-1106, T-703, T-301.

Allowed files: `app/infrastructure/embedding_providers/{__init__,openai}.py`, tests.

Implementation requirements: batch size capped to model limit; vectors converted to immutable `tuple[float, ...]`; token usage propagated.

Otherwise standard.

#### Task : T-1212 — `core/wiring/{llm,embeddings,governance}.py`

Purpose: bind ports to adapters and build `LlmService` from `Container`.

Depends on: T-1210, T-1211, T-1203, T-708.

Allowed files: `app/core/wiring/{llm,embeddings,governance}.py`.

Forbidden: any of these may import `app.infrastructure.*`; no other module may.

Implementation requirements: build `LlmService` with: `ChatModel` adapter, `DefaultModelRouter` from settings, governance gate from `ai_governance.service`, prompt registry, system clock, cost calculator. Add to `Container`.

Tests required: wiring smoke test boots in-process and verifies field types match Protocols.

Otherwise standard.

### Section S13 — Documents (domain + persistence + API skeleton)

#### Task : T-1301 — `app/documents/{domain,ports}.py`

Purpose: pure types and outbound ports for parsing/chunking.

Depends on: T-203.

Allowed files: `app/documents/__init__.py`, `app/documents/{domain,ports}.py`, tests.

Forbidden: no FastAPI, no SQLAlchemy, no parser SDK imports here.

Implementation requirements

- `domain.py`: `Document(id: DocumentId, tenant_id, source_uri: str | None, content_type: str, status: Literal["pending","processing","ready","failed"], created_at, ready_at, failure_reason: str | None)`; `Chunk(id: ChunkId, document_id, ordinal: int, text: str, token_count: int, page: int | None, section: str | None, hash: str)`; `ChunkStrategy(name: Literal["recursive_token"], target_tokens: int, overlap_tokens: int)`.
- `ports.py`: `DocumentParser(Protocol)` `parse(blob: AsyncIterator[bytes], content_type: str) -> AsyncIterator[ParsedPage]`; `Chunker(Protocol)` `chunk(pages: Iterable[ParsedPage], strategy: ChunkStrategy) -> Iterable[Chunk]`.

Tests required: dataclass invariants; status transitions are validated.

Otherwise standard.

#### Task : T-1302 — `app/documents/parsers/` (txt, md, html, pdf)

Purpose: implement `DocumentParser` per content type.

Depends on: T-1301.

Allowed files: `app/documents/parsers/{__init__,txt,markdown,html,pdf}.py`, tests. `pyproject.toml` adds `pypdf`, `beautifulsoup4`.

Forbidden: importing `pypdf`/`bs4` outside this folder.

Implementation requirements: dispatch by content type; each parser yields `ParsedPage(page: int | None, text: str, section: str | None)`. PDF parser uses `pypdf`; HTML uses `bs4` with safe text extraction; markdown via pure-Python parser (no shell out). Reject unsupported content types with `ValidationError`.

Tests required: golden-file tests for each parser; PDF round-trip on a 2-page fixture.

Otherwise standard.

#### Task : T-1303 — `app/documents/chunkers/` (recursive token-aware)

Purpose: produce `Chunk` items with token-aware splitting.

Depends on: T-1301. `pyproject.toml` adds `tiktoken`.

Allowed files: `app/documents/chunkers/{__init__,recursive}.py`, tests.

Forbidden: `tiktoken` outside this folder.

Implementation requirements: recursive splitter using `tiktoken` encoder selected by configured embedding model family; overlap honored; deterministic chunk hashes.

Tests required: chunk count and overlap invariants on a known text; deterministic hash.

Otherwise standard.

#### Task : T-1304 — `app/documents/persistence.py` + migration

Purpose: `documents` and `chunks` tables, plus the embeddings table that `pgvector` adapter will write into.

Depends on: T-801.

Allowed files: `app/documents/persistence.py`, `alembic/versions/0005_documents.py`.

Forbidden: ORM types leaking outside the module.

Implementation requirements

- `documents` columns: `id PK`, `tenant_id`, `source_uri`, `content_type`, `status`, `created_at`, `ready_at`, `failure_reason`, `blob_ref_bucket`, `blob_ref_key`, `byte_size`. Index on `(tenant_id, status)`.
- `chunks`: `id PK`, `document_id FK`, `ordinal`, `text`, `token_count`, `page`, `section`, `hash`. Unique `(document_id, ordinal)`.
- `embeddings` table (owned here per scope §5): `chunk_id FK PK`, `embedding Vector(<dim>)`, `model TEXT`, `created_at`. Dimension parameterized via Alembic op constant (must match configured embedding model).
- Read functions return only domain types: `Document`, `Chunk`.

Tests required (integration): table creation; round-trip; cascade on document delete.

Otherwise standard.

#### Task : T-1305 — `app/documents/api.py` POST/GET

Purpose: ingestion entrypoint + status read.

Depends on: T-1304, T-906, T-501.

Allowed files: `app/documents/api.py`, tests.

Forbidden: doing parse/embed work in the request path.

Implementation requirements

- `POST /api/v1/documents` (multipart upload **or** `{source_uri}` JSON): persist `Document(status="pending")`, store blob via `BlobStorage`, enqueue ingestion job via `TaskQueue` (job name `documents.ingest`), return `202 Accepted` with `{document_id, status: "pending", tracking_url}`.
- `GET /api/v1/documents/{id}` returns `{id, status, ready_at, failure_reason}`. 404 if not owned by current tenant.
- Idempotency: depends on `app.api.idempotency.IdempotencyKey`.

Tests required (api): 202 on upload; 401/422 paths; idempotent re-POST; 404 cross-tenant.

Otherwise standard.

### Section S14 — Queue + worker + ingestion service

#### Task : T-1401 — `app/infrastructure/queue/arq.py` (TaskQueue adapter)

Purpose: implement `TaskQueue` over Arq.

Depends on: T-603, T-301.

Allowed files: `app/infrastructure/queue/{__init__,arq}.py`, tests.

Forbidden: `arq` outside this file.

Implementation requirements: `ArqTaskQueue(TaskQueue)`: `enqueue` serializes payload as JSON, attaches `request_id` (current `request_id_var`) and `tenant_id`, sets idempotency key as Arq `_job_id` if provided. Configure retries via `EnqueueOptions`. Provide `WorkerSettings` factory consumed by `core.wiring.queue`.

Tests required (integration): submit a noop job, assert it runs once.

Otherwise standard.

#### Task : T-1402 — `core/wiring/queue.py` + worker entrypoint

Purpose: the worker boots through the **same** composition root as the API.

Depends on: T-1401, T-504.

Allowed files: `app/core/wiring/queue.py`.

Forbidden: defining a second container or settings reader for the worker.

Implementation requirements

- `WorkerSettings`: Arq config with `functions = [documents.ingestion.ingest_document]` (function objects registered here), `on_startup`/`on_shutdown` hooks that initialize the same `Container` via `core.lifespan.startup_container(settings)` and tear it down.
- `make worker` runs `arq app.core.wiring.queue.WorkerSettings`.
- Job context exposes `container` so handlers can resolve services.

Tests required (integration): worker startup populates the container with the same field types as the API (assert types match Protocols).

Acceptance: API and worker cannot diverge in wiring.

Otherwise standard.

#### Task : T-1403 — `app/documents/ingestion.py` + `service.py`

Purpose: the actual ingestion job — pure code that lives in `documents` and uses ports only.

Depends on: T-1301..T-1305, T-1402, T-1103, T-1501 (Vector store interface).

Allowed files: `app/documents/{service,ingestion}.py`, tests.

Forbidden: importing `arq`, `openai`, `pypdf`, `tiktoken` directly here (use ports).

Implementation requirements

- `ingest_document(ctx, *, document_id, tenant_id, request_id)` (Arq-job signature with `ctx` typed as `Mapping[str, Any]` so this file does not import Arq):
  1. set `request_id_var`;
  2. load `Document` and `BlobRef`;
  3. transition status to `processing`;
  4. parse via `DocumentParser` chosen by content type;
  5. chunk via `Chunker`;
  6. embed via `EmbeddingsService.embed_batch` (model id from settings);
  7. persist chunks + embeddings via `VectorStore.upsert(...)` (port from `app.rag.ports`);
  8. transition status to `ready`. On any failure: status `failed`, `failure_reason` set, structured error log, audit emit, no swallow.
- `service.create_document` is the helper used by the POST endpoint.

Tests required (integration): with fake `EmbeddingModel`, ingest a small text document end-to-end; status transitions observed; chunks present.

Acceptance: status transitions `pending → processing → ready` visible via GET endpoint.

Otherwise standard.

#### Task : T-1404 — Integration test for enqueue → run → status

Allowed files: `tests/integration/test_documents_ingestion.py`.

Implementation requirements: real Postgres + Redis (Testcontainers), real Arq worker started in-process; upload a TXT; poll status until `ready` (timeout 30s); assert chunks count > 0.

Tests required: see above.

Otherwise standard.

### Section S15 — Vector store

#### Task : T-1501 — `app/rag/ports.py` (VectorStore)

Purpose: declare the VectorStore port owned by `rag` (per dep-graph table §4).

Depends on: T-203.

Allowed files: `app/rag/__init__.py`, `app/rag/ports.py`, tests.

Forbidden: no `pgvector`/`qdrant_client` imports here.

Implementation requirements: `VectorRecord(chunk_id, document_id, tenant_id, vector, metadata: Mapping[str,Any])`; `RetrievedChunk(chunk_id, document_id, score, text, page, section, source_uri)`; `VectorStore(Protocol)` async `upsert(records: Sequence[VectorRecord]) -> None`, `search(*, tenant_id, query_vector, top_k, filters: Mapping[str,Any] | None) -> Sequence[RetrievedChunk]`.

Tests required: Protocol satisfiability against an in-memory fake.

Otherwise standard.

#### Task : T-1502 — `app/infrastructure/vector_stores/pgvector.py`

Purpose: pgvector implementation of `VectorStore`.

Depends on: T-1501, T-1304 (embeddings table), T-701.

Allowed files: `app/infrastructure/vector_stores/{__init__,pgvector}.py`, tests.

Forbidden: importing `pgvector` outside this file.

Implementation requirements: bulk upsert via SQLAlchemy `insert(...).on_conflict_do_update(...)`; search via cosine distance (`<=>`) with optional metadata filters; join with `chunks` to assemble `RetrievedChunk` fields (`text`, `page`, `section`); enforce tenant filter in `WHERE`. Hybrid (BM25) deferred to Phase 3 (documented).

Tests required (integration): insert 100 records; search returns top-k ordered by similarity; tenant filter respected. **Do not** fake pgvector here.

Acceptance: Phase 2 acceptance criterion (real pgvector retrieval) holds.

Otherwise standard.

#### Task : T-1503 — `app/core/wiring/vector_store.py`

Purpose: bind `VectorStore` port to pgvector adapter.

Depends on: T-1502.

Allowed files: `app/core/wiring/vector_store.py`.

Implementation requirements: returns a Protocol-typed instance; added to `Container`.

Otherwise standard.

#### Task : T-1504 — Integration test for real pgvector similarity

Allowed files: `tests/integration/test_vector_store_pgvector.py`.

Implementation requirements: build deterministic embeddings via `FakeEmbeddingModel`; insert; search; assert ordering matches expectation.

### Section S16 — RAG

#### Task : T-1601 — `app/rag/{domain,pipeline,service}.py`

Purpose: domain + pipeline + service.

Depends on: T-1501, T-1103, T-1102, T-1001.

Allowed files: `app/rag/{domain,pipeline,service}.py`, tests.

Forbidden: SDK imports; inline prompts; calls to LLM outside `app.llm.service`.

Implementation requirements

- `domain.py`: `Query(question: str, top_k: int = 5, filters: Mapping[str,Any] | None)`; `Citation(document_id, chunk_id, source_uri: str | None, page: int | None, section: str | None, preview: str)`; `Answer(text: str, citations: tuple[Citation, ...])`.
- `pipeline.py`: pure orchestration steps as small functions: `embed_query`, `retrieve`, `attach_citations`, `compose_prompt_inputs`. No I/O directly; takes ports as parameters.
- `service.py`: `RagService.ask(query: Query, *, tenant_id) -> Answer`:
  1. embed the question via `EmbeddingModel` (one call only — direct, not batch).
  2. `retrieve` top-k from `VectorStore`.
  3. build `RagAnswerInput { question, citations: [...preview...] }`.
  4. call `LlmService.call_structured(intent="rag.answer", prompt_id="rag_answer", prompt_version="1.0.0", inputs=..., tenant_id=...)`. The governance check runs inside `LlmService`.
  5. construct `Answer` with citations matched 1:1 to retrieved chunks.
- Must never return an Answer with empty citations when retrieval returned ≥ 1 chunk. If retrieval is empty: return `Answer(text=<no-context fallback>, citations=())` — still go through `LlmService` so observation is emitted.

Tests required (unit, using fakes): pipeline returns citations; structured output validated against `RagAnswerOutput`; governance-denied surfaces `BudgetExceededError`.

Acceptance: rule §15 / AGENTS.md "RAG answers must include citations" holds.

Otherwise standard.

#### Task : T-1602 — `app/rag/api.py` POST `/rag/ask`

Purpose: the second golden-path endpoint.

Depends on: T-1601, T-501.

Allowed files: `app/rag/api.py`, tests.

Implementation requirements: Pydantic request `{question: str, top_k: int = 5, filters: dict | None}`; response `{answer: str, citations: [{document_id, chunk_id, source_uri, page, section, preview}], request_id: str}`. `X-Budget-Warning` header propagated if present.

Tests required: see T-1603.

Otherwise standard.

#### Task : T-1603 — RAG unit + API tests

Allowed files: `app/rag/tests/test_api.py`, `tests/api/test_rag_ask.py`.

Implementation requirements: happy path returns ≥1 citation when documents exist; auth 401; validation 422; Problem Details on `BudgetExceededError`; `X-Request-ID` echo; with `LLM_MONTHLY_BUDGET_USD=0`, request returns 409 `budget-exceeded` and `FakeChatModel` is not invoked (assert via a counter).

Acceptance: Phase 2 acceptance criteria #6 and #8 hold for RAG.

Otherwise standard.

### Section S17 — Golden-path integration

#### Task : T-1701 — End-to-end golden-path test

Purpose: the single test that proves Phase 2 works.

Depends on: every previous task.

Allowed files: `tests/integration/test_golden_path.py`.

Implementation requirements

- Boot api+worker+postgres+redis via Testcontainers or `make up` (mark `slow`).
- Register a user, log in.
- `POST /api/v1/documents` uploading a 2-page PDF fixture; assert 202.
- Poll `GET /api/v1/documents/{id}` until status `ready` (≤ 30s).
- `POST /api/v1/rag/ask {"question": "<known content question>"}` using **FakeChatModel** wired via env switch (`LLM_PROVIDER=fake`) so CI never calls OpenAI.
- Assert: 200; `answer` non-empty; at least one citation; `citation.document_id` matches the uploaded id; `X-Request-ID` echoes if inbound.

Acceptance: Phase 2 acceptance criterion #3 holds.

Otherwise standard.

#### Task : T-1702 — `LLMCallObservation` 11-field assertion

Allowed files: `tests/integration/test_observation_fields.py`.

Implementation requirements: capture structured log emitted by `LlmService` for the golden path; assert every one of the 11 required fields is present and non-null. Fail loudly on any missing key.

Acceptance: Phase 2 acceptance criterion #4 holds.

#### Task : T-1703 — Continuous-trace assertion

Allowed files: `tests/integration/test_trace_continuity.py`.

Implementation requirements: install an in-memory OTel `InMemorySpanExporter` (via test wiring override), run the golden-path ask, and assert that spans `rag.ask → embeddings.embed → vector_store.search → llm.chat` form one connected trace (single `trace_id`, parent-child links).

Acceptance: Phase 2 acceptance criterion #5 holds.

### Section S18 — Documentation & hardening

#### Task : T-1801 — Update `docs/architecture.md`, `docs/folder-structure.md`, `docs/dependency-graph.md`

Purpose: align legacy docs with what Phase 2 actually ships (per scope §7).

Allowed files: the three docs.

Implementation requirements: update tables and diagrams to reflect `platform/`, `ai_governance`, Arq in Phase 2, adapter list. Mark sections that referred to Phase 3 features as "Phase 3".

Acceptance: docs no longer contradict the Phase 2 revision pack.

#### Task : T-1802 — Update `README.md` quickstart + golden-path walkthrough

Allowed files: `README.md`.

Implementation requirements: `make up`, register user, upload document, ask question, expected response shape, where to find OTel traces. No secrets.

#### Task : T-1803 — Mark ADR-0009 Superseded; cross-link 0018–0022

Allowed files: `docs/adr/0009-background-jobs-arq.md`, `docs/adr/README.md`.

Implementation requirements: ADR-0009 gets a `Status: Superseded by ADR-0022` header line; `docs/adr/README.md` index updated.

#### Task : T-1804 — Final `make check`

Purpose: prove Phase 2 closure.

Allowed files: none (read-only run).

Commands

```
make fmt
make lint
make typecheck
make test
make test-int
make check
```

Acceptance: every Phase 2 acceptance criterion (4-§8) is verified green.

---

## 6. Final golden-path acceptance test (summary)

The acceptance bar for closing Phase 2 is **mechanically** the union of:

1. `make check` returns 0 on a clean checkout.
2. `lint-imports` reports zero violations.
3. `tests/integration/test_golden_path.py` passes (T-1701) using the **fake** LLM provider in CI.
4. `tests/integration/test_observation_fields.py` proves all 11 `LLMCallObservation` fields are present (T-1702).
5. `tests/integration/test_trace_continuity.py` proves a continuous trace across `rag.ask → embeddings.embed → vector_store.search → llm.chat` (T-1703).
6. `tests/integration/test_governance.py` proves `LLM_MONTHLY_BUDGET_USD=0` yields RFC 9457 `409 budget-exceeded` with zero provider calls (T-1206 + T-1603).
7. Auth refresh-reuse test (T-908) proves family revocation and audit emit.
8. Every error path in API tests returns Problem Details and `X-Request-ID`.
9. Manual smoke against `make up` with a real OpenAI key reproduces the golden-path against the real provider (operator-run, optional but recommended before tag).

---

## 7. Final review checklist (used by human and reviewer model on every PR)

- Architecture
  - [ ] No new top-level folder under `app/` outside the established set.
  - [ ] No `app.infrastructure.*` import outside `app.core.wiring.*`.
  - [ ] No `app.platform.*` → `app.infrastructure.*` import.
  - [ ] No SDK import outside its dedicated adapter file.
  - [ ] No `os.environ` outside `app/core/config/`.
  - [ ] No cross-module persistence/adapters imports.
- Types & layering
  - [ ] `domain.py` is pure; no FastAPI / SQLAlchemy / httpx / SDK imports.
  - [ ] `service.py` returns domain types only.
  - [ ] `api.py` returns Pydantic response models only; never ORM objects.
  - [ ] `persistence.py` mapped classes never leave the module.
- LLM
  - [ ] No inline prompt strings.
  - [ ] Every LLM call goes through `app.llm.service`.
  - [ ] Governance gate consulted **before** the provider call.
  - [ ] `LLMCallObservation` has all 11 fields populated.
- Errors
  - [ ] No `except Exception: pass` or bare `except`.
  - [ ] All raised errors subclass `AppError`.
  - [ ] No raw provider responses or stack traces in error bodies.
  - [ ] Every error response is `application/problem+json`.
- Observability
  - [ ] All logs via `structlog` (no `print`, no ad-hoc `logging.getLogger`).
  - [ ] Every response carries `X-Request-ID`.
  - [ ] External HTTP via `app/infrastructure/http/` only.
- Tests
  - [ ] Unit + API + integration tests added per task table.
  - [ ] Contract tests parameterized for new adapters.
  - [ ] No skipped/xfailed tests left in tree.
  - [ ] Coverage ≥ 80% on `app/`.
- Migrations
  - [ ] Single Alembic head.
  - [ ] `alembic upgrade head` and `downgrade base` both succeed.
- Imports
  - [ ] `lint-imports` exit 0.
  - [ ] No new contract `ignore_imports` entries beyond §03.

---

## 8. Instructions for the lower-complexity implementation model

You are an executor, not a designer. Follow these rules without exception:

1. **One task at a time.** Pick the next unfinished task from §4 (lowest task id within the earliest unfinished section). Do not skip ahead. Do not interleave.
2. **Read AGENTS.md and this file before every task.** If anything is ambiguous, stop and report — do not invent behavior.
3. **Respect "Allowed files".** You may create/modify only files explicitly listed for the current task, plus `app/<module>/__init__.py` re-exports when re-exporting a new symbol added in the same task. Editing any other file is a failure.
4. **Respect "Forbidden".** Forbidden imports/files/patterns must not appear. If you think you need them, stop and report.
5. **Implement the "Implementation requirements" literally.** Do not optimize, generalize, or add abstractions. Do not add features not listed.
6. **Write the listed tests.** Tests must fail before the implementation and pass after.
7. **Run the listed Commands.** A task is not done until they all succeed. Always run `make lint typecheck test` at minimum. Run `make test-int` and `make check` when listed.
8. **Do not bypass quality gates.** No `# type: ignore` without rule code + one-line reason. No `noqa` without a code. No `@pytest.mark.skip` to silence failure. No deleting failing tests.
9. **Update `importlinter.toml` and `docs/dependency-graph.md` in the same task** when introducing a new allowed edge.
10. **Report after each task:** files created/modified, tests added, commands executed, all command outputs (or final status), and any unresolved issues. If a task can't be completed without violating a rule, **stop and report** — do not modify other files to make it work.
11. **Never invent prompts.** All prompts live in `app/prompts/library/*.yaml` (T-1002 is the only Phase 2 prompt).
12. **Never call provider SDKs directly.** All providers are accessed via `app.llm.service` / `app.embeddings.service` and adapters wired in `app.core.wiring.*`.
13. **Stop signals.** Stop and request guidance when: (a) a contract would need to be weakened, (b) a forbidden import seems required, (c) a test from a previous task is failing after your change, (d) a dependency listed in "Depends on" is not yet complete.

Final reminder: the lower-complexity model is **not authorized** to make architectural decisions. If the plan is wrong or incomplete, report — do not "fix it".

---

## 9. Instructions for the reviewer model

You are a strict reviewer. Approve only when every item below is true.

1. **AGENTS.md compliance.** Re-check every rule in §2 (Global rules) and AGENTS.md §2/§7 against the diff. Any violation → reject.
2. **ADR compliance.** Re-check ADRs 0018 (platform), 0019 (ai_governance), 0020 (golden path), 0021 (rename), 0022 (Arq). Any deviation → reject.
3. **Imports.** Manually verify (and confirm `lint-imports` confirms):
   - No `app.infrastructure.*` import outside `app.core.wiring.*`.
   - No SDK import outside its adapter file.
   - No cross-module persistence/adapters reach-in.
4. **Layers.** Domain code does not import FastAPI, SQLAlchemy, httpx, or any SDK.
5. **Tests.** Every change is covered by a test of the right kind (unit / api / integration / contract). No xfail, skip, or weakening. Coverage ≥ 80%.
6. **Types.** `mypy --strict` clean on `app/`. Every `# type: ignore` carries a rule code and a one-line reason.
7. **Observability.** All logs via structlog. Every external HTTP via `app/infrastructure/http/`. Every LLM call records an `LLMCallObservation` with all 11 fields and opens an OTel span.
8. **Errors.** All errors are `AppError` subclasses and serialize as RFC 9457 Problem Details at the edge. No stack traces, SQL, secrets, or provider raw bodies in error bodies.
9. **Scope discipline.** No new top-level folders, no new dependencies beyond the task's allow-list, no out-of-scope features. **Reject broad, clever, or architecture-changing changes.** If unsure whether something is in scope: reject.
10. **Documentation.** New edges in the dependency graph or new ports require `importlinter.toml` and dep-graph doc updates in the same PR.
11. **ADR for architectural deltas.** Any change that affects a public interface, dependency, or rule requires an ADR.

When approving, the reviewer model must explicitly confirm: *"Verified against AGENTS.md, ADRs 0018–0022, importlinter contracts, and the §7 review checklist of IMPLEMENTATION_PLAN.md."*
