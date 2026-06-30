# Technology Decisions

> One row per technology. Why it's in, what it competed against, what we give up by choosing it, and where it might bite us at scale.

The table is intentionally opinionated. Every "Why" answer must hold up in five years.

---

## Language & runtime

### Python 3.13

- **Why**: Best-in-class ecosystem for AI (PydanticAI, LangGraph, official provider SDKs). 3.13 brings improved typing (`TypeIs`, better generics ergonomics), faster startup, and the free-threaded build pathway for the future. The AI ecosystem is Python-native; fighting that is a tax.
- **Alternatives considered**: Go (great runtime, weak AI SDKs), Node/TypeScript (good AI SDKs, weaker numerical stack and DX with Pydantic-equivalents), Rust (operationally heavy for product teams).
- **Tradeoff**: GIL still constrains true CPU parallelism in 3.13 mainstream builds. We mitigate by keeping the HTTP path I/O-bound (async) and offloading CPU work to workers.
- **Future bottleneck**: heavy CPU-bound tasks (parsing, reranking) — addressed via worker pools and, where it matters, native bindings (e.g. `tiktoken`, `rapidfuzz`).

---

## Dependency & environment management

### uv

- **Why**: Fast, deterministic, lockfile-first, single binary, replaces pip+pip-tools+virtualenv+poetry. Authoritative for Python projects starting in 2025. See [ADR-0014](adr/0014-uv-as-package-manager.md).
- **Alternatives considered**: Poetry (slower, fragile lockfile, plugin churn), pip-tools + venv (manual), pdm (smaller ecosystem).
- **Tradeoff**: relatively young; we accept that it occasionally moves faster than its docs. Pinning the uv version in CI mitigates.
- **Future bottleneck**: monorepo workspaces — uv already supports workspaces, ready when we need them.

---

## Web framework

### FastAPI

- **Why**: Async-native, Pydantic-native, OpenAPI generation is automatic and accurate, mature ecosystem, dependency-injection via `Depends` is sufficient for our composition root. Streaming responses (SSE) are first-class.
- **Alternatives considered**: Litestar (excellent, smaller community), Starlette directly (too low level for a foundation), Django+DRF (sync-first, heavyweight for AI workloads), Flask (no async story worth shipping).
- **Tradeoff**: FastAPI is "Starlette + Pydantic + DI conventions" — we accept light coupling to Starlette internals (middleware, lifespan).
- **Future bottleneck**: very large numbers of routes hurt OpenAPI generation; we mitigate by mounting per-version routers and keeping per-module routers small.

---

## Validation & schemas

### Pydantic v2

- **Why**: Rust-backed performance, exhaustive validation, the de-facto schema layer for FastAPI and PydanticAI. Structured outputs from LLMs are validated by it directly.
- **Alternatives considered**: msgspec (faster, but ecosystem coupling to Pydantic is decisive), attrs (no validation), dataclasses (no validation).
- **Tradeoff**: Pydantic models can creep from the API edge into the domain. We resist this explicitly: domain types may be Pydantic models **only** when validation belongs to the domain; otherwise use `@dataclass(slots=True, frozen=True)`.

---

## Database

### PostgreSQL

- **Why**: Single most boring, durable, capable database in our class. Triggers, partial indexes, JSONB, listen/notify, logical replication, and a healthy extension ecosystem.
- **Alternatives considered**: MySQL (weaker extension story), SQLite (great for tests, not for production multi-writer workloads), CockroachDB (premature for foundation).
- **Future bottleneck**: write-heavy ingest at scale — partitioning, read replicas, and worker-side batching. Multi-region — logical replication or a managed Postgres with geo-replication.

### pgvector

- **Why**: One database, one operational surface for relational + vector. HNSW and IVFFlat indices are sufficient up to single-digit millions of vectors. Removes an entire service from our infra in early product life.
- **Alternatives considered**: Qdrant (excellent, additive operational cost), Pinecone (managed, vendor lock-in), Weaviate (heavier).
- **Tradeoff**: pgvector recall/latency degrades at very large scales and lacks some hybrid-search ergonomics. **Mitigation**: `VectorStore` port. We can swap to Qdrant per-collection without touching `rag/`. See [ADR-0005](adr/0005-vector-store-abstraction.md).

### SQLAlchemy 2.x + asyncpg + Alembic

- **Why**: Typed declarative API, mature async engine, the best migration tooling in Python. asyncpg is the fastest, most correct PG driver. See [ADR-0003](adr/0003-async-sqlalchemy-asyncpg-alembic.md).
- **Alternatives considered**: SQLModel (Pydantic + SQLAlchemy hybrid; we prefer separation), Tortoise ORM (smaller ecosystem), raw asyncpg + hand-rolled migrations (high friction).
- **Tradeoff**: SQLAlchemy is non-trivial to master; we keep usage idiomatic, lean on the typed declarative style, and document patterns in a developer guide.

---

## Cache & queue substrate

### Redis

- **Why**: Cache, rate-limit token buckets, idempotency-key storage, short-term conversation memory, Arq queue backend. One operational dependency, many uses.
- **Alternatives considered**: Memcached (no data structures), Dragonfly/Valkey (Redis-compatible; we can swap silently if needed), in-process LRU (not horizontally scalable).
- **Future bottleneck**: persistence guarantees for queue durability — Redis with AOF is acceptable; if durability requirements rise, swap `TaskQueue` adapter to SQS/Cloud Tasks.

---

## Background work

### Arq (Phase 3)

- **Why**: Async-native, small, Redis-backed, no Celery operational weight, integrates cleanly with FastAPI's async stack. See [ADR-0009](adr/0009-background-jobs-arq.md).
- **Alternatives considered**: Celery (sync-first, heavy), Dramatiq (async support is bolted on), Taskiq (promising but younger), Temporal (excellent for workflows; overkill for the foundation, additive later behind the `TaskQueue` port).
- **Future bottleneck**: complex workflows (retries with state, sagas) — introduce Temporal as an additional adapter or sibling system; do not stretch Arq for what it isn't.

---

## AI runtime

### PydanticAI

- **Why**: Pydantic-native, typed agents, typed tools, typed results, provider-agnostic, streaming-first. The right abstraction layer between us and provider SDKs without forcing LangChain weight on us. See [ADR-0006](adr/0006-pydanticai-as-agent-runtime.md).
- **Alternatives considered**: LangChain/LangGraph (powerful, leaky abstractions, expensive cognitive overhead), Instructor (great for structured outputs only; PydanticAI subsumes it), raw provider SDKs (no agent runtime).
- **Tradeoff**: PydanticAI is young; we wrap it behind our own `llm/` port so we are never bound to its API.

### Provider SDKs: openai, anthropic, google-genai

- **Why**: First-party SDKs are the most up-to-date with provider features (e.g., new model parameters, structured outputs, tool format changes). Adapters wrap them behind our `ChatModel` port.
- **Alternatives**: LiteLLM as a single multiplexer — we **borrow the idea** (provider router) but keep our own port to avoid an additional runtime dependency we can't shape.

---

## Authentication

### JWT (Ed25519 / RS256) + Argon2id

- **Why**: Industry-standard, stateless access tokens, asymmetric signing for safe multi-service verification. Argon2id is the current best-practice for password hashing. See [ADR-0002](adr/0002-authentication-jwt-argon2.md).
- **Alternatives considered**: opaque session tokens with a session table (fine, but less convenient for multi-service futures), HS256 (acceptable in a single deployable, fragile across services), bcrypt (acceptable; Argon2id is strictly better in 2025).
- **Future bottleneck**: SSO/OIDC, scoped tokens, organization-level roles — `IdentityProvider` port lets us add OIDC adapters without changing domains.

---

## Observability

### structlog

- **Why**: Best-in-class structured logging in Python, plays well with both JSON sinks and dev-friendly console rendering, integrates with OTel via context vars.
- **Alternatives considered**: stdlib `logging` (works but verbose), loguru (opinionated, harder to integrate with OTel correlation).

### OpenTelemetry

- **Why**: Vendor-neutral, the obvious choice for traces + metrics + logs propagation. Auto-instrumentation for FastAPI, SQLAlchemy, httpx, Redis exists and is solid.
- **Alternatives considered**: Sentry (great for errors; **complementary**, not a replacement), proprietary APM agents (lock-in).
- **Future bottleneck**: span volume / cardinality — handled by tail-based sampling at the collector layer, not in app code.

See [ADR-0001](adr/0001-observability-stack-structlog-otel.md).

---

## Tooling

### Ruff (linter + formatter)

- **Why**: One tool to replace Flake8, isort, Black, pyupgrade, pydocstyle. Fast enough to run on save. See [ADR-0015](adr/0015-ruff-as-single-linter-formatter.md).
- **Alternatives**: Black + isort + Flake8 (three tools, three configs, slower).

### Mypy (strict)

- **Why**: Mature, widely understood, integrates with editors and CI. Pyright/Pylance is an editor companion; mypy is the gate.
- **Alternatives considered**: Pyright as the gate — excellent but its CLI ergonomics for CI are weaker; we may add it later as an additional check.

### Pytest + pytest-asyncio + testcontainers + polyfactory

- **Why**: Canonical async testing stack. Testcontainers gives us real Postgres/Redis in CI without flakiness from in-process fakes. Polyfactory builds typed test data from Pydantic models.

### Docker + Docker Compose

- **Why**: The smallest local development surface that matches production semantics. Compose for local; the same image deploys to k8s/Cloud Run/etc.

### Pre-commit

- **Why**: Local fast-fail before CI; same hooks run in CI as a backstop.

---

## API contract

### OpenAPI 3.1 + RFC 9457 Problem Details

- **Why**: OpenAPI is generated by FastAPI from Pydantic models — no drift. RFC 9457 is the modern replacement for RFC 7807; one consistent error shape is a contract feature. See [ADR-0010](adr/0010-rfc9457-problem-details-errors.md).

---

## Multi-tenancy posture (forward-looking)

- All domain entities will carry an `account_id` / `tenant_id` from day one, even before the foundation is multi-tenant in product.
- Tenant isolation is enforced at the query layer (a `TenantContext` injected via DI), with the door open to Postgres Row-Level Security policies if a product requires hard isolation.
- This decision is cheap now; retrofitting is brutal.

---

## What we deliberately did **not** pick (and why)

- **LangChain / LlamaIndex** — too many leaky abstractions, breaking changes are routine. We borrow ideas (chunkers, retrievers) without taking the dependency.
- **GraphQL (Strawberry / Ariadne)** — not justified for the foundation; REST + OpenAPI covers our needs and is faster to teach.
- **gRPC** — internal-only value; we have no internal-service problem yet. Easy to add later.
- **Kafka** — operational weight not justified. Redis Streams covers our queue/event needs at this stage; Kafka becomes an additional adapter behind ports when we have the events-per-second to warrant it.
- **A custom DI container** — FastAPI's `Depends` plus a small startup `Container` dataclass is enough. See [ADR-0017](adr/0017-dependency-injection-strategy.md).
- **SQLModel** — blends two concerns (validation + ORM) that we deliberately keep separate.
- **Alembic auto-migrations as the source of truth** — Alembic generates a starting point; humans review and edit. Auto-generated migrations are not authoritative.
