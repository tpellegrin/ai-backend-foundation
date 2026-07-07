# AI Backend Foundation

A production-grade FastAPI backend foundation for AI-native products.

AI Backend Foundation provides the architecture, runtime structure, and engineering discipline needed to build reliable systems around LLMs, retrieval, document processing, background jobs, governance, observability, and API edge hardening.

It is designed as a reusable platform substrate: modular enough to adapt, strict enough to scale, and explicit enough to extend safely.

---

## Foundation pillars

| Architecture | Readiness | Delivery |
| --- | --- | --- |
| Modules own their domain concepts end to end. Application code depends on ports, provider code sits behind adapters, and import rules are enforced mechanically. | Runtime concerns are part of the foundation: typed settings, structured errors, request correlation, health probes, structured logging, tracing hooks, and sanitized failure paths. | Work is split into small tasks with allowed files, forbidden changes, acceptance criteria, stop conditions, and review checklists. |

---

## What it provides

- **FastAPI application foundation** with explicit app creation, lifespan, and wiring boundaries
- **Strict module boundaries** enforced by Import Linter
- **Typed configuration** with Pydantic Settings
- **RFC 9457 Problem Details** for consistent API errors
- **Request correlation** with `X-Request-ID`
- **Structured logging** with `structlog`
- **Health, readiness, and liveness probes**
- **Security headers and pagination utilities**
- **Platform ports** for storage, cache, queue, rate limiting, idempotency, and future cross-cutting capabilities
- **Pragmatic ports-and-adapters architecture** for provider replacement
- **Layered application core** with explicit infrastructure adapter boundaries
- **Runtime wiring container** for resources, adapters, and use-case assembly
- **Task-driven implementation workflow** with specifications, review contracts, and implementation patterns

---

## Current status

| Area | Status |
| --- |------|
| Python 3.13 tooling with `uv` | Done |
| Ruff, Mypy, Pytest, coverage, pre-commit, and Makefile workflows | Done |
| Docker/local development stack | Done |
| Import-boundary contracts | Done |
| Shared primitives and application error hierarchy | Done |
| RFC 9457 Problem Details | Done |
| Typed settings | Done |
| Observability primitives | Done |
| App composition root, lifespan, and wiring boundary | Done |
| API exception handling | Done |
| Security headers and pagination | Done |
| Health/readiness/liveness infrastructure | Done |
| Platform ports and initial infrastructure adapters | Done |
| Auth and users | In progress |
| Prompt registry | Next |
| Documents, ingestion, embeddings, vector store, RAG, citations, governance | Planned |

The core foundation is in place and the product-oriented AI slices are being added incrementally, while the next product slice builds toward:

```text
documents → ingestion job → embeddings → vector store → RAG answer with citations
```

---

## Architecture model

This project uses pragmatic **ports and adapters** with a layered application core.

In pattern terms, it is closest to Hexagonal Architecture / Ports and Adapters. The repository makes the concrete dependency rules explicit so the architecture can be enforced mechanically instead of relying on convention.

The core rule is:

```text
Application code depends on ports.
Infrastructure adapters implement ports.
Only app.core.wiring.* imports concrete infrastructure adapters.
```

Runtime construction follows the same boundary:

```text
Resources are created by wiring.
Adapters are created by wiring.
Use cases are assembled by wiring.
API handlers receive already-wired application objects.
```

FastAPI dependency injection is used at the API edge, but it is not the application composition model. API dependencies may retrieve already-wired use cases or request-scoped edge concerns. They must not manually construct Redis, database, OpenAI, storage, queue, vector-store, or other infrastructure adapters.

The architecture has three main parts.

### 1. Layered application core

```text
app.main
app.api
app.core
app.auth
app.users
app.documents
app.rag
app.llm
app.embeddings
app.prompts
app.ai_governance
app.platform
app.shared
app.observability
```

Application and capability modules own their ports locally. There is no global `app.ports` package.

### 2. Outer driven-adapter ring

```text
app.infrastructure.*
```

Infrastructure modules contain concrete driven adapters: Postgres, Redis, storage, queues, HTTP clients, LLM providers, embedding providers, vector stores, and similar runtime integrations.

Infrastructure adapters may import the ports they implement. They must not import application composition code or unrelated infrastructure adapters.

### 3. Composition surface

```text
app.core.wiring.*
```

Wiring modules create resources, instantiate adapters, and assemble use cases. This is the approved place for binding concrete infrastructure into application workflows.

Practical dependency shape:

```text
Entrypoints call the app:
app.main / app.api / future app.worker
        ↓
Layered application core
        ↓ depends on ports
Ports owned by platform/domain/capability modules

Infrastructure adapters implement those ports:
app.infrastructure.* → app.<owner>.ports

Concrete adapters are selected only by:
app.core.wiring.* → app.infrastructure.*
```

Valid examples:

```text
app.infrastructure.redis.cache -> app.platform.cache.ports
app.infrastructure.storage.local -> app.platform.storage.ports
app.infrastructure.llm_providers.openai -> app.llm.ports
app.infrastructure.vector_stores.pgvector -> app.rag.ports
app.core.wiring.cache -> app.infrastructure.redis.cache
```

Forbidden examples:

```text
app.api.* -> app.infrastructure.*
app.main.* -> app.infrastructure.*
app.rag.* -> app.infrastructure.*
app.platform.* -> app.infrastructure.*
app.infrastructure.redis.* -> app.infrastructure.storage.*
```

Entrypoints and delivery mechanisms such as `app.main`, `app.api`, and a future `app.worker` are application edge modules. They are not placed under `app.infrastructure`, which is reserved for driven adapters the application calls outward.

Import boundaries are enforced with Import Linter. If a task conflicts with those boundaries, implementation stops and the task spec or architecture docs are corrected before code continues.

See:

- [`docs/phase-2-revision/03-revised-dependency-graph.md`](docs/phase-2-revision/03-revised-dependency-graph.md)
- [`docs/dependency-graph.md`](docs/dependency-graph.md)
- [`docs/adr/0026-infrastructure-as-outer-adapter-ring.md`](docs/adr/0026-infrastructure-as-outer-adapter-ring.md)
- [`docs/adr/0027-use-pragmatic-ports-and-adapters.md`](docs/adr/0027-use-pragmatic-ports-and-adapters.md)
- [`docs/adr/0029-keep-framework-and-provider-type-at-the-edges.md`](docs/adr/0029-keep-framework-and-provider-type-at-the-edges.md)
- [`docs/adr/0030-centralize-application-wiring.md`](docs/adr/0030-centralize-application-wiring.md)

---

## Project structure

```text
app/
  main/              # ASGI entrypoint and app creation
  api/               # API edge: errors, routers, pagination, security headers
  core/              # settings, container, lifespan, wiring
  shared/            # shared primitives, application errors, Problem Details
  observability/     # logging, correlation, health, tracing, metrics
  platform/          # cross-cutting ports: storage, cache, queue, etc.
  infrastructure/    # concrete driven adapters behind ports

  auth/              # authentication slice
  users/             # user profile slice
  documents/         # document ingestion slice
  rag/               # retrieval-augmented generation slice
  llm/               # LLM ports and service layer
  embeddings/        # embedding model ports
  prompts/           # prompt registry
  ai_governance/     # budgets, policy, audit, governance checks
```

The structure avoids broad technical buckets such as `models/`, `schemas/`, `services`, and `routers`. Modules own their concepts end to end.

---

## Engineering methodology

Implementation is task-driven.

Each task lives in:

```text
docs/implementation/tasks/
```

Each task defines:

- purpose
- dependencies
- allowed files
- forbidden changes
- implementation requirements
- tests required
- acceptance criteria
- common failure modes
- review checklist

The workflow is intentionally strict:

```text
task spec
  ↓
implementation
  ↓
review against architecture and rules
  ↓
patch findings
  ↓
re-review
  ↓
commit
```

If a task needs files outside its allowed list, implementation stops. The task spec is patched first, reviewed, and committed separately when appropriate. The project does not rely on hard-coded shortcuts or boundary workarounds to make tests pass.

This keeps changes small enough to review and concrete enough to test.

---

## AI-assisted development process

The repository includes operating procedures for AI-assisted implementation and review:

```text
docs/ai/
  implement-task.md
  review-task.md
  apply-review.md
  architect.md
```

These documents are not a substitute for engineering judgment. They define guardrails for using AI agents on bounded tasks: respect allowed files, stop on contradictions, preserve dependency boundaries, and produce deterministic review reports.

Implementation patterns are captured in:

```text
docs/implementation/patterns.md
```

The process is based on a simple constraint: AI-assisted work is more reliable when the unit of work is small, the context is explicit, and the expected result is testable. The repository is structured around that constraint.

---

## Quality gates

Core checks:

```bash
uv sync --all-groups
make fmt
make lint
make typecheck
make test
uv run lint-imports
```

The foundation is guarded by:

- Ruff formatting and linting
- Mypy strict typing
- Pytest with coverage gate
- Import Linter contracts
- pre-commit hooks
- Docker build validation
- structured task review

Quality gates are not bypassed. If a gate fails because the task is under-specified, the task is fixed.

---

## API edge standards

The API edge is designed to be predictable and safe:

- centralized exception handling
- RFC 9457 Problem Details responses
- sanitized 500 errors
- no stack traces or provider payloads in responses
- `X-Request-ID` on success and error responses
- security headers as middleware
- pagination as a typed dependency
- no ad-hoc `HTTPException` usage below the API layer

---

## Observability

Observability is part of the foundation, not a later add-on.

Implemented and planned observability primitives include:

- structured JSON logs
- request correlation
- access logs
- health/readiness/liveness endpoints
- OpenTelemetry resource, tracer, and meter configuration
- future spans for LLM calls, embedding calls, queue jobs, ingestion, and RAG

The design keeps observability reusable without letting it dominate business modules.

---

## AI platform roadmap

The platform is being built toward an end-to-end AI workflow:

1. document upload
2. blob storage
3. background ingestion with Arq
4. PDF/text extraction
5. chunking
6. embeddings
7. pgvector storage
8. prompt registry
9. governance checks
10. RAG answer generation
11. citations
12. audit trail

Provider-specific code is kept behind ports so concrete providers can be replaced without rewriting product logic.

Planned adapter surfaces include:

- OpenAI chat
- OpenAI embeddings
- OpenAI-compatible providers
- Redis cache
- Arq queue
- local/S3-like blob storage
- pgvector vector store

Implementation progress is tracked in [`docs/implementation/roadmap.md`](docs/implementation/roadmap.md).

---

## Scope

This repository focuses on the backend foundation required to build AI-native products.

It intentionally prioritizes:

- architecture over feature breadth
- explicit contracts over implicit coupling
- replaceable adapters over provider lock-in
- production runtime concerns over demo shortcuts
- testable slices over large unreviewable changes
- durable process over one-off implementation speed

Product-specific features, UI concerns, billing, tenant management, and business workflows belong in applications built on top of this foundation.

---

## Important documents

Read in order:

1. [`AGENTS.md`](AGENTS.md)
2. [`docs/architecture.md`](docs/architecture.md)
3. [`docs/folder-structure.md`](docs/folder-structure.md)
4. [`docs/phase-2-revision/03-revised-dependency-graph.md`](docs/phase-2-revision/03-revised-dependency-graph.md)
5. [`docs/dependency-graph.md`](docs/dependency-graph.md)
6. [`docs/technology-decisions.md`](docs/technology-decisions.md)
7. [`docs/implementation/rules.md`](docs/implementation/rules.md)
8. [`docs/implementation/patterns.md`](docs/implementation/patterns.md)
9. [`docs/implementation/roadmap.md`](docs/implementation/roadmap.md)
10. [`docs/adr/`](docs/adr/)

---

## Design philosophy

AI systems should be built like long-lived software systems from the start.

That means clear boundaries, explicit contracts, replaceable adapters, observable runtime behavior, typed configuration, testable modules, and a process that prevents architectural drift.

The same standard applies to the repository itself. Large ambiguous changes are broken into small, inspectable tasks. Each task has defined inputs, allowed files, acceptance criteria, review rules, and quality gates.

Strictness is intentional. It makes future features cheaper, reviews clearer, integrations safer, and AI-assisted development more reliable.
