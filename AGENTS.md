# AGENTS.md

> Instructions for **any** automated coding agent (and humans) contributing to this repository.
> These rules are not advice. They are enforced by `import-linter`, `ruff`, `mypy`, and CI.
> If a rule contradicts the issue you are working on, stop and open an ADR. Do not silently break it.

---

## 1. Project purpose

`ai-backend-foundation` is a **production substrate for building multiple AI products** on Python 3.13 / FastAPI / SQLAlchemy 2.x / Postgres+pgvector / Redis / Arq. It is **not** a CRUD template, **not** a tutorial, **not** an architecture museum. Every decision optimizes for **cost of change**, not first-write speed.

Read in order before contributing:
1. `docs/architecture.md`
2. `docs/folder-structure.md`
3. `docs/dependency-graph.md`
4. `docs/phase-2-revision/` (current authoritative pack)
5. `docs/adr/`

---

## 2. Architecture rules (non-negotiable)

1. Optimize for change, not first-write speed.
2. Abstract only what is genuinely volatile: LLM, embeddings, vector store, blob storage, cache, queue, auth provider, external APIs.
3. **Do not** abstract FastAPI, Pydantic, SQLAlchemy, or PostgreSQL.
4. Vertical slices. No top-level `models/`, `schemas/`, `routers/`, `services/`, `repositories/`, `utils/`, `common/`, `helpers/`.
5. Every module's public surface goes through its `__init__.py`. Nothing else is public.
6. **No module may import another module's `persistence.py` or `adapters/`.**
7. Infrastructure adapters must never leak into domain code.
8. Business logic must not depend on FastAPI, SQLAlchemy, provider SDKs, or HTTP concepts.
9. SQLAlchemy ORM classes must never cross the persistence boundary.
10. Pydantic models live at the API edge (`api.py`) and for validation-heavy domain value objects. **Never** mix ORM/API/domain into one class.
11. Every external call must be observable.
12. Every LLM call must record `LLMCallObservation` with: provider, model, prompt_id, prompt_version, tokens_in, tokens_out, latency_ms, cost_usd, status, request_id, tenant_id.
13. Every LLM call must consult `app.ai_governance.service.check_call_allowed(...)` **before** invoking the provider.
14. Prompts are versioned artifacts in `app/prompts/library/`. **No inline prompt strings** in business logic.
15. RAG answers must include citations. No exceptions.

---

## 3. Module boundary rules

The dependency graph is in `docs/phase-2-revision/03-revised-dependency-graph.md`. The short version:

- **Layers**, top-to-bottom: `main` → `api` → `core` → domain (`auth|users|documents|rag|ai|ai_governance`) → capability (`llm|embeddings|prompts`) → `platform` → `infrastructure` → leaves (`shared`, `observability`).
- A module at layer `N` may import only from layers `< N`.
- **Only `app.core.wiring.*` may import from `app.infrastructure.*`.** Nowhere else. Ever.
- Domain code imports **ports** from `app.platform.*`, never adapters.
- `app.llm`, `app.embeddings`, `app.prompts` are siblings; they do not import each other.
- `app.ai` and `app.rag` are siblings; they do not import each other.
- `app.auth` does not import `app.users`.
- `app.users` may import `app.auth` **read-only domain types** only (not `auth.persistence`, not `auth.adapters`).

Every new edge requires (a) updating the dep-graph doc and (b) updating `importlinter.toml` **in the same PR**.

---

## 4. Folder structure rules

Inside `app/<module>/`:

| File / folder        | Allowed to contain                                                   | Forbidden to contain                                              |
| -------------------- | -------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `__init__.py`        | re-exports of the module's public surface only                       | implementations                                                   |
| `domain.py`          | dataclasses, value objects, domain errors, pure functions            | FastAPI, SQLAlchemy, httpx, SDK imports, `app.infrastructure.*`, `app.platform.*` adapters |
| `ports.py`           | `Protocol` definitions for outbound dependencies                     | implementations                                                   |
| `service.py`         | use-case orchestration; depends on ports + domain                    | HTTP request/response types, SQLAlchemy mapped classes            |
| `api.py`             | FastAPI router + Pydantic request/response models                    | business logic, SQL queries, ORM objects in responses             |
| `persistence.py`     | SQLAlchemy mapped classes + queries returning **domain** types       | leaking mapped classes outside the module                         |
| `adapters/`          | module-specific adapter implementations                              | being imported by other modules                                   |
| `deps.py`            | FastAPI `Depends` providers                                          | business logic                                                    |
| `tests/`             | unit and module-scoped integration tests                             | reaching into other modules' privates                             |

Top-level forbidden folder names (CI rejects): `models/`, `schemas/`, `routers/`, `services/`, `repositories/`, `utils/`, `common/`, `helpers/`.

---

## 5. Testing requirements

Every change must include tests appropriate to its kind:

- **Unit tests** for `domain.py` and pure logic in `service.py` — no I/O.
- **API tests** for every new endpoint with: happy path, auth-fail (401), validation-fail (422), Problem Details shape, `X-Request-ID` echo.
- **Integration tests** (Testcontainers) for anything touching Postgres, Redis, pgvector, or Arq. Do **not** fake pgvector in tests that claim to validate retrieval.
- **Contract tests** for any new adapter implementing a Port (`ChatModel`, `EmbeddingModel`, `VectorStore`, `BlobStorage`, `TaskQueue`, `Cache`).
- **Settings tests** for any new `BaseSettings` field — assert bad values fail startup.
- **Boundary tests**: `import-linter` runs in CI; do not exclude a contract to silence a failure.

Coverage gate: `--cov-fail-under=80` on `app/`.

---

## 6. Commands to run before completion

In this order, locally, before opening a PR:

```bash
make fmt          # ruff format
make lint         # ruff check
make typecheck    # mypy --strict on app/
make test         # unit + api tests
make test-int     # integration tests (requires docker)
make check        # runs everything CI runs, including import-linter
```

If `make check` does not pass, the change is not done.

---

## 7. Forbidden patterns (CI will reject these)

- `from app.infrastructure.<anything> import ...` anywhere **except** under `app/core/wiring/`.
- `from app.platform.<x>.adapters import ...` — there are no adapters in `platform/`; it is ports only.
- Importing a provider SDK (`openai`, `anthropic`, `google.generativeai`, `cohere`, `voyageai`, `qdrant_client`, `boto3`, `redis`, `arq`, `pydantic_ai`) **outside** its dedicated adapter file. `pydantic_ai` is imported **only** in `app/ai/agent_runner.py`.
- `import os; os.environ[...]` or `os.getenv(...)` **outside** `app/core/config/`.
- Constructing a SQLAlchemy `Session` / `AsyncSession` **outside** `app/infrastructure/db/`.
- Returning a SQLAlchemy mapped class from a service or an API handler.
- A top-level `models/`, `schemas/`, `routers/`, `services/`, `repositories/`, `utils/`, `common/`, `helpers/` folder.
- `print(` in `app/`. Use `structlog`.
- `requests`, `urllib.request`, sync `psycopg2`, `time.sleep` in `app/`. Use `httpx`, `asyncpg`, `asyncio.sleep`.
- `# type: ignore` without a code (`# type: ignore[<rule>]`) and a one-line reason.
- `except Exception: pass`, bare `except:`, or swallowing exceptions without re-raising or recording.
- Hardcoded secrets, model names, prompt strings, or URLs in business logic.
- Returning provider raw responses or stack traces in error payloads.
- Inline prompt strings in `service.py` / `pipeline.py`. All prompts live in `app/prompts/library/`.
- Calling an LLM without going through `app.llm.service` (which enforces governance + observation).

---

## 8. How to add a new module

1. Create `app/<module>/` with at minimum: `__init__.py`, `domain.py`, `tests/`.
2. If the module exposes HTTP: add `api.py`, register router in `app/api/v1.py`.
3. If the module owns tables: add `persistence.py`, add an Alembic migration in the same PR.
4. If the module depends on a cross-cutting capability: import the port from `app.platform.*`, not the adapter.
5. Add an entry for the module to `importlinter.toml` (which other modules it may import from).
6. Update `docs/folder-structure.md` and `docs/dependency-graph.md` in the same PR.
7. Open an ADR if the module changes a public interface, introduces/removes a dependency, or constrains future contributors.

---

## 9. How to add a new provider adapter

Example: adding `AnthropicChatModel`.

1. Create `app/infrastructure/llm_providers/anthropic.py`. This is the **only** file allowed to import the `anthropic` SDK.
2. Implement the `app.llm.ports.ChatModel` Protocol. Translate provider types into the **domain** types defined in `app.llm.domain`. Do not leak SDK types outward.
3. Add a settings block to `app.core.config` (model id, API key as `SecretStr`, base URL).
4. Wire the adapter in `app/core/wiring/llm.py` behind a config switch.
5. Run the existing `ChatModel` **contract test suite** against the new adapter (parameterized).
6. Add per-call observation: ensure provider/model/cost are reported via `LLMCallObservation`.
7. Update `docs/architecture.md` table of adapters.

The same shape applies for `EmbeddingModel`, `VectorStore`, `BlobStorage`, `TaskQueue`, `Cache`, `RateLimiter`, `IdempotencyStore`.

---

## 10. How to add a new prompt

1. Create `app/prompts/library/<prompt_id>_v<n>.yaml`.
2. The YAML must declare: `id`, `version` (semver), `description`, `owner`, `template` (Jinja2), `input_schema` (Pydantic model path), `output_schema` (Pydantic model path if structured).
3. Add the input/output Pydantic schemas next to the YAML.
4. Add a unit test that renders the template with a sample input and validates the rendered output's shape.
5. Bump `version` when changing the template; **never edit a published version in place**.
6. Phase 3: add a golden dataset under `app/prompts/evals/<prompt_id>/`.

Inline prompt strings in any other file are a CI failure.

---

## 11. How to add a new API endpoint

1. Add the route in `app/<module>/api.py`. Request and response models are Pydantic v2 in the same file.
2. Use `Annotated[..., Depends(...)]` for dependencies. Pull the current user from `app.auth.deps.get_current_user`.
3. Return domain types translated to API response models — never an ORM mapped class.
4. Document errors using `responses=` in the route decorator. Error bodies are **always** RFC 9457 Problem Details (`app.shared.problem_details`).
5. Make sure the global error handler is registered in `app/api/errors.py`; do not catch broad exceptions inside the handler.
6. Add API tests: happy path, 401, 422, Problem Details shape assertion, `X-Request-ID` echo.
7. If the endpoint is a write that can be retried: depend on `app.api.idempotency.IdempotencyKey`.
8. If the endpoint is rate-limited: depend on `app.api.rate_limit.RateLimit(...)`.

---

## 12. How to handle errors

- Raise a subclass of `app.shared.errors.AppError` from domain/service code. Never raise `Exception` directly. Never raise `HTTPException` from below `api.py`.
- `app/api/errors.py` is the single mapping from `AppError` → Problem Details. Do not add ad-hoc handlers in route files.
- Problem Details payloads must include `type`, `title`, `status`, `detail`, `code`, `request_id`. Never include stack traces, SQL, secrets, or provider raw responses.
- Inside a traced operation, mark the span as errored: `span.set_status(StatusCode.ERROR)` and `span.record_exception(...)`.
- Every error path must log structurally with `logger.error(...)` and the request id in context.

---

## 13. How to handle observability

- All logs go through `structlog` (configured in `app.observability.logging`). Never `print`, never `logging.getLogger(...)` ad hoc.
- Every request carries `X-Request-ID`. The correlation middleware sets it on the request context and the response header. Use `app.observability.correlation.request_id_var.get()` if you need it inside services.
- Every external HTTP call goes through `app.infrastructure.http` (auto-traced httpx).
- Every LLM call is wrapped by `app.llm.service`, which:
    - opens an OTel span with name `llm.chat` and the 11 required attributes;
    - records an `LLMCallObservation`;
    - logs `event="llm.call"` structurally.
- Every background job emits `job_id`, `job_name`, `attempt`, `request_id`/`correlation_id`, and `tenant_id` (when present).
- Health probes: `/healthz` (liveness), `/readyz` (deps reachable), `/livez` (process), optional `/metrics`.

---

## 14. How to avoid overengineering

Before adding a new abstraction, answer **yes** to at least one:

1. Does this isolate a third-party API that we have observed churn in?
2. Does this enable a known replacement (provider, store, queue, etc.)?
3. Does this make tests dramatically cheaper for a path that runs in CI?

If none apply: do not add the abstraction. Inline the logic. We can extract it later when the second consumer appears.

Specific anti-patterns to **not** introduce:
- A generic `Repository<T>` per entity.
- A custom DI container (we use FastAPI `Depends` + a `Container` dataclass).
- A homegrown agent framework on top of PydanticAI.
- A new top-level folder for a "concept" that has no production caller yet.
- A second prompt template engine.
- A new error envelope shape next to Problem Details.

Defer until justified: GraphQL, WebSockets, microservice split, DDD aggregates, event sourcing, multi-modal pipelines.

---

## 15. When in doubt

Open an ADR. The format is in `docs/adr/README.md`. A bad decision recorded is recoverable; an unrecorded one is not.
