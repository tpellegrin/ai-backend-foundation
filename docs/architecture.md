# Architecture

> The goal of this document is to make every architectural decision in this repository **explainable in one sentence and defensible in five years**.

---

## 1. Guiding philosophy

We optimize for **change**, not for first-write speed. AI products mutate rapidly: new providers, new modalities, new retrieval strategies, new agent topologies. The architecture must absorb that change without rewrites.

Four non-negotiable properties drive every decision:

1. **Replaceability** — every external dependency (LLM, embedder, vector store, blob storage, cache, queue, auth provider) sits behind an explicit interface owned by the consuming domain.
2. **Locality of change** — adding a new AI capability should touch one module and the composition root, nothing else.
3. **Honest types** — Pydantic v2 at the edge, dataclasses/`@dataclass(slots=True)` or Pydantic models in the domain, SQLAlchemy 2.x ORM mapped classes at the persistence boundary. The type system is part of the design.
4. **Observability is not optional** — every request carries a correlation ID, every external call is a span, every domain event is logged structurally.

We pragmatically apply **SOLID**, **Hexagonal Architecture (Ports & Adapters)**, and **vertical slicing**. We deliberately reject dogmatic Clean Architecture: we only introduce a layer or an abstraction when it earns its keep by either (a) enabling a known replacement, (b) isolating a third party, or (c) making tests dramatically cheaper.

---

## 2. The shape of the system

```
                           ┌────────────────────────┐
                           │   API (FastAPI app)    │
                           │  versioned routers     │
                           └───────────┬────────────┘
                                       │
                          composition root (app/core)
                                       │
        ┌──────────────┬───────────────┼───────────────┬──────────────┐
        ▼              ▼               ▼               ▼              ▼
     auth/          users/           ai/             rag/         documents/
   (JWT, pw)      (identity)     (agents,        (pipeline,      (ingest,
                                 memory,         retrieval,       chunk)
                                 tools)          citations)
        │              │               │               │              │
        └──────────────┴──────┬────────┴───────┬───────┴──────────────┘
                              ▼                ▼
                            llm/          embeddings/        prompts/
                       (provider ports)  (provider ports)  (versioned
                                                            templates)
                              │                │
                              ▼                ▼
                       infrastructure/  (adapters: OpenAI, Anthropic,
                                         Gemini, pgvector, Redis, S3, …)

                shared/  ◄── pure cross-cutting types only (errors, ids, pagination)
                observability/  ◄── logging, tracing, metrics, middleware
```

Three things to notice:

- Domain modules (`auth`, `users`, `ai`, `rag`, `documents`) **depend on capability modules** (`llm`, `embeddings`, `prompts`) **only via their ports**, never their adapters.
- Adapters for capability modules live in `infrastructure/<provider>/…` and are wired in the composition root.
- `shared/` and `observability/` are leaves of the dependency graph. They depend on nothing in the app and everyone depends on them.

The full dependency rules are spelled out in [dependency-graph.md](dependency-graph.md) and will be enforced via `import-linter` in Phase 2 ([ADR-0011](adr/0011-enforce-module-boundaries-with-import-linter.md)).

---

## 3. Vertical slices, not file-type folders

Top-level folders represent **domains and capabilities**, not technical roles. There is no top-level `models/`, `schemas/`, `routers/`, or `services/`. A change like "add citations to RAG answers" lives almost entirely inside `app/rag/`.

Inside a module we use a small, consistent internal layout — but only when the module is non-trivial:

```
app/<module>/
    __init__.py        # public surface (re-exports the small public API)
    domain.py | domain/    # entities, value objects, domain errors, pure logic
    ports.py | ports/      # Protocols / ABCs the module depends on (outbound)
    service.py | application/  # use cases / orchestrators
    api.py | api/          # FastAPI router(s), request/response Pydantic models
    persistence.py | persistence/  # SQLAlchemy mapped classes + queries (if module owns tables)
    adapters/          # inbound/outbound adapters specific to this module
    events.py          # domain events (optional)
    deps.py            # FastAPI dependency providers for this module
    tests/             # co-located unit tests for the module
```

We do **not** force every module to have all of these files. A tiny module is a single file. A complex module (e.g. `rag`) gets subpackages. The rule is: **structure should reflect complexity, not aspiration**.

See [folder-structure.md](folder-structure.md) for the annotated tree.

---

## 4. Ports & Adapters, applied pragmatically

The system has a small, intentional set of **ports** (interfaces). Each port has one or more adapters.

| Port (interface)        | Owner module     | Adapters (Phase 2/3)                                 |
| ----------------------- | ---------------- | ---------------------------------------------------- |
| `ChatModel`             | `llm`            | OpenAI, Anthropic, Gemini, OpenAI-compatible (vLLM, Groq, Together, Azure OpenAI) |
| `EmbeddingModel`        | `embeddings`     | OpenAI, Voyage, Cohere, local (sentence-transformers via sidecar) |
| `VectorStore`           | `rag`            | pgvector (default), Qdrant, Pinecone (future)        |
| `PromptRegistry`        | `prompts`        | filesystem + DB-backed                               |
| `ConversationStore`     | `ai`             | Postgres, Redis (short-term)                         |
| `BlobStorage`           | `infrastructure` | local FS (dev), S3 (prod), GCS                       |
| `Cache`                 | `infrastructure` | Redis                                                |
| `TaskQueue`             | `infrastructure` | Arq (Phase 3, see [ADR-0009](adr/0009-background-jobs-arq.md)) |
| `IdentityProvider`      | `auth`           | local JWT, OIDC (future)                             |
| `Clock`, `IdGenerator`  | `shared`         | system, deterministic-for-tests                      |

**Why ports?** Because each of these *will* be swapped. Not hypothetically — observably, in real AI products, within months. The cost of the Protocol is roughly zero; the cost of not having it is a rewrite.

**Why not more ports?** We do not abstract Postgres, SQLAlchemy, FastAPI, or Pydantic. Replacing them is a different project. Abstracting them buys nothing and costs daily friction. This is the deliberate line where Clean Architecture stops being useful and starts being theater.

See [ADR-0004](adr/0004-llm-provider-abstraction.md), [ADR-0005](adr/0005-vector-store-abstraction.md), [ADR-0007](adr/0007-no-generic-repository-pattern.md).

---

## 5. The AI core

The AI capability is structured as four cooperating modules:

### 5.1 `llm/` — chat models behind one port

- `ChatModel` protocol: `complete(messages, *, tools, response_model, stream) -> ChatResult | AsyncIterator[ChatChunk]`.
- Built on **PydanticAI** as the agent runtime ([ADR-0006](adr/0006-pydanticai-as-agent-runtime.md)) and on provider SDKs underneath.
- Structured outputs are first-class: pass a Pydantic model, get a validated instance back. No regex on JSON.
- Streaming is the default shape; non-streaming is a thin collector on top.
- Tool-calling is provider-agnostic at the port; provider quirks live in adapters.
- A small **router** in front (cost/latency/capability based) is allowed but optional; defaults to a single configured model.

### 5.2 `embeddings/` — vectors behind one port

- `EmbeddingModel` protocol: `embed(texts: list[str]) -> list[Vector]` + `dimensions: int`.
- Batching, retries, and rate-limit awareness live in a shared `infrastructure/llm_client/` resilience layer (httpx + tenacity), not in each adapter.

### 5.3 `prompts/` — versioned, observable, testable

- Prompts are **first-class artifacts**, not f-strings sprinkled in code.
- Each prompt has: an ID, a semantic version, a Pydantic input schema, a Pydantic output schema (when structured), and an evaluation harness hook.
- Stored as files in `app/prompts/library/` initially, with optional DB-backed overrides for live editing.
- See [ADR-0008](adr/0008-prompt-management-and-versioning.md).

### 5.4 `ai/` — agents, memory, tools, MCP-ready

- Agents are PydanticAI agents composed in `ai/agents/`, each with explicit tools and a typed result model.
- `ConversationStore` is an outbound port; default adapter is Postgres with a Redis short-term cache.
- Tool registry is explicit; tools are typed callables with Pydantic input/output. The same registry will expose MCP-compatible descriptors in the future ([ADR-0012](adr/0012-future-mcp-compatibility.md)).
- Streaming reaches the HTTP edge as **Server-Sent Events** by default.

### 5.5 `rag/` — retrieval pipeline

The pipeline is a small composition of pure stages:

```
ingest → normalize → chunk → embed → upsert(VectorStore)
query → expand? → embed → search(VectorStore) → rerank? → cite → answer(ChatModel)
```

- Chunking strategies are pluggable (recursive, token-aware, structural).
- Citations are attached at retrieval time so the answer step cannot lose them.
- pgvector is the default ([ADR-0005](adr/0005-vector-store-abstraction.md)) because it removes an entire operational service in early product life; the `VectorStore` port keeps Qdrant/Pinecone reachable.

---

## 6. Persistence

- **SQLAlchemy 2.x** with the typed declarative API (`Mapped[...]`, `mapped_column`) and the **async engine** + `asyncpg` driver.
- **Alembic** for migrations; one migration history for the whole app. Each module owns its tables but shares the metadata.
- **No generic `Repository<T>`**. Queries are written as small functions that take an `AsyncSession` and return domain objects or DTOs. Repositories appear only when a module legitimately needs to swap persistence (rare) or has a complex query surface worth naming ([ADR-0007](adr/0007-no-generic-repository-pattern.md)).
- **Unit of Work** is the request: one `AsyncSession` per request, committed by the route handler or the application service, rolled back by the error middleware.
- **pgvector** is enabled at the database level; vector columns are normal columns with a typed wrapper.
- Connection pooling via SQLAlchemy's async pool; PgBouncer compatibility is preserved (no server-side prepared statements with transaction pooling — configured explicitly).

See [ADR-0003](adr/0003-async-sqlalchemy-asyncpg-alembic.md).

---

## 7. API design

- **REST-first**, versioned under `/api/v1/...`. GraphQL is explicitly out of scope for the foundation.
- **OpenAPI** generated by FastAPI is the contract; we lint it in CI.
- **Errors** follow **RFC 9457 Problem Details** with a small set of stable `type` URIs and a `code` machine identifier. One central error model, one error middleware ([ADR-0010](adr/0010-rfc9457-problem-details-errors.md)).
- **Pagination**: cursor-based for list endpoints (`?cursor=...&limit=...`); offset pagination is permitted only for admin views.
- **Idempotency**: write endpoints that can be retried accept `Idempotency-Key` headers; results are cached in Redis with a bounded TTL.
- **Validation**: Pydantic v2 at the edge for both request and response models. Domain types are separate from API types; we never leak ORM objects to the HTTP boundary.
- **Streaming**: Server-Sent Events for token streams; WebSocket reserved for bidirectional agent UIs (future).
- **Rate limiting**: hooks via a `RateLimiter` dependency (Redis token-bucket adapter in Phase 2).

---

## 8. Authentication & security

- **JWT access tokens** (short-lived) + **opaque refresh tokens** stored hashed in Postgres. Algorithm: EdDSA (Ed25519) or RS256; never HS256 in multi-service deployments.
- **Argon2id** for password hashing (`argon2-cffi`). Bcrypt is acceptable but Argon2id is the default ([ADR-0002](adr/0002-authentication-jwt-argon2.md)).
- **Secrets** only from environment / secret manager. `.env` files are dev-only and gitignored. Pydantic `BaseSettings` validates and types every setting at startup; the app refuses to boot on misconfiguration.
- **CORS**: deny-by-default; explicit origins per environment.
- **Security headers** middleware (HSTS, X-Content-Type-Options, Referrer-Policy, etc.).
- **Authorization**: a small policy layer in `auth/policies.py`; roles + resource-level checks. RBAC now, ABAC compatible.
- **Audit logging**: sensitive actions emit structured audit events on a dedicated logger.

---

## 9. Observability

- **Structured logging** via `structlog`, JSON in production, key-value in dev. One logger configuration, never `logging.getLogger("root")` ad hoc.
- **OpenTelemetry** for traces and metrics. Auto-instrumentation for FastAPI, SQLAlchemy, httpx, Redis; manual spans around LLM calls with attributes for `model`, `provider`, `prompt_id`, `prompt_version`, `tokens_in`, `tokens_out`, `cost_usd`, `latency_ms`.
- **Correlation IDs**: `X-Request-ID` propagated via context vars; injected into every log record and every outbound HTTP header.
- **Health endpoints**: `/healthz` (liveness — process up), `/readyz` (readiness — dependencies reachable), `/livez` if needed; `/metrics` exposed for Prometheus scrape (optional, behind setting).
- **LLM cost & token accounting**: every chat call records a `LLMCallObservation` (provider, model, tokens, latency, cost, status, prompt_id@version). This is the foundation for evals, billing, and budget guards.

See [ADR-0001](adr/0001-observability-stack-structlog-otel.md).

---

## 10. Async story and background work

- The HTTP path is fully async (FastAPI + asyncpg + httpx).
- CPU-bound or long-running work (document parsing, large embedding batches, evals) runs in a background queue. We choose **Arq** (Redis-backed) for Phase 3: small, async-native, no Celery weight ([ADR-0009](adr/0009-background-jobs-arq.md)).
- The HTTP layer enqueues jobs through the `TaskQueue` port; workers consume them with the same DI container.

---

## 11. Configuration

- One `Settings` class per concern (DatabaseSettings, RedisSettings, LLMSettings, AuthSettings, ObservabilitySettings, …), composed into a root `AppSettings`. All are Pydantic `BaseSettings` ([ADR-0013](adr/0013-config-strategy-pydantic-settings.md)).
- Environments: `local`, `test`, `staging`, `production`. The environment selects defaults; explicit env vars always win.
- No reading of `os.environ` outside the `core/config` module.

---

## 12. Testing strategy

- **Unit tests** for pure domain logic (`domain.py`, `service.py`) — no I/O, fast, deterministic.
- **Contract tests** for ports — every adapter must pass the same suite (e.g. all `ChatModel` adapters answer the same scenarios).
- **Integration tests** with Postgres + Redis via **testcontainers** for the persistence and queue paths.
- **API tests** with `httpx.AsyncClient` against the app; dependency overrides swap real providers for in-memory fakes.
- **Eval tests** (Phase 3+) for prompts: golden datasets, scored with deterministic and LLM-judge metrics. Eval failures break CI on tagged prompts.
- Factories via `polyfactory`; no shared mutable fixtures.

---

## 13. Developer experience

- **`uv`** for dependency and environment management ([ADR-0014](adr/0014-uv-as-package-manager.md)).
- **`make up`** boots the full stack via Docker Compose (api + postgres-with-pgvector + redis + otel-collector).
- **`make test`**, **`make lint`**, **`make typecheck`**, **`make fmt`**, **`make migrate`**, **`make revision msg=...`**.
- **Pre-commit**: Ruff (lint + format), Mypy (strict), end-of-file-fixer, trailing-whitespace, check-merge-conflict, detect-secrets.
- **Ruff** as the only linter and formatter ([ADR-0015](adr/0015-ruff-as-single-linter-formatter.md)).
- **Mypy strict** on `app/`, lenient on `tests/`.
- An **ADR** is required for any decision that is hard to reverse.

---

## 14. Known future bottlenecks (and how the design defers them, not denies them)

| Bottleneck                                  | Likely trigger                          | Designed escape hatch                                    |
| ------------------------------------------- | --------------------------------------- | -------------------------------------------------------- |
| pgvector recall/latency on >10M vectors     | Large corpora, hybrid search needs      | `VectorStore` port → swap to Qdrant/Pinecone; hybrid search via stage in `rag/` |
| Single Postgres write throughput            | Heavy ingest workloads                  | Separate `ingest` worker pool; partitioned tables for documents/embeddings |
| LLM provider lock-in / cost                 | Pricing changes, new SOTA models        | `ChatModel` port + provider router; cost observability already in place |
| Long-running agent runs blocking workers    | Multi-step agents, deep tool use        | Move agent loop to Arq workers; SSE re-attach by run_id  |
| Prompt sprawl                               | More products, more variants            | `prompts/` registry with semver + evals as gate          |
| Multi-tenancy                               | Productization                          | All domain entities carry an `account_id`/`tenant_id` from day one; row-level isolation at the query layer |
| Auth complexity (SSO, orgs, scopes)         | Enterprise customers                    | `IdentityProvider` port; auth module is replaceable without touching domains |
| Vector + relational + full-text in one DB   | Search quality plateau                  | Tantivy/Meilisearch as a `SearchIndex` port (additive)   |
| Eval cost / reproducibility                 | Model drift                             | Versioned prompts + golden datasets + recorded LLM observations |

---

## 15. What we explicitly chose **not** to do

- **No GraphQL** in the foundation. REST + OpenAPI is enough; GraphQL can be added as an additional adapter if a product needs it.
- **No DDD aggregates / event sourcing**. Overkill for the foundation; reachable by introducing `events.py` per module if a product requires it.
- **No microservices**. One deployable, multiple modules. We split when a real boundary appears, not before.
- **No custom DI container** (no `dependency-injector`, no `punq`). FastAPI's `Depends` is the composition root for HTTP; a small `Container` dataclass wires singletons at startup ([ADR-0017](adr/0017-dependency-injection-strategy.md)).
- **No ORM behind a repository for every entity**. SQLAlchemy 2.x is already a good enough abstraction for our use cases.
- **No premature abstraction of FastAPI, Pydantic, SQLAlchemy, or Postgres**. These are foundational dependencies, not pluggable providers.

---

## 16. How to evaluate this architecture

A reviewer should be able to answer "yes" to each:

1. Can I swap OpenAI for Anthropic without touching `rag/` or `ai/`? **Yes** — change config + adapter wiring.
2. Can I add a new domain module (e.g. `evaluations/`) without modifying any other module? **Yes** — it depends on `llm/`, `prompts/`, `shared/` only.
3. Can I run the full system locally with one command? **Yes** — `make up`.
4. Can I trace one HTTP request from edge to LLM provider and back? **Yes** — correlation ID + OTel spans.
5. Can I delete a module and have the type checker tell me everything that breaks? **Yes** — strict typing + explicit public surfaces.
6. Can I onboard a new engineer in a day? **Yes** — README → architecture → folder-structure → one ADR → first PR.

If any answer becomes "no" in the future, that is a bug in the architecture, not in the code.
