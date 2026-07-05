# ADR-0029: Keep framework and provider types at the edges

- Status: Proposed
- Date: 2026-07-05
- Supersedes: none
- Superseded by: none
- Related: ADR-0018 (platform ports layer), ADR-0026 (infrastructure as an outer adapter ring), ADR-0027 (pragmatic ports-and-adapters), ADR-0028 (module-local use-case orchestration)

## Context

The project uses FastAPI, SQLAlchemy, Redis, provider SDKs, background workers, and AI provider integrations. These tools are necessary, but they should not dominate the business-facing parts of the application.

A key lesson from Clean Architecture and Ports-and-Adapters is that framework and provider details should stay near the edges. Inner application flows should depend on stable project-owned types and ports.

The project already follows this direction in several places:

- API errors are translated through Problem Details at the API edge.
- Concrete infrastructure adapters live under `app.infrastructure`.
- Ports are defined by platform, capability, or domain modules.
- Concrete adapters are selected in `app.core.wiring.*`.
- Provider-specific payloads should not leak into API responses or domain services.

This ADR makes that rule explicit.

## Decision

Framework-specific and provider-specific types must stay at the appropriate edge.

The following are edge concerns:

- FastAPI request, response, routing, dependency, and exception primitives;
- SQLAlchemy engine/session/model-specific infrastructure primitives;
- Redis client types;
- Arq worker/client/job types;
- HTTPX client/response types where used as provider transport;
- OpenAI, Anthropic, or provider SDK request/response objects;
- pgvector/vector-store driver objects;
- storage SDK objects;
- any other concrete external integration type.

These types must not leak into domain, capability, platform port, or use-case boundaries unless a task or ADR explicitly authorizes the boundary.

The preferred flow is:

1. Edge/framework code translates external inputs into project-owned request or command types.
2. Use cases and services depend on project-owned types and ports.
3. Infrastructure adapters translate between project-owned ports and provider SDKs.
4. API edge code translates project-owned results into HTTP responses.
5. Errors crossing the API boundary are sanitized and shaped by the project’s error model.

## Rules

1. FastAPI types belong in `app.api`, `app.main`, or approved dependency/wiring surfaces.

2. Provider SDK types belong in `app.infrastructure.*` or in narrowly approved adapter modules.

3. SQLAlchemy infrastructure types belong in infrastructure DB modules, persistence modules, or approved wiring/session boundaries.

4. Domain, capability, and use-case code should depend on project-owned ports and DTOs, not provider SDK payloads.

5. Platform ports must not expose concrete provider/client types.

6. API responses must not expose raw provider payloads unless explicitly modeled and sanitized.

7. Infrastructure adapters are responsible for translating provider-specific objects into project-owned results or errors.

8. If an external type appears in an inner module, the task must explain why and the reviewer must treat it as an architectural decision.

## Consequences

### Positive

- Keeps business logic testable without frameworks or provider SDKs.
- Makes provider replacement realistic.
- Reduces accidental lock-in to OpenAI, Redis, SQLAlchemy, Arq, or FastAPI internals.
- Keeps API behavior predictable and sanitized.
- Makes use cases easier to test with fakes.
- Strengthens the ports-and-adapters model.

### Neutral

- Some translation code is required at the edges.
- Some project-owned DTOs or result types may be needed where raw SDK payloads would be quicker.

### Negative

- More explicit mapping code may be required.
- There is a risk of over-modeling if every provider payload is wrapped too aggressively.
- Reviewers must distinguish harmless edge-local types from harmful inner-layer leakage.

## Alternatives considered

### 1. Allow provider SDK types throughout the application

Rejected.

This is quick at first but makes provider replacement difficult. It also spreads external semantics into business logic and tests.

### 2. Wrap every external object immediately

Rejected as a universal rule.

Wrapping everything can create unnecessary DTOs and mapping layers. The project should wrap external objects when they cross a boundary, not reflexively at every line of code.

### 3. Keep framework/provider types at the edges and translate at boundaries

Accepted.

This balances replaceability and implementation cost.

## Implementation notes

Examples of acceptable edge-local usage:

- FastAPI `Request` in API middleware.
- SQLAlchemy `AsyncSession` in a DB session dependency or repository/persistence adapter.
- Redis client in `app.infrastructure.redis.*`.
- OpenAI SDK response in `app.infrastructure.llm_providers.openai.*`.
- Arq job types in `app.infrastructure.queue.arq` or approved worker wiring.

Examples of suspicious leakage:

- `app.rag.service` accepting an OpenAI SDK response object.
- `app.documents` depending directly on an S3 SDK client.
- `app.ai` returning raw provider payloads to the API layer.
- `app.platform.cache.ports.Cache` exposing a Redis client type.
- `app.api` directly importing a concrete infrastructure adapter.

## Review guidance

A reviewer should ask:

- Does this module import a framework or provider SDK type?
- Is this module an approved edge/adapter/wiring surface?
- Is the external type crossing into a domain, capability, platform port, or use-case boundary?
- Should this be represented as a project-owned type instead?
- Is the adapter translating provider errors into project errors?
- Are provider payloads sanitized before reaching API responses?
- Would this code still be easy to test if the provider changed?

## Relationship to task specs

Task specs that introduce provider integrations must explicitly state:

- where the provider SDK is allowed;
- which port is implemented;
- which project-owned type crosses the boundary;
- which tests prove provider-specific objects do not leak;
- which wiring surface binds the adapter.

If the task does not specify those boundaries, implementation must stop and the task spec must be corrected.

## Summary

Frameworks and providers are implementation details. They are welcome at the edges, but they must not define the shape of the application core.

The core speaks in project-owned ports, commands, results, and errors. Adapters translate.
