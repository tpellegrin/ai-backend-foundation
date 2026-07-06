# ADR-0027: Use pragmatic ports-and-adapters over strict Clean Architecture rings

- Status: Accepted
- Date: 2026-07-05
- Supersedes: none
- Superseded by: none
- Related: ADR-0018 (platform ports layer), ADR-0023 (composition-root ownership), ADR-0026 (infrastructure as an outer adapter ring), ADR-0028 (module-local use-case orchestration), ADR-0029 (framework and provider types at the edges), ADR-0030 (centralized application wiring and container boundaries)

ADR-0027 is the philosophy/umbrella ADR for the project's architectural approach. ADR-0028, ADR-0029, and ADR-0030 are its more enforceable projections. Mechanical enforcement lives in `.importlinter` (import boundary contracts), `docs/dependency-graph.md` and `docs/folder-structure.md` (structural rules), and the project's review and task specifications.

## Context

The project has been evolving toward a ports-and-adapters architecture with a layered application core, explicit module ownership, and mechanically enforced dependency boundaries.

During the Phase 2 infrastructure work, especially around T-701 and T-702, the project clarified that `app.infrastructure` is an outer adapter ring for driven adapters. Infrastructure adapters implement ports owned by platform, capability, or domain modules, while concrete adapter binding happens only in `app.core.wiring.*`.

This raised a broader architectural question: should the repository move toward a stricter Clean Architecture ring layout, such as:

- entities
- use cases
- interface adapters
- frameworks and drivers

That model is defensible and well-known, but it would reorganize the project around architectural rings rather than bounded product/capability modules.

The current repository is intentionally organized around modules such as:

- `app.documents`
- `app.rag`
- `app.ai`
- `app.ai_governance`
- `app.llm`
- `app.embeddings`
- `app.prompts`
- `app.platform`
- `app.infrastructure`

This structure supports local ownership: a module owns its concepts, ports, services, API surface, tests, and internal rules as much as possible.

Strict Clean Architecture rings would improve theoretical purity, but at the cost of locality and implementation simplicity. A single feature could be scattered across `entities/`, `use_cases/`, `ports/`, `interface_adapters/`, and `frameworks/`. That would make task boundaries wider and harder for both human reviewers and AI agents to follow.

The project needs Clean Architecture discipline, but not necessarily Clean Architecture folder names.

## Decision

The project will use a pragmatic ports-and-adapters architecture with Clean Architecture-inspired dependency discipline, rather than reorganizing around strict Clean Architecture rings.

The repository will keep its bounded module layout.

The accepted architectural model is:

1. The layered application core is organized by bounded modules and capabilities.
2. Ports are owned by the modules that need or define the abstraction.
3. Infrastructure adapters live outside the layered core and implement those ports.
4. Runtime composition is centralized in `app.core.wiring.*`.
5. Entrypoints and delivery mechanisms, such as `app.main`, `app.api`, and future `app.worker`, are modeled separately from infrastructure.
6. Import boundaries are enforced mechanically through Import Linter and review rules.

The project may borrow Clean Architecture ideas, especially:

- dependencies point toward stable abstractions;
- framework and provider types do not leak into inner business flows;
- use-case orchestration should be explicit;
- concrete adapters are selected at composition time;
- API handlers translate requests and responses rather than owning business workflows.

However, the repository will not adopt a global folder layout such as:

- `entities/`
- `use_cases/`
- `interface_adapters/`
- `frameworks/`

unless a future ADR proves that the current module-oriented structure no longer scales.

## Consequences

### Positive

- Preserves local ownership of domain and capability concepts.
- Keeps feature work easier to inspect and review.
- Keeps AI-assisted tasks narrower and less prone to cross-cutting edits.
- Avoids generic architectural buckets that can become dumping grounds.
- Retains the main benefits of Clean Architecture without adopting all of its ceremony.
- Keeps FastAPI integration ergonomic while still preventing framework leakage into inner flows.
- Supports replaceable infrastructure providers through ports and explicit wiring.

### Neutral

- The architecture is not “pure Clean Architecture” in the textbook folder-structure sense.
- The README and docs should describe the project as “pragmatic ports-and-adapters” rather than “strict Clean Architecture.”
- Some concepts may still need explicit documentation because the project uses a hybrid of layered core, ports-and-adapters, and Clean Architecture dependency discipline.

### Negative

- Reviewers familiar with strict Clean Architecture may expect use cases, entities, presenters, gateways, and frameworks to live in separate top-level folders.
- The project must be disciplined to avoid turning module-local services into large unstructured “service” blobs.
- Module ownership can hide ring boundaries unless the implementation patterns remain explicit.

## Alternatives considered

### 1. Adopt strict Clean Architecture rings globally

A strict layout would organize code around rings:

- entities
- use cases
- interface adapters
- frameworks and drivers

Rejected for now.

It provides strong theoretical clarity, but it would scatter bounded product concepts across multiple top-level folders. That increases task size, review complexity, and cognitive overhead. It also conflicts with the project’s current rule that modules own their concepts end to end.

### 2. Keep a traditional layered architecture

A traditional stack would place infrastructure as a lower layer and allow higher layers to import downward.

Rejected.

This is simpler at first, but it is a poor fit for replaceable provider adapters. It makes it harder for infrastructure adapters to implement ports owned by the application, and it encourages domain/API code to depend directly on concrete infrastructure.

### 3. Centralize all ports in a global `app.ports` package

A central ports package would simplify import rules.

Rejected.

ADR-0018 already established that ports live with their owning modules (`VectorStore` near `app.rag`, `ChatModel` near `app.llm`, `Cache` near `app.platform.cache`). A global `app.ports` package weakens local ownership and could become an abstraction dumping ground.

Reopening a global `app.ports` package requires a new ADR that supersedes ADR-0018.

### 4. Continue with pragmatic ports-and-adapters and module ownership

Accepted.

This preserves the current strengths of the repository while adopting the useful parts of Clean Architecture.

## Implementation notes

README and architecture docs should describe the model as:

> A pragmatic ports-and-adapters architecture with a layered application core.

or:

> Clean Architecture-inspired ports-and-adapters, organized around bounded modules rather than textbook ring folders.

Avoid claiming:

> This is strict Clean Architecture.

Prefer:

> The project borrows Clean Architecture’s dependency discipline while keeping module-local ownership.

Future implementation tasks should continue to use bounded module paths unless a task or ADR explicitly introduces a new structural convention.

## Review guidance

A reviewer should reject changes that:

- move code into generic architecture buckets without an ADR;
- introduce provider SDKs into domain, capability, API, or platform modules;
- bypass `app.core.wiring.*` for concrete adapter composition;
- create a central `app.ports` package without an ADR;
- turn module services into broad unstructured orchestration blobs;
- use Clean Architecture terminology to justify unnecessary ceremony.

A reviewer should allow changes that:

- make use-case orchestration clearer inside a bounded module;
- keep ports near their owning module;
- keep concrete adapters in `app.infrastructure`;
- keep FastAPI-specific concerns at the API edge;
- keep provider-specific concerns behind ports.

## Summary

The project chooses pragmatic ports-and-adapters over strict Clean Architecture rings.

The goal is not architectural purity by folder name. The goal is durable boundaries, explicit composition, replaceable adapters, and small reviewable changes.
