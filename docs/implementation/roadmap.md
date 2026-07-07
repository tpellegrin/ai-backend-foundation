# Phase 2 Implementation Roadmap

> Living status board for every task defined in [`IMPLEMENTATION_PLAN.md`](../../IMPLEMENTATION_PLAN.md).
> The authoritative spec of each task lives in [`./tasks/T-XXX.md`](./tasks/); this file only tracks **status** and a one-sentence summary.
> Companion docs: [`./rules.md`](./rules.md) · [`./review.md`](./review.md) · [`../ai/review-task.md`](../ai/review-task.md).

---

## Status legend

- `[x]` — **Done.** Task is fully implemented, committed to `main`, and has received a **PASS** review per [`../ai/review-task.md`](../ai/review-task.md). All `Commands` from the task file succeed on `main`.
- `[~]` — **In progress / under review.** A branch or PR exists, but review has not returned **PASS** (or review returned **PASS WITH MINOR ISSUES** with unresolved patches).
- `[!]` — **Blocked.** A stop signal (see [`./rules.md`](./rules.md) §6) is open against this task.
- `[ ]` — **Not started** or status uncertain.

Only `[x]` implies "committed to `main` and reviewed". Every other marker is provisional.

---

## Rules for updating this file

The roadmap is a **status mirror**, not a source of truth. Update rules:

1. A task may be checked `[x]` **only after** a reviewer returned **PASS** (or **PASS WITH MINOR ISSUES** whose safe reviewer patches were applied and re-review returned **PASS**) per [`../ai/review-task.md`](../ai/review-task.md) §2.4, **and** the resulting commit is on `main`.
2. The reviewer (human or model) is the party authorized to flip a task to `[x]` in the same commit that closes the task, or in a follow-up docs-only commit that references the review report path.
3. An implementer may set a task to `[~]` when work starts, and to `[!]` when they raise a stop signal — but must **never** self-approve to `[x]`.
4. Never mark a task done because "the code is clearly there" — the reviewed commit on `main` is the gate. Uncertain tasks stay `[ ]`.
5. Do not modify task files (`./tasks/T-XXX.md`) to keep them in sync with this roadmap. Descriptions here are derived from the task files; if a task file changes, refresh the description here in the same commit.
6. Do not add new tasks here that do not also exist under [`./tasks/`](./tasks/). Adding or removing tasks is an architect-level concern (open an ADR) — this file only reflects what already exists.
7. This file is documentation only. Editing it does not require an ADR, an `.importlinter` update, or a test.

---

## S01 — Foundation & tooling

- [x] **T-101** — Initialize `pyproject.toml` with uv — Lock Python 3.13 + uv toolchain and declare dependency groups for deterministic installs.
- [x] **T-102** — Ruff + Mypy + Pytest config — Enforce style, type, and test discovery from the first commit.
- [x] **T-103** — `Makefile` with all targets — Provide a single stable command surface for developers and CI.
- [x] **T-104** — `Dockerfile` (multi-stage, non-root, uv) — Two-stage image (`builder` + `runtime`) built on `python:3.13-slim` with `uv sync --frozen`.
- [x] **T-105** — `docker-compose.yml` + override — Local stack: `api`, `worker`, `pgvector/pgvector:pg16`, `redis:7-alpine`, `otel-collector`.
- [x] **T-106** — `.pre-commit-config.yaml` — Pinned hooks for ruff, mypy, EOF/whitespace, merge-conflict, detect-secrets, and `lint-imports`.
- [x] **T-107** — `.importlinter` with Phase 2 contracts — Declare layer/independence/forbidden contracts for `app/` at repo root (INI format).
- [x] **T-108** — `.github/workflows/ci.yml` — CI jobs for quality (`make lint typecheck test` + `lint-imports`) and integration (`make test-int`).
- [x] **T-109** — `.env.example`, `.gitignore`, `.editorconfig` — Document required env vars and standardize workspace defaults.

## S02 — Shared primitives

- [x] **T-201** — `app/shared/errors.py` `AppError` hierarchy — Base exception with `code/title/status/detail/extras` and standard subclasses.
- [x] **T-202** — `app/shared/problem_details.py` — Pydantic v2 model + factory for RFC 9457 Problem Details payloads.
- [x] **T-203** — Shared leaves: `ids`, `clock`, `pagination`, `result`, `types`, `pydantic` — Small utility surface used by every downstream module.

## S03 — Configuration

- [x] **T-301** — `app/core/config/` Pydantic Settings — Nested `AppSettings` aggregating meta, logging, DB, Redis, JWT, and provider settings.
- [x] **T-302** — Settings validation test — Parameterized test that removes required env vars and asserts `AppSettings()` raises `ValidationError`.

## S04 — Observability

- [x] **T-402** — `correlation.py` `request_id_var` + middleware — ContextVar-based request id and ASGI middleware that echoes `X-Request-ID`.
- [x] **T-401** — `app/observability/logging.py` structlog — `configure_logging`/`get_logger` with request-id-aware structlog processors.
- [x] **T-403** — `tracing.py` + `metrics.py` config holders — Resource, tracer, and meter helpers; exporters wired later in `app/core/wiring/`.
- [x] **T-404** — `middleware.py` access log — One structured log per request with method, path, status, duration, request id, user id.
- [x] **T-405** — Health endpoints `/healthz` `/readyz` `/livez` — Pure endpoint shapes plus a `Probe`/`ProbeRegistry` composed by later wiring tasks.

## S05 — App factory + API edge

- [x] **T-501** — `app/api/errors.py` `AppError` → Problem Details handler — Register handlers for `AppError`, validation, and fallback `Exception`.
- [x] **T-502** — `security_headers.py` + `pagination.py` — Standard security response headers and shared pagination primitives.
- [x] **T-503** — `app/api/v1.py` router mount point — Empty `/api/v1` `APIRouter` that module tasks append `include_router(...)` lines to.
- [x] **T-504** — `app/core/container.py`, `di.py`, `lifespan.py` — Incremental `Container` dataclass, FastAPI dependency helpers, and lifespan hook registry.
- [x] **T-505** — `app/main/app_factory.py` `create_app()` — Composition root that builds `Container`, mounts routers, and installs middleware (ADR-0023).
- [x] **T-506** — `app/main/__init__.py` ASGI entrypoint — `app = create_app()`, the module Uvicorn/Gunicorn/Arq imports.
- [x] **T-507** — API error & correlation tests — Assert Problem Details shape, sanitized 500s, and `X-Request-ID` echo behavior.

## S06 — Platform ports

- [x] **T-601** — `app/platform/storage/ports.py` (`BlobStorage`) — `BlobRef` + async `BlobStorage` protocol (`put/get/delete/head/generate_presigned_url`).
- [x] **T-602** — `app/platform/cache/ports.py` (`Cache`) — Async `Cache` protocol with `get/set/delete/incr/expire` and `CacheKey` NewType.
- [x] **T-603** — `app/platform/queue/ports.py` (`TaskQueue` + `Job`) — Enqueue/status/cancel protocol plus `EnqueueOptions`, `JobId`, `JobStatus`.
- [x] **T-604** — `app/platform/rate_limit/ports.py` (`RateLimiter`) — `RateLimitDecision` + `RateLimiter.allow(key, quota, window_s)` protocol.
- [x] **T-605** — `app/platform/idempotency/ports.py` (`IdempotencyStore`) — `IdempotencyRecord` + `begin/complete/get` protocol for retry-safe writes.

## S07 — Infrastructure base

- [x] **T-701** — `app/infrastructure/db/` — Async engine, `async_sessionmaker`, `DeclarativeBase`, and pgvector SQLAlchemy type registration.
- [x] **T-702** — `app/infrastructure/redis/` (+ `Cache` adapter) — `build_client(settings)` and `RedisCache` implementing the `Cache` port.
- [x] **T-703** — `app/infrastructure/http/` shared httpx — `AsyncClient` factory with HTTPX instrumentation wired via `app.core.wiring.observability`.
- [x] **T-704** — `infrastructure/storage/local.py` (`BlobStorage` local) — Local-filesystem adapter for the Phase 2 `BlobStorage` port.
- [ ] **T-705** — *(removed — deferred to Phase 3)* — S3 adapter is not part of Phase 2.
- [x] **T-706** — `infrastructure/rate_limit/redis.py` — Redis-Lua atomic rate limiter with `rl:{key}` namespace.
- [x] **T-707** — `infrastructure/idempotency/redis.py` — Redis-backed `IdempotencyStore` adapter.
- [x] **T-708** — `core/wiring/storage.py`, `cache.py` — Wiring that returns Protocol-typed `BlobStorage` and `Cache` bound into the `Container`.
- [x] **T-709** — Lifespan readiness ordering fix — Move `app.state.ready = True` to the final step of successful startup, after Redis wiring and `RedisProbe` registration, so `/readyz` never reports ready before all wired resources are initialized.

## S08 — Persistence + migrations

- [x] **T-801** — Alembic init (async) — `env.py` on the async engine, reading `DATABASE_URL` via `core.config`, collecting `Base.metadata`.
- [x] **T-802** — Initial migration (pgvector + base) — `CREATE EXTENSION IF NOT EXISTS vector`; no domain tables in this revision.
- [x] **T-803** — DB session + pgvector round-trip integration test — Testcontainers Postgres proving `Vector(3)` insert/select round-trips.

## S09 — Auth + Users

- [x] **T-901** — `app/auth/domain.py` — Frozen `Credentials`, `AuthenticatedUser`, `AccessToken`, `RefreshToken`, and auth-specific errors.
- [x] **T-902** — `app/auth/ports.py` — `PasswordHasher`, `TokenSigner`, and `IdentityProvider` protocols.
- [x] **T-903** — `app/auth/adapters/argon2_hasher.py` — Argon2id hasher with configurable settings, `needs_rehash`, and no leaked provider exceptions.
- [x] **T-904** — `app/auth/adapters/jwt_signer.py` — RS256/EdDSA JWT signer with standard claims and 30s clock skew.
- [x] **T-904A** — Establish platform SQLAlchemy mapping foundation — Move shared `Base`/metadata to `app.platform.db` to unblock feature-module persistence.
- [x] **T-905** — `app/auth/persistence.py` + migration — `UserRow` and `RefreshTokenRow` mapped classes translated to auth domain/read-model types at the boundary.
- [x] **T-905A** — Refresh-token persistence mutation helpers — Add rotation, single-token revocation, and family revocation helpers returning auth domain/read-model records.
- [x] **T-906A** — Auth runtime wiring — Wire `PasswordHasher` and `TokenSigner` into the `Container` through `app/core/wiring/auth.py`.
- [x] **T-906B** — Auth production refinement — Fix refresh-token rotation transaction ordering
- [x] **T-906** — Auth service + policies + deps — `register/login/refresh/logout` service with refresh-token rotation and reuse detection.
- [x] **T-907** — `app/auth/api.py` — `/auth/register|login|refresh|logout` endpoints raising only `AppError` subclasses.
- [x] **T-907A** — Auth production refinement — Fix refresh FK bug, wire Clock, and remove API TODOs.
- [x] **T-908** — Auth API tests + refresh-reuse detection — Happy path, 401/422, Problem Details, `X-Request-ID`, and family revocation on reuse.
- [x] **T-906C** — Propagate email through authenticated principal — Add `email` to the public authenticated principal returned by `get_current_user`, so downstream modules like `app.users` can use the authenticated user's email without importing auth persistence, auth adapters, or decoding JWTs.
- [x] **T-910** — `app/users/` minimal — `User` profile, `GET /api/v1/users/me`, and lazy `get_or_create_profile` on first read.
- [ ] **T-911** — Scope-based authorization dependency — Add a reusable API-edge authorization dependency factory.

## S10 — Prompts

- [ ] **T-1001** — `app/prompts/{domain,ports,registry}.py` — `Prompt` dataclass and `PromptRegistry` protocol with Jinja2 rendering + schema validation.
- [ ] **T-1002** — `library/rag_answer_v1.yaml` + IO schemas — Canonical Phase 2 prompt with declared input/output Pydantic schemas.
- [ ] **T-1003** — `app/prompts/api.py` (read-only) — `GET /prompts` and `GET /prompts/{id}/{version}` for prompt inspection.
- [ ] **T-1004** — Registry render + schema-validation tests — Verify template render + schema round-trip on the shipped prompt.

## S11 — LLM + embeddings ports

- [ ] **T-1100** — `app/ai_governance/{domain,ports}.py` (pre-llm interface only) — Ship governance domain types (`BudgetPolicy`, `UsageEntry`) and outbound persistence ports (`UsageRepository`, `BudgetPolicyStore`) so S12 can implement the service against a stable contract. The `GovernanceGate` Protocol lives in `app.llm.ports` (T-1101) per ADR-0024; `app.llm` does not import `app.ai_governance`.
- [ ] **T-1101** — `app/llm/{domain,ports,observability,router}.py` — Chat domain types, `ChatModel` protocol, observation record, and `ModelRouter`.
- [ ] **T-1102** — `app/llm/service.py` — `LlmService` that consults `GovernanceGate` and emits `LLMCallObservation` around every provider call.
- [ ] **T-1103** — `app/embeddings/{domain,ports,service}.py` — Embedding domain, `EmbeddingModel` port, and `EmbeddingsService`.
- [ ] **T-1104** — Fake `ChatModel` + fake `EmbeddingModel` — Deterministic in-memory doubles used by CI and contract tests.
- [ ] **T-1105** — `ChatModel` contract test suite — Parameterized cases: happy path, 5xx→`UpstreamProviderError`, empty-messages rejection, JSON response format.
- [ ] **T-1106** — `EmbeddingModel` contract test suite — Parameterized adapter contract for embedding providers.

## S12 — AI governance + OpenAI adapters

- [ ] **T-1202** — `app/ai_governance/persistence.py` + migration — Policy/usage/audit tables with `(tenant_id, occurred_at)` indexes and `Numeric(12,6)` costs.
- [ ] **T-1203** — `app/ai_governance/service.py` — `check_call_allowed` and `record_usage` implementing model allow-list and monthly-budget policy.
- [ ] **T-1204** — `events.py` + audit emit — `AIUsageAuditEvent` emitted via structlog with the standard correlation fields.
- [ ] **T-1205** — `app/ai_governance/api.py` (read-only) — Endpoints to inspect current policy and monthly usage.
- [ ] **T-1206** — Budget tests (deny / warning / audit) — Prove hard-deny at 100 % budget, 80 % `X-Budget-Warning`, and audit emission.
- [ ] **T-1210** — `infrastructure/llm_providers/openai.py` — OpenAI `ChatModel` adapter translating `ChatRequest`/`ChatResponse` without leaking SDK types.
- [ ] **T-1211** — `infrastructure/embedding_providers/openai.py` — OpenAI `EmbeddingModel` adapter using the shared httpx client.
- [ ] **T-1212** — `core/wiring/{llm,embeddings,governance}.py` — Wire `LlmService`, `EmbeddingModel`, and governance gate into the `Container`.

## S13 — Documents (domain + API)

- [ ] **T-1301** — `app/documents/{domain,ports}.py` — `Document`, `Chunk`, `BlobRef`, and outbound port protocols.
- [ ] **T-1302** — `app/documents/parsers/` (txt, md, html, pdf) — Content-type dispatch yielding `ParsedPage` records; PDF via `pypdf`.
- [ ] **T-1303** — `app/documents/chunkers/` (recursive token-aware) — Recursive splitter using `tiktoken` with configurable overlap and deterministic chunk hashes.
- [ ] **T-1304** — `app/documents/persistence.py` + migration — `documents` and `chunks` tables with tenant/status indexes.
- [ ] **T-1305** — `app/documents/api.py` POST/GET — Upload endpoint (enqueues ingestion) and status endpoint returning `202 Accepted` semantics.

## S14 — Queue + worker

- [ ] **T-1401** — `app/infrastructure/queue/arq.py` (`TaskQueue` adapter) — Arq-backed `TaskQueue` propagating `request_id`, `tenant_id`, retries, and idempotency.
- [ ] **T-1402** — `core/wiring/queue.py` + worker entrypoint — Compose `WorkerSettings` and expose it via `app/worker.py` for `arq app.worker.WorkerSettings`.
- [ ] **T-1403** — `app/documents/ingestion.py` + `service.py` — Arq job orchestrating parse → chunk → embed → upsert vectors → mark `ready`.
- [ ] **T-1404** — Integration test for enqueue → run → status — End-to-end Postgres+Redis+Arq test polling status until `ready`.

## S15 — Vector store

- [ ] **T-1501** — `app/rag/ports.py` (`VectorStore`) — `VectorRecord`, `RetrievedChunk`, and `VectorStore` (`upsert`, `search`) protocol.
- [ ] **T-1502** — `app/infrastructure/vector_stores/pgvector.py` — pgvector adapter with cosine distance, tenant filter, and chunk join.
- [ ] **T-1503** — `app/core/wiring/vector_store.py` — Wire Protocol-typed `VectorStore` and register a readiness probe.
- [ ] **T-1504** — Integration test for real pgvector similarity — Testcontainers Postgres proving similarity round-trip on real pgvector.

## S16 — RAG pipeline

- [ ] **T-1601** — `app/rag/{domain,pipeline,service}.py` — `Query`, `Citation`, `Answer` and the retrieve→augment→generate pipeline.
- [ ] **T-1602** — `app/rag/api.py` POST `/rag/ask` — RAG endpoint returning answer + citations and propagating `X-Budget-Warning`.
- [ ] **T-1603** — RAG unit + API tests — Citations present, 401/422, Problem Details on `BudgetExceededError`, and `budget=0` bypasses provider.

## S17 — Golden-path integration

- [ ] **T-1701** — End-to-end golden-path test — Register → upload → poll `ready` → `POST /rag/ask` → assert answer + ≥1 citation.
- [ ] **T-1702** — `LLMCallObservation` 11-field assertion — Capture the golden-path log and assert every required field is non-null.
- [ ] **T-1703** — Continuous-trace assertion — In-memory OTel exporter proves one trace across `rag.ask → embeddings.embed → vector_store.search → llm.chat`.

## S18 — Docs + hardening

- [ ] **T-1801** — Update `docs/architecture.md`, `docs/folder-structure.md`, `docs/dependency-graph.md` — Reflect what Phase 2 actually ships (platform ports, ai_governance, Arq, local BlobStorage).
- [ ] **T-1802** — Update `README.md` quickstart + golden-path walkthrough — Product-facing quickstart and end-to-end walkthrough.
- [ ] **T-1803** — Mark ADR-0009 Superseded; cross-link 0018–0022 — Housekeeping on the ADR set.
- [ ] **T-1804** — Final `make check` — Full green run on a clean checkout as the Phase 2 acceptance gate.
