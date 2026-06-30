# AI Backend Foundation

> A production-grade, AI-first backend platform foundation.
> Not a CRUD boilerplate. Not a demo. A reusable engineering substrate for building many AI products.

---

## Status

**Phase 1 + Phase 2 architecture revision (this commit).**
No implementation code is included yet, by design. Implementation begins after the revised architecture is approved.

| Phase   | Scope                                                                                   | Status      |
| ------- | --------------------------------------------------------------------------------------- | ----------- |
| Phase 1 | Architecture, folder structure, technology decisions, ADRs, dep graph                   | ✅ Delivered |
| Phase 1.5 | Pre-Phase-2 revision pack: contradictions resolved, `platform/` + `ai_governance/` introduced, Arq promoted, golden-path slice defined, `AGENTS.md`, ADRs 0018–0022 | ✅ Delivered |
| Phase 2 | Foundation + golden-path vertical slice (documents → RAG with citations + governance + Arq) | ⏳ Pending approval |
| Phase 3 | Multi-provider adapters, agents, evals, hybrid retrieval, governance maturity            | ⏳ Pending  |

The repository was renamed from `ai-backend-boilerplate` to `ai-backend-foundation` (see [ADR-0021](docs/adr/0021-repository-rename-to-foundation.md)).

---

## What this is

A backend platform designed to be:

- **AI-first** — LLMs, embeddings, RAG, agents, tool-calling and streaming are first-class, not bolted on.
- **Modular** — vertical slices by domain. Business logic never leaks across module boundaries.
- **Replaceable** — LLM providers, embedding providers, vector store, blob storage, cache, and queue are all behind explicit interfaces. Anthropic, OpenAI, Gemini and OpenAI-compatible providers are interchangeable.
- **Async-first** — FastAPI + async SQLAlchemy 2.x + async drivers end-to-end.
- **Observable** — structured logs, traces, metrics, correlation IDs and health/readiness/liveness from day one.
- **Testable** — pure domain logic, ports & adapters, dependency overrides, factories, and (where it pays off) testcontainers.
- **Pleasant** — one-command local startup, strict typing, pre-commit, Ruff, Mypy, sensible Makefile.

## What this is **not**

- Not a tutorial app.
- Not a clean-architecture cargo cult — patterns are applied only where they earn their keep.
- Not a place for `models/`, `schemas/`, `services/`, `routers/` top-level folders.
- Not a multi-tenant SaaS product. It is the **foundation** on top of which such products are built.

---

## Read these first (in order)

1. [AGENTS.md](AGENTS.md) — enforceable contributor rules for humans and AI agents.
2. [docs/architecture.md](docs/architecture.md) — overall architecture and principles.
3. [docs/folder-structure.md](docs/folder-structure.md) — every directory, what it owns, what it must not own.
4. [docs/dependency-graph.md](docs/dependency-graph.md) — module dependency rules (enforced in CI).
5. [docs/phase-2-revision/](docs/phase-2-revision/) — **authoritative** pack for Phase 2: contradictions, revised tree, revised dep graph, Phase 2/3 scope, risk register.
6. [docs/technology-decisions.md](docs/technology-decisions.md) — why each technology was chosen, alternatives, tradeoffs, and future scaling bottlenecks.
7. [docs/adr/](docs/adr/) — the Architecture Decision Records that pin the consequential choices.

## Approval gate

This commit is intentionally documentation-only. Once reviewed and approved, Phase 2 materializes the foundation **and** the first golden-path vertical slice (see [docs/phase-2-revision/04-phase-2-scope.md](docs/phase-2-revision/04-phase-2-scope.md)):

- `pyproject.toml` (uv), `uv.lock`, tool configs, `Makefile`, `Dockerfile`, `docker-compose.yml`, pre-commit, `importlinter.toml`, CI.
- `app/core/` (settings, app factory, lifespan, DI, `wiring/`).
- `app/shared/`, `app/observability/`, `app/api/`.
- `app/platform/` — cross-cutting ports (storage, cache, queue, rate_limit, idempotency).
- `app/infrastructure/` — adapters for db, redis, http, storage, queue (Arq), rate_limit, idempotency, OpenAI chat, OpenAI embeddings, pgvector.
- `app/auth/` + `app/users/` minimal skeletons.
- `app/prompts/`, `app/llm/`, `app/embeddings/`, `app/ai_governance/` (budgets + audit + governance API).
- `app/documents/` (POST /documents + ingestion via Arq) and `app/rag/` (POST /rag/ask with citations).
- `app/ai/` skeleton (`AgentRunner` facade only).
- Tests: unit, API, integration (Testcontainers: Postgres+pgvector, Redis, Arq), contract suites for ports, import-linter contracts.

No placeholder code. Every file in Phase 2 will be production-quality. The golden path runs end-to-end on `make up`.
