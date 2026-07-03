# AI Backend Foundation

A production-grade backend foundation for AI-native products.

AI Backend Foundation provides the architecture, runtime structure, and engineering discipline needed to build reliable systems around LLMs, retrieval, document processing, background jobs, governance, observability, and API edge hardening.

It is designed as a reusable platform substrate: modular enough to adapt, strict enough to scale, and explicit enough to extend safely.

---

## Foundation pillars

| Bounded Architecture | Operational Readiness | Disciplined Delivery |
| --- | --- | --- |
| Modules own their domain concepts end to end. Dependency direction is explicit, provider integrations sit behind ports, and architecture rules are enforced mechanically. | Runtime concerns are built in from the start: typed settings, structured errors, request correlation, health probes, structured logging, tracing hooks, and sanitized failure paths. | Work is decomposed into small, reviewable tasks with explicit scope, acceptance criteria, implementation patterns, and stop conditions. |

---

## What it provides

- **FastAPI application foundation** with a dedicated composition root
- **Strict module boundaries** enforced by Import Linter
- **Typed configuration** with Pydantic Settings
- **RFC 9457 Problem Details** for consistent API errors
- **Request correlation** with `X-Request-ID`
- **Structured logging** with `structlog`
- **Health, readiness, and liveness probes**
- **Security headers and pagination utilities**
- **Platform ports** for storage, cache, queue, and future cross-cutting capabilities
- **Ports-and-adapters architecture** for provider replacement
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

The remaining Phase 2 work completes the golden-path product slice:

```text
documents → ingestion job → embeddings → vector store → RAG answer with citations
```

---

## Architecture

The project follows a layered, modular architecture:

```text
app.main
  ↓
app.api
  ↓
app.core
  ↓
domain modules
  ↓
capability modules
  ↓
app.platform / app.infrastructure
  ↓
app.shared / app.observability
```

The dependency graph is part of the architecture and is mechanically enforced.

Core rules:

- lower layers never import upward
- `app.main` owns application composition
- `app.core` owns container, DI, lifespan, and wiring primitives
- domain modules stay vertically sliced
- infrastructure adapters do not leak into business logic
- provider-specific objects never cross port boundaries
- shared behavior is explicit, not hidden in global helpers

See [`docs/dependency-graph.md`](docs/dependency-graph.md).

---

## Project structure

```text
app/
  main/              # ASGI entrypoint and app composition
  api/               # API edge: errors, routers, pagination, security headers
  core/              # settings, container, DI, lifespan, wiring
  shared/            # shared primitives, application errors, Problem Details
  observability/     # logging, correlation, health, tracing, metrics
  platform/          # cross-cutting ports: storage, cache, queue, etc.
  infrastructure/    # concrete adapters behind ports

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
4. [`docs/dependency-graph.md`](docs/dependency-graph.md)
5. [`docs/technology-decisions.md`](docs/technology-decisions.md)
6. [`docs/implementation/rules.md`](docs/implementation/rules.md)
7. [`docs/implementation/patterns.md`](docs/implementation/patterns.md)
8. [`docs/adr/`](docs/adr/)

---

## Design philosophy

AI systems should be engineered like long-lived software systems from day one.

That means clear boundaries, explicit contracts, replaceable adapters, observable runtime behavior, typed configuration, testable modules, and a process that prevents architectural drift.

The same principle applies to the way the repository is built. Large ambiguous requests are broken into small, inspectable tasks. Each task has defined inputs, allowed files, acceptance criteria, review rules, and quality gates.

Strictness is intentional. It makes future features cheaper, reviews clearer, integrations safer, and AI-assisted development more reliable.
