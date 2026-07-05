# AI Backend Foundation

A production-grade backend foundation for AI-native products.

AI Backend Foundation provides the architecture, runtime structure, and engineering discipline needed to build reliable systems around LLMs, retrieval, document processing, background jobs, governance, observability, and API edge hardening.

It is designed as a reusable platform substrate: modular enough to adapt, strict enough to scale, and explicit enough to extend safely.

---

## Foundation pillars

| Bounded Architecture | Operational Readiness | Disciplined Delivery |
| --- | --- | --- |
| Modules own their domain concepts end to end. Dependency boundaries are explicit, provider integrations sit behind ports, and architecture rules are enforced mechanically. | Runtime concerns are built in from the start: typed settings, structured errors, request correlation, health probes, structured logging, tracing hooks, and sanitized failure paths. | Work is decomposed into small, reviewable tasks with explicit scope, acceptance criteria, implementation patterns, and stop conditions. |

---

## What it provides

- **FastAPI application foundation** with a dedicated composition path
- **Strict module boundaries** enforced by Import Linter
- **Typed configuration** with Pydantic Settings
- **RFC 9457 Problem Details** for consistent API errors
- **Request correlation** with `X-Request-ID`
- **Structured logging** with `structlog`
- **Health, readiness, and liveness probes**
- **Security headers and pagination utilities**
- **Platform ports** for storage, cache, queue, and future cross-cutting capabilities
- **Pragmatic ports-and-adapters architecture** for provider replacement
- **Layered application core** with explicit infrastructure adapter boundaries
- **AI-ready slices** for LLMs, embeddings, prompts, documents, RAG, and governance
- **Task-driven implementation workflow** with specifications, review contracts, and implementation patterns

---

## Current status

Phase 2 implementation is in progress.

The foundation layer currently includes:

- Python 3.13 project tooling with `uv`
- Ruff, Mypy, Pytest, coverage, pre-commit, and Makefile workflows
- Docker and local development stack
- CI workflow scaffold
- import-boundary contracts
- shared primitives and application error hierarchy
- Problem Details error model
- typed settings
- observability primitives
- app composition root
- API exception handling
- security headers and pagination
- health/readiness/liveness infrastructure
- initial platform ports
- initial infrastructure foundations

The remaining Phase 2 work completes the golden-path product slice:

```text
documents → ingestion job → embeddings → vector store → RAG answer with citations
```

---

## Architecture model

This project uses a pragmatic **ports-and-adapters** architecture with a layered application core.

In pattern terms, it is closest to Hexagonal Architecture / Ports and Adapters, but the repository names the concrete rules explicitly rather than relying on pattern terminology. The goal is simple: application code depends on stable ports, provider-specific code lives behind adapters, and runtime composition happens in one approved place.

The architecture has three main parts:

1. **Layered application core**
    - `app.main`
    - `app.api`
    - `app.core`
    - domain modules such as `app.documents`, `app.rag`, `app.ai`, and `app.ai_governance`
    - capability modules such as `app.llm`, `app.embeddings`, and `app.prompts`
    - platform ports such as storage, cache, queue, rate limiting, and idempotency
    - shared primitives and observability support

2. **Outer driven-adapter ring**
    - `app.infrastructure.*`
    - concrete adapters for Postgres, Redis, storage, queues, HTTP clients, LLM providers, embedding providers, vector stores, and similar runtime integrations
    - adapters import the ports they implement

3. **Composition surface**
    - `app.core.wiring.*`
    - the only approved place where concrete infrastructure adapters are bound into the application

The core rule is:

```text
Application code depends on ports.
Infrastructure adapters implement ports.
Only app.core.wiring.* imports concrete infrastructure adapters.
```

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

This means the following is valid:

```text
app.infrastructure.redis.cache -> app.platform.cache.ports
app.infrastructure.storage.local -> app.platform.storage.ports
app.infrastructure.llm_providers.openai -> app.llm.ports
app.infrastructure.vector_stores.pgvector -> app.rag.ports
app.core.wiring.cache -> app.infrastructure.redis.cache
```

And the following is forbidden:

```text
app.api.* -> app.infrastructure.*
app.main.* -> app.infrastructure.*
app.rag.* -> app.infrastructure.*
app.platform.* -> app.infrastructure.*
app.infrastructure.redis.* -> app.infrastructure.storage.*
```

For Phase 2, `app.infrastructure` is the only modeled outer adapter ring for **driven adapters**: technical integrations the application calls outward. Entrypoints and delivery mechanisms such as `app.main`, `app.api`, and future `app.worker` are modeled separately as application edge modules. They are not placed under `app.infrastructure`.

Import boundaries are mechanically enforced with Import Linter. If a task conflicts with those boundaries, implementation stops and the specification or architecture is corrected before code continues.

See:

- [`docs/phase-2-revision/03-revised-dependency-graph.md`](docs/phase-2-revision/03-revised-dependency-graph.md)
- [`docs/dependency-graph.md`](docs/dependency-graph.md)
- [`docs/adr/0026-infrastructure-as-outer-adapter-ring.md`](docs/adr/0026-infrastructure-as-outer-adapter-ring.md)

---

## Project structure

```text
app/
  main/              # ASGI entrypoint and app creation
  api/               # API edge: errors, routers, pagination, security headers
  core/              # settings, container, DI, lifespan, wiring
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

The structure avoids generic technical buckets such as `models/`, `schemas/`, `services`, and `routers`. Modules own their domain concepts end to end.

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

This keeps work small, explicit, and reviewable. Complex systems are built more safely when each change has a narrow scope, clear inputs, and a defined acceptance boundary.

The workflow:

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

If a task conflicts with the architecture, implementation stops and the specification is corrected first. The process favors architectural integrity over workarounds.

---

## AI-assisted development process

The repository includes operating procedures for AI-assisted development:

```text
docs/ai/
  implement-task.md
  review-task.md
  apply-review.md
  architect.md
```

These documents define how implementation and review agents should:

- implement one task at a time
- respect allowed-file boundaries
- stop on contradictions
- apply review findings
- produce deterministic review reports
- avoid speculative future work
- preserve dependency direction

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

Observability is part of the foundation.

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

Phase 2 builds toward an end-to-end AI workflow:

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

The platform is structured so providers can be replaced without rewriting product logic.

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

Read in this order:

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

AI systems should be engineered like long-lived software systems from day one.

That means clear boundaries, explicit contracts, replaceable adapters, observable runtime behavior, typed configuration, testable modules, and a process that prevents architectural drift.

The same principle applies to the way the repository is built. Large ambiguous requests are broken into small, inspectable tasks. Each task has defined inputs, allowed files, acceptance criteria, review rules, and quality gates.

Strictness is intentional. It makes future features cheaper, reviews clearer, integrations safer, and AI-assisted development more reliable.
