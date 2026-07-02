# IMPLEMENTATION_PLAN.md — Phase 2 of `ai-backend-foundation`

> Authoritative, sequential, file-scoped, test-driven task list for implementing Phase 2.
> This document is binding for the implementing model. It must not be re-interpreted or re-designed.
> Source of architectural truth: `AGENTS.md`, `docs/phase-2-revision/02..07`, `docs/adr/0018..0022`.

This plan is split across three companion files:

- **Rules** (global rules, stop signals, allowed-files discipline, command discipline, lower-complexity model instructions): [`docs/implementation/rules.md`](docs/implementation/rules.md)
- **Review** (reviewer model instructions, final review checklist, architecture compliance checklist): [`docs/implementation/review.md`](docs/implementation/review.md)
- **Tasks** (one file per task, exact format preserved): [`docs/implementation/tasks/`](docs/implementation/tasks/)

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

None blocking. The revision pack (`01-contradictions.md`) resolved C-1..C-10 already. Two clarifications the implementing model must honor (these are **also** mirrored in [`docs/implementation/rules.md`](docs/implementation/rules.md) §1):

- **C-2 clarification**: OTel exporters and providers are constructed inside `app/core/wiring/`. `app/observability/` only exposes config types, middleware factories, and the `request_id_var` context var. Do not import OTel exporters from `app/observability/`.
- **C-4 clarification**: One type per role per module. `domain.py` → frozen dataclasses (Pydantic only for validation-heavy value objects). `api.py` → Pydantic v2 request/response. `persistence.py` → SQLAlchemy mapped. **Never** mix.
- **S3 storage adapter is Phase 3.** Phase 2 ships **only** the local-FS `BlobStorage` adapter. Settings, `.env.example`, docker-compose, and wiring must not assume S3 in Phase 2. Task T-705 is removed; `aioboto3` does not enter Phase 2.
- **Container is incremental.** `app/core/container.py` (T-504) defines the `Container` dataclass, starting with the **minimal** set of fields wired by tasks already completed — namely `settings` and `probe_registry`. Per [ADR-0023](docs/adr/0023-composition-root-ownership.md), the initial `Container` (with `settings` and an empty `ProbeRegistry`) is **constructed by `create_app()` in `app.main`** (T-505), not by the lifespan; `app.core.lifespan` mutates it in place. Each later wiring task (T-701 db_engine/session_factory, T-702/T-708 cache, T-1212 llm+embeddings+governance, T-1402 queue, T-1503 vector_store) **appends** its field to the dataclass and its probe to the same `ProbeRegistry` instance. A task may not reference a Container field that has not yet been added.
- **Makefile arrives in T-103.** Tasks T-101 and T-102 must not invoke `make ...` in their `Commands` block; they use the equivalent `uv run` commands directly. Every later task may use `make ...`.
- **`importlinter` runs at every phase.** Contracts in T-107 validate cleanly against an empty/skeleton `app/` package (T-107 creates a minimal `app/__init__.py` so `lint-imports` has a target). The same contracts continue to apply unchanged after every later task adds modules.
- **Repository State Awareness.** Early tasks operate on an incomplete repository. Future files (like `app/__init__.py` before T-107) must never be created early to satisfy tooling. Command failures caused by repository incompleteness should be reported, not worked around. Task boundaries take precedence over making commands pass. Coverage requirements evolve with the repository state.
- **ai_governance domain/ports precede `app.llm.service`.** A standalone task T-1100 (ai_governance domain + ports only) executes before T-1102. The remaining ai_governance tasks (T-1201..T-1206) stay in S12 as scheduled.

---

## 2. How to use this plan

1. **Read first, in order:**
   1. `AGENTS.md` (architectural law)
   2. [`docs/implementation/rules.md`](docs/implementation/rules.md) (global rules, Repository State Awareness, stop signals, allowed-files discipline, command discipline, lower-complexity model instructions)
   3. This file's §3 (dependency map) and §4 (task index)
   4. The specific task file you are about to execute, at [`docs/implementation/tasks/T-XXX.md`](docs/implementation/tasks/)
   5. [`docs/implementation/review.md`](docs/implementation/review.md) (so you know exactly what the reviewer will check)
2. **Pick the next unfinished task** from §4 (lowest task id within the earliest unfinished section). Do not skip ahead. Do not interleave.
3. **Execute the task** literally, honoring its `Allowed files`, `Forbidden`, `Implementation requirements`, `Tests required`, `Acceptance criteria`, and `Commands` blocks. Each task file is self-contained: paste it together with `docs/implementation/rules.md` into a lower-complexity model (e.g. Gemini Flash) and execute.
4. **Stop and report** if any of the conditions listed under "Stop signals" in [`docs/implementation/rules.md`](docs/implementation/rules.md) §5 are true. Do not improvise.
5. **Before opening a PR**, run `make check` and self-check against [`docs/implementation/review.md`](docs/implementation/review.md) §2 and §3.

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

- **S04 execution order is `T-402 → T-401 → T-403 → T-404 → T-405`, not lexical by task id.** T-401 (`logging.py`) reads `request_id_var` from T-402 (`correlation.py`), so the leaf task T-402 lands first. The task index below enumerates by number for readability; the dependency-driven order above is binding. See `docs/implementation/rules.md` §1.
- **Health probes and `/api/v1` router are wired incrementally across S04/S05/S07+.** T-405 ships only pure endpoint shapes and a `ProbeRegistry`; T-505 (`create_app()` in `app.main`) constructs the **empty** `ProbeRegistry` on the `Container` and installs it on `app.state.container` before the lifespan runs; T-504's lifespan owns the `app.state.ready` flag and mutates the existing `Container` in place (no external I/O; DB/Redis/vector/queue infrastructures do not exist yet at S05). Each later wiring task appends its probe alongside its `Container` field (T-701 DB, T-702/T-708 Redis/cache, T-1402 queue, T-1503 vector store), on the same registry instance the health router already closes over. T-505 mounts the health router with an `is_ready` closure. T-503 ships an empty `/api/v1` mount point; each module task appends its `include_router(...)` line in the same PR that introduces the module's `api.py`. See `docs/implementation/rules.md` §1 and [ADR-0023](docs/adr/0023-composition-root-ownership.md).
- OpenAI LLM/embedding adapters (S11) require: `app.llm.domain`, `app.embeddings.domain`, settings (S03), HTTP client (S07), observability (S04).
- Document ingestion (S13–S15) requires: documents persistence (S13), blob storage (S07), queue (S14), embeddings (S11), vector store (S15).
- RAG (S16) requires: settings (S03), DB (S07), platform ports (S06), prompts (S10), embeddings port (S11), vector store (S15), `ai_governance` (S12).
- Tests of any LLM-touching code default to **fake** `ChatModel` / `EmbeddingModel` adapters introduced in S11; OpenAI adapters are tested by their own contract suite only.

---

## 4. Task index

Legend: `M` = mandatory for Phase 2 acceptance; `S` = skeleton-only (do not over-build).

Every row links to the self-contained task file under [`docs/implementation/tasks/`](docs/implementation/tasks/).

| ID    | Section                          | Title                                                              | Kind |
| ----- | -------------------------------- | ------------------------------------------------------------------ | ---- |
| [T-101](docs/implementation/tasks/T-101.md) | S01 Foundation/tooling           | Initialize `pyproject.toml` (uv, py3.13, deps groups)              | M    |
| [T-102](docs/implementation/tasks/T-102.md) | S01                              | Add Ruff + Mypy + Pytest config                                    | M    |
| [T-103](docs/implementation/tasks/T-103.md) | S01                              | Create `Makefile` with all targets                                 | M    |
| [T-104](docs/implementation/tasks/T-104.md) | S01                              | Create `Dockerfile` (multi-stage, non-root, uv)                    | M    |
| [T-105](docs/implementation/tasks/T-105.md) | S01                              | Create `docker-compose.yml` + `docker-compose.override.yml`        | M    |
| [T-106](docs/implementation/tasks/T-106.md) | S01                              | Create `.pre-commit-config.yaml`                                   | M    |
| [T-107](docs/implementation/tasks/T-107.md) | S01                              | Create `importlinter.toml` with Phase 2 contracts                  | M    |
| [T-108](docs/implementation/tasks/T-108.md) | S01                              | Create `.github/workflows/ci.yml`                                  | M    |
| [T-109](docs/implementation/tasks/T-109.md) | S01                              | Create `.env.example`, `.gitignore`, `.editorconfig`               | M    |
| [T-201](docs/implementation/tasks/T-201.md) | S02 Shared primitives            | `app/shared/errors.py` (`AppError` hierarchy)                      | M    |
| [T-202](docs/implementation/tasks/T-202.md) | S02                              | `app/shared/problem_details.py` (RFC 9457 model + factory)         | M    |
| [T-203](docs/implementation/tasks/T-203.md) | S02                              | `app/shared/ids.py`, `clock.py`, `pagination.py`, `result.py`, `types.py`, `pydantic.py` | M |
| [T-301](docs/implementation/tasks/T-301.md) | S03 Configuration                | `app/core/config/__init__.py` Pydantic Settings hierarchy          | M    |
| [T-302](docs/implementation/tasks/T-302.md) | S03                              | Settings validation test (bad env → startup fail)                  | M    |
| [T-401](docs/implementation/tasks/T-401.md) | S04 Observability                | `app/observability/logging.py` structlog config                    | M    |
| [T-402](docs/implementation/tasks/T-402.md) | S04                              | `app/observability/correlation.py` `request_id_var` + middleware  | M    |
| [T-403](docs/implementation/tasks/T-403.md) | S04                              | `app/observability/tracing.py`, `metrics.py` config holders        | M    |
| [T-404](docs/implementation/tasks/T-404.md) | S04                              | `app/observability/middleware.py` access log + X-Request-ID echo   | M    |
| [T-405](docs/implementation/tasks/T-405.md) | S04                              | `app/observability/health.py` `/healthz`, `/readyz`, `/livez`      | M    |
| [T-501](docs/implementation/tasks/T-501.md) | S05 App factory + API edge       | `app/api/errors.py` AppError → Problem Details handler             | M    |
| [T-502](docs/implementation/tasks/T-502.md) | S05                              | `app/api/security_headers.py`, `pagination.py`                     | M    |
| [T-503](docs/implementation/tasks/T-503.md) | S05                              | `app/api/v1.py` router mount point                                 | M    |
| [T-504](docs/implementation/tasks/T-504.md) | S05                              | `app/core/container.py`, `di.py`, `lifespan.py`                    | M    |
| [T-505](docs/implementation/tasks/T-505.md) | S05                              | `app/main/app_factory.py` `create_app()` (composition site; ADR-0023) | M |
| [T-506](docs/implementation/tasks/T-506.md) | S05                              | `app/main/__init__.py` ASGI entrypoint                             | M    |
| [T-507](docs/implementation/tasks/T-507.md) | S05                              | API error/correlation tests (Problem Details, X-Request-ID echo)   | M    |
| [T-601](docs/implementation/tasks/T-601.md) | S06 Platform ports               | `app/platform/storage/ports.py` (BlobStorage)                       | M    |
| [T-602](docs/implementation/tasks/T-602.md) | S06                              | `app/platform/cache/ports.py` (Cache)                              | M    |
| [T-603](docs/implementation/tasks/T-603.md) | S06                              | `app/platform/queue/ports.py` (TaskQueue + Job)                    | M    |
| [T-604](docs/implementation/tasks/T-604.md) | S06                              | `app/platform/rate_limit/ports.py` (RateLimiter)                   | M    |
| [T-605](docs/implementation/tasks/T-605.md) | S06                              | `app/platform/idempotency/ports.py` (IdempotencyStore)             | M    |
| [T-701](docs/implementation/tasks/T-701.md) | S07 Infrastructure base          | `app/infrastructure/db/` async engine + sessionmaker + pgvector type | M  |
| [T-702](docs/implementation/tasks/T-702.md) | S07                              | `app/infrastructure/redis/` async client + Cache adapter           | M    |
| [T-703](docs/implementation/tasks/T-703.md) | S07                              | `app/infrastructure/http/` shared httpx + tenacity + OTel          | M    |
| [T-704](docs/implementation/tasks/T-704.md) | S07                              | `app/infrastructure/storage/local.py` BlobStorage local adapter    | M    |
| [T-705](docs/implementation/tasks/T-705.md) | S07                              | *(REMOVED — deferred to Phase 3)*                                  | —    |
| [T-706](docs/implementation/tasks/T-706.md) | S07                              | `app/infrastructure/rate_limit/redis.py`                           | M    |
| [T-707](docs/implementation/tasks/T-707.md) | S07                              | `app/infrastructure/idempotency/redis.py`                          | M    |
| [T-708](docs/implementation/tasks/T-708.md) | S07                              | `app/core/wiring/storage.py`, `cache.py`                           | M    |
| [T-801](docs/implementation/tasks/T-801.md) | S08 Persistence + migrations     | Alembic init + `alembic/env.py` async config                       | M    |
| [T-802](docs/implementation/tasks/T-802.md) | S08                              | Initial migration: pgvector extension + base metadata              | M    |
| [T-803](docs/implementation/tasks/T-803.md) | S08                              | Integration test: DB session + pgvector type round-trip            | M    |
| [T-901](docs/implementation/tasks/T-901.md) | S09 Auth                         | `app/auth/domain.py`                                               | M    |
| [T-902](docs/implementation/tasks/T-902.md) | S09                              | `app/auth/ports.py` (IdentityProvider, TokenSigner, PasswordHasher)| M    |
| [T-903](docs/implementation/tasks/T-903.md) | S09                              | `app/auth/adapters/argon2_hasher.py`                               | M    |
| [T-904](docs/implementation/tasks/T-904.md) | S09                              | `app/auth/adapters/jwt_signer.py`                                  | M    |
| [T-905](docs/implementation/tasks/T-905.md) | S09                              | `app/auth/persistence.py` (users, refresh_tokens) + migration      | M    |
| [T-906](docs/implementation/tasks/T-906.md) | S09                              | `app/auth/service.py` + `policies.py` + `deps.py`                  | M    |
| [T-907](docs/implementation/tasks/T-907.md) | S09                              | `app/auth/api.py` (register/login/refresh/logout)                  | M    |
| [T-908](docs/implementation/tasks/T-908.md) | S09                              | Auth API tests + refresh-reuse detection test                      | M    |
| [T-910](docs/implementation/tasks/T-910.md) | S09 Users                        | `app/users/{domain,persistence,service,api,deps}.py` GET /users/me | M    |
| [T-1001](docs/implementation/tasks/T-1001.md) | S10 Prompts                      | `app/prompts/{domain,ports,registry}.py` + `__init__.py`           | M    |
| [T-1002](docs/implementation/tasks/T-1002.md) | S10                              | `app/prompts/library/rag_answer_v1.yaml` + IO schemas              | M    |
| [T-1003](docs/implementation/tasks/T-1003.md) | S10                              | `app/prompts/api.py` (read-only inspection)                        | M    |
| [T-1004](docs/implementation/tasks/T-1004.md) | S10                              | Prompt registry render + schema-validation tests                   | M    |
| [T-1100](docs/implementation/tasks/T-1100.md) | S11 LLM + embeddings ports       | `app/ai_governance/{domain,ports}.py` (pre-llm interface only)     | M    |
| [T-1101](docs/implementation/tasks/T-1101.md) | S11                              | `app/llm/{domain,ports,observability,router}.py`                   | M    |
| [T-1102](docs/implementation/tasks/T-1102.md) | S11                              | `app/llm/service.py` (governance gate + observation)               | M    |
| [T-1103](docs/implementation/tasks/T-1103.md) | S11                              | `app/embeddings/{domain,ports,service}.py`                         | M    |
| [T-1104](docs/implementation/tasks/T-1104.md) | S11                              | Fake `ChatModel` + fake `EmbeddingModel` test doubles              | M    |
| [T-1105](docs/implementation/tasks/T-1105.md) | S11                              | ChatModel contract test suite (parameterized)                      | M    |
| [T-1106](docs/implementation/tasks/T-1106.md) | S11                              | EmbeddingModel contract test suite (parameterized)                 | M    |
| [T-1202](docs/implementation/tasks/T-1202.md) | S12                              | `app/ai_governance/persistence.py` (3 tables) + migration          | M    |
| [T-1203](docs/implementation/tasks/T-1203.md) | S12                              | `app/ai_governance/service.py` (check_call_allowed, record_usage)  | M    |
| [T-1204](docs/implementation/tasks/T-1204.md) | S12                              | `app/ai_governance/events.py` + audit emit                         | M    |
| [T-1205](docs/implementation/tasks/T-1205.md) | S12                              | `app/ai_governance/api.py` (read-only) + wiring                    | M    |
| [T-1206](docs/implementation/tasks/T-1206.md) | S12                              | Budget-deny + 80% warning + audit tests                            | M    |
| [T-1210](docs/implementation/tasks/T-1210.md) | S12+S11                          | `app/infrastructure/llm_providers/openai.py` (ChatModel adapter)    | M    |
| [T-1211](docs/implementation/tasks/T-1211.md) | S12+S11                          | `app/infrastructure/embedding_providers/openai.py`                  | M    |
| [T-1212](docs/implementation/tasks/T-1212.md) | S12+S11                          | `app/core/wiring/llm.py`, `embeddings.py`, `governance.py`         | M    |
| [T-1301](docs/implementation/tasks/T-1301.md) | S13 Documents (domain + API)     | `app/documents/{domain,ports}.py`                                  | M    |
| [T-1302](docs/implementation/tasks/T-1302.md) | S13                              | `app/documents/parsers/` (txt, md, html, pdf via pypdf)            | M    |
| [T-1303](docs/implementation/tasks/T-1303.md) | S13                              | `app/documents/chunkers/` (recursive token-aware, tiktoken)        | M    |
| [T-1304](docs/implementation/tasks/T-1304.md) | S13                              | `app/documents/persistence.py` (documents, chunks) + migration     | M    |
| [T-1305](docs/implementation/tasks/T-1305.md) | S13                              | `app/documents/api.py` POST/GET endpoints                          | M    |
| [T-1401](docs/implementation/tasks/T-1401.md) | S14 Queue + worker               | `app/infrastructure/queue/arq.py` TaskQueue adapter                | M    |
| [T-1402](docs/implementation/tasks/T-1402.md) | S14                              | `app/core/wiring/queue.py` + worker entrypoint sharing wiring      | M    |
| [T-1403](docs/implementation/tasks/T-1403.md) | S14                              | `app/documents/ingestion.py` job + `app/documents/service.py`      | M    |
| [T-1404](docs/implementation/tasks/T-1404.md) | S14                              | Integration test: enqueue → run → status transitions               | M    |
| [T-1501](docs/implementation/tasks/T-1501.md) | S15 Vector store                 | `app/rag/ports.py` (VectorStore)                                   | M    |
| [T-1502](docs/implementation/tasks/T-1502.md) | S15                              | `app/infrastructure/vector_stores/pgvector.py` adapter             | M    |
| [T-1503](docs/implementation/tasks/T-1503.md) | S15                              | `app/core/wiring/vector_store.py`                                  | M    |
| [T-1504](docs/implementation/tasks/T-1504.md) | S15                              | Integration test: real pgvector similarity round-trip              | M    |
| [T-1601](docs/implementation/tasks/T-1601.md) | S16 RAG                          | `app/rag/{domain,pipeline,service}.py`                             | M    |
| [T-1602](docs/implementation/tasks/T-1602.md) | S16                              | `app/rag/api.py` POST `/rag/ask`                                   | M    |
| [T-1603](docs/implementation/tasks/T-1603.md) | S16                              | RAG unit + API tests (citations always present)                    | M    |
| [T-1701](docs/implementation/tasks/T-1701.md) | S17 Golden-path integration      | End-to-end test: upload → ingest → ask → answer + citation         | M    |
| [T-1702](docs/implementation/tasks/T-1702.md) | S17                              | LLMCallObservation field-completeness assertion                    | M    |
| [T-1703](docs/implementation/tasks/T-1703.md) | S17                              | Continuous-trace assertion (POST /ask → embed → search → chat)     | M    |
| [T-1801](docs/implementation/tasks/T-1801.md) | S18 Docs + hardening             | Update `docs/architecture.md`, `docs/folder-structure.md`, `docs/dependency-graph.md` | M |
| [T-1802](docs/implementation/tasks/T-1802.md) | S18                              | Update `README.md` quickstart + golden-path walkthrough            | M    |
| [T-1803](docs/implementation/tasks/T-1803.md) | S18                              | Mark ADR-0009 Superseded; ensure ADRs 0018–0022 cross-linked       | M    |
| [T-1804](docs/implementation/tasks/T-1804.md) | S18                              | Final `make check` on clean checkout                               | M    |

---

## 5. Links to split files

- Implementation rules, stop signals, allowed-files & command discipline, lower-complexity model instructions: [`docs/implementation/rules.md`](docs/implementation/rules.md)
- Reviewer model instructions, final review checklist, architecture compliance checklist, golden-path acceptance summary: [`docs/implementation/review.md`](docs/implementation/review.md)
- Per-task specs (one file per task, preserving the exact format — Purpose / Depends on / Allowed files / Forbidden / Implementation requirements / Tests required / Acceptance criteria / Commands / Common failure modes / Review checklist):
  - [`docs/implementation/tasks/`](docs/implementation/tasks/) — 93 task files: `T-101.md` through `T-1804.md`.
