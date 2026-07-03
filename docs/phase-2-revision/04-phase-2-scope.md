# Revised Phase 2 Scope

> Phase 2 delivers the **foundation** plus the **first golden-path vertical slice**. Nothing else.
> If a feature is not listed here, it is Phase 3 or later.

---

## 1. Repository hygiene & tooling

- `pyproject.toml` — uv-managed; pinned Python 3.13; dependency groups: `main`, `dev`, `test`.
- `uv.lock` — committed.
- `Makefile` — `up`, `down`, `test`, `test-int`, `lint`, `typecheck`, `fmt`, `migrate`, `revision msg=...`, `worker`, `check` (runs everything CI runs).
- `Dockerfile` — multi-stage; non-root user; uv-based build; healthcheck.
- `docker-compose.yml` — services: `api`, `worker`, `postgres` (with pgvector), `redis`, `otel-collector`. Healthchecks for every service. Dev overrides in `docker-compose.override.yml`.
- `.pre-commit-config.yaml` — Ruff (lint+format), Mypy strict on `app/`, end-of-file-fixer, trailing-whitespace, check-merge-conflict, detect-secrets, import-linter.
- `ruff` config in `pyproject.toml`: line length 100, target 3.13, all reasonable rule sets on; per-folder ignores documented.
- `mypy` config: strict on `app/`, lenient on `tests/` (no `disallow_untyped_defs` for test files), explicit follow-imports = normal.
- `pytest` config: marker registry (`unit`, `integration`, `api`, `contract`, `slow`), `--strict-markers`, `pytest-asyncio` in `auto` mode, `pytest-cov` with `--cov-fail-under=80` for `app/`.
- `importlinter.toml` — contracts as in §03 of this revision pack.
- `.github/workflows/ci.yml` — lint, typecheck, unit, integration (Testcontainers), import-linter, build image. Required for merge.

## 2. App foundation (`app/`)

- `app/main/` — composition site and ASGI entrypoint **package** (`app/main/app_factory.py::create_app()`); no top-level `app/main.py` module.
- `app/core/` — `config/` (Pydantic Settings, env-driven, fails fast); `app_factory.py`; `lifespan.py`; `container.py`; `di.py`; `wiring/{llm,embeddings,vector_store,storage,cache,queue,governance}.py`.
- `app/shared/` — full (errors, problem_details, pagination, ids, clock, result, types, pydantic base).
- `app/observability/` — structlog config; OTel tracer/meter setup (exporters constructed in `core.wiring` and registered here); correlation middleware (`X-Request-ID` in/out); access log middleware; exception → Problem Details handler; `/healthz`, `/readyz`, `/livez`, optional `/metrics`.
- `app/platform/` — all five port modules (`storage`, `cache`, `queue`, `rate_limit`, `idempotency`). Protocols only. No SDKs imported.
- `app/infrastructure/` — adapters listed below in §3.
- `app/api/` — `v1.py` (mounts per-module routers under `/api/v1`), `errors.py`, `pagination.py`, `idempotency.py`, `rate_limit.py`, `security_headers.py`, CORS deny-by-default.

## 3. Infrastructure adapters (Phase 2)

| Adapter                                      | Notes                                                                         |
| -------------------------------------------- | ----------------------------------------------------------------------------- |
| `infrastructure/db/`                         | async engine, sessionmaker, base metadata, pgvector type, session-per-request |
| `infrastructure/redis/`                      | async client + `Cache` adapter                                                |
| `infrastructure/http/`                       | shared httpx client; tenacity retries; OTel instrumentation; timeouts         |
| `infrastructure/storage/local.py`            | `BlobStorage` local-FS adapter (dev). S3 adapter is deferred to Phase 3 (roadmap T-705). |
| `infrastructure/queue/arq.py`                | `TaskQueue` Arq adapter; worker entrypoint                                    |
| `infrastructure/rate_limit/redis.py`         | Redis token-bucket adapter                                                    |
| `infrastructure/idempotency/redis.py`        | Redis-backed `IdempotencyStore`                                               |
| `infrastructure/llm_providers/openai.py`     | only OpenAI in Phase 2; ports are provider-agnostic                           |
| `infrastructure/embedding_providers/openai.py` | only OpenAI in Phase 2                                                      |
| `infrastructure/vector_stores/pgvector.py`   | pgvector adapter; hybrid (BM25 + vector) deferred                             |

Other providers (Anthropic, Gemini, Voyage, Cohere, Qdrant) are Phase 3. The `BlobStorage` S3 adapter (`infrastructure/storage/s3.py`) is also Phase 3; the `BlobStorage` port itself ships in Phase 2 so a future S3 adapter can be added behind it without a port change.

## 4. Domain modules (Phase 2 materialization)

### `auth/` — minimal skeleton
- Endpoints: `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`.
- Argon2id `PasswordHasher` adapter; JWT (asymmetric) `TokenSigner` adapter.
- Refresh tokens: opaque, high-entropy, hashed at rest, rotated, reuse-detected.
- `policies.py`: `require_authenticated`, scope checks.
- Tests: unit (hashing, claims), API (full login → refresh → logout).

### `users/` — minimal skeleton
- Endpoint: `GET /api/v1/users/me`.
- User row created on first signup; nothing else.
- Tests: API (`/users/me` returns 401 unauthenticated; 200 with profile when authenticated).

### `prompts/`
- Filesystem-loading registry; semantic versions; Pydantic input/output schemas.
- One real prompt shipped: `library/rag_answer_v1.yaml` (used by the golden path).
- `GET /api/v1/prompts` (admin, read-only) and `GET /api/v1/prompts/{id}/{version}`.

### `llm/`
- `ChatModel` Protocol (`complete` + `stream`); `ModelRouter` Protocol; default `router.py`.
- `service.call_chat(...)` and `service.call_structured(model, ...)`.
- Every call: (a) consults `ai_governance.service.check_call_allowed(...)`, (b) records `LLMCallObservation` (provider, model, prompt_id, prompt_version, tokens_in, tokens_out, latency_ms, cost_usd, status, request_id, tenant_id), (c) opens an OTel span with the same attributes.
- Contract tests: a single suite each adapter must pass.

### `embeddings/`
- `EmbeddingModel` Protocol; batching + retry-aware service helper.

### `ai_governance/`
- Domain: `BudgetPolicy` (per-tenant daily/monthly USD + tokens), `ModelAllowlist`, `UsageEntry`.
- Service: `check_call_allowed(*, tenant_id, model, est_tokens) -> AllowDecision`; `record_usage(...)`; `pick_fallback(model) -> Model | None`.
- Persistence: `usage_entries`, `budget_policies`, `model_allowlists` tables.
- Events: `AIUsageAuditEvent` emitted on every recorded usage.
- API (Phase 2, read-only): `GET /api/v1/governance/budgets`, `GET /api/v1/governance/usage`.
- Phase 2 enforcement: hard-deny when monthly budget exceeded; soft-warn (header `X-Budget-Warning`) at 80%.

### `ai/` — **skeleton only in Phase 2**
- `AgentRunner` facade signature defined; no agents shipped; no endpoints exposed.

### `documents/` — golden path producer
- Endpoint: `POST /api/v1/documents` (multipart or URL upload).
- Domain: `Document`, `Chunk`, `ChunkStrategy`.
- Parsers: `txt`, `markdown`, `html`, `pdf` (via `pypdf`).
- Chunkers: recursive token-aware (tiktoken).
- Ingestion job enqueued via `platform.queue.TaskQueue`; runs in Arq worker; writes `documents` + `chunks` rows and calls `embeddings.service.embed_batch()`; vectors persisted via `rag` `VectorStore` port.
- Endpoint returns `202 Accepted` with `document_id` and job tracking URL `GET /api/v1/documents/{id}` (status: `pending` → `processing` → `ready` | `failed`).

### `rag/` — golden path consumer
- Endpoint: `POST /api/v1/rag/ask` `{question, top_k?, filters?}` → `{answer, citations[]}`.
- Pipeline: `embed(query) → search(VectorStore, top_k) → cite → answer(ChatModel, prompt=rag_answer_v1)`.
- Citations are always present and reference `(document_id, chunk_id, span, source_uri?)`.
- Streaming via SSE deferred to Phase 3.

## 5. Persistence

- Alembic initialized; one head; one migration per Phase 2 module owning tables.
- Tables in Phase 2: `users`, `refresh_tokens`, `documents`, `chunks`, `embeddings` (pgvector), `usage_entries`, `budget_policies`, `model_allowlists`.
- pgvector extension enabled in the initial migration.

## 6. Testing (Phase 2 mandatory)

- Unit tests for every `domain.py` and pure logic in `service.py`.
- API tests for every endpoint listed above, including:
    - happy path
    - auth failure (401)
    - validation failure (422)
    - Problem Details error shape assertion
    - `X-Request-ID` echo
- Integration tests (Testcontainers) for:
    - Postgres + pgvector retrieval (real vectors, real similarity)
    - Redis cache, rate limiter, idempotency
    - Arq job enqueue + execute end-to-end
- Contract test suites for `ChatModel`, `EmbeddingModel`, `VectorStore` (run against fakes in unit; against real providers behind an env flag).
- An import-linter test in CI.
- A "settings validation" test that boots `AppSettings` with bad env and asserts startup failure.

## 7. Documentation (Phase 2 updates)

- `README.md` — quickstart, golden path walkthrough.
- `docs/architecture.md` — updated to reflect `platform`, `ai_governance`, Arq Phase 2.
- `docs/folder-structure.md` — updated tree.
- `docs/dependency-graph.md` — updated edges + contracts.
- `docs/adr/` — new ADRs 0018–0022; 0009 marked Superseded.
- `AGENTS.md` — created.

## 8. Acceptance criteria for Phase 2

Phase 2 is "done" when **all** of the following hold:

1. `make up` boots api + worker + postgres + redis + otel-collector with healthchecks green.
2. `make check` (lint + typecheck + unit + integration + import-linter) passes on a clean checkout.
3. The golden path runs end-to-end against `make up`: upload a PDF, wait for `ready`, ask a question, receive an answer with at least one citation pointing to a real chunk in the uploaded PDF.
4. The LLM call emits an `LLMCallObservation` containing all 11 required fields (provider, model, prompt_id, prompt_version, tokens_in, tokens_out, latency_ms, cost_usd, status, request_id, tenant_id).
5. The trace for the golden path is continuous from `POST /rag/ask` through `embed → search → chat-complete`.
6. Setting `LLM_MONTHLY_BUDGET_USD=0` for the tenant causes `POST /rag/ask` to return a Problem Details `409 budget-exceeded` without making the LLM call.
7. Refresh-token reuse triggers detection: the family is revoked, audit event emitted.
8. Every endpoint returns RFC 9457 Problem Details on error.
9. Every response carries `X-Request-ID`.
10. `import-linter` reports zero violations.

If any acceptance criterion is not met, Phase 2 is incomplete. No partial release.
