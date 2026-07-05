# ADR-0026: Infrastructure as an outer adapter ring

- Status: Accepted
- Date: 2026-07-05
- Supersedes: none
- Superseded by: none
- Related: ADR-0011 (import-linter), ADR-0018 (platform ports layer), ADR-0023 (composition-root ownership), ADR-0025 (direct-import semantics for `core-wiring-only-infra`)

## Context

ADR-0018 established the project’s ports-and-adapters model: platform modules, and later capability/domain modules, define `Protocol` ports; infrastructure modules provide concrete adapters that implement those ports.

ADR-0023 established that runtime composition belongs to the application composition path: `app.main` creates the app, `app.core.lifespan` drives startup/shutdown, and `app.core.wiring.*` is the approved surface where concrete adapters are bound into the application.

T-107 encoded the module boundaries with an `import-linter` `Layers` contract and placed `app.infrastructure` below `app.platform` in that layer stack. The intent was to signal that infrastructure is an implementation detail. The mechanical effect was different: under `import-linter` layer semantics, a lower layer may not import a higher layer. That meant infrastructure adapters could not import the ports they implement.

T-702, which introduces the Redis cache adapter, was the first task to expose this mismatch. The adapter needed the valid edge:

```text
app.infrastructure.redis.* -> app.platform.cache.ports
```

However, the layer order made that edge illegal. The implementer changed `.importlinter` to make `lint-imports` pass, but `.importlinter` was outside T-702’s Allowed files and no ADR or task spec had authorized the contract change. Review correctly rejected the silent contract edit and paused the task.

The same failure would recur for future adapter tasks, including:

```text
app.infrastructure.redis.* -> app.platform.cache.ports
app.infrastructure.storage.* -> app.platform.storage.ports
app.infrastructure.queue.* -> app.platform.queue.ports
app.infrastructure.llm_providers.* -> app.llm.ports
app.infrastructure.embedding_providers.* -> app.embeddings.ports
app.infrastructure.vector_stores.* -> app.rag.ports
```

The root cause is not Redis-specific. It is a modeling mismatch: `app.infrastructure` is not a lower layer of the core application. It is an outer adapter ring. Infrastructure adapters depend inward on the ports they implement, and the application depends on those adapters only through the approved composition path.

A linear `Layers` contract is a good fit for the layered core, but it is a poor fit for modeling an outer adapter ring. Placing `app.infrastructure` inside the layer stack can be made mechanically valid, but it creates cognitive overhead: infrastructure is conceptually outside the core while being mechanically positioned between core and domain/capability/platform modules.

Therefore, this ADR separates the two concerns:

- the `Layers` contract governs the layered core;
- dedicated infrastructure boundary contracts govern the outer adapter ring.

## Decision

1. `app.infrastructure` is modeled as an outer adapter ring, not as a layer inside the core stack.

For Phase 2, `app.infrastructure` is the only modeled outer adapter ring for driven adapters: database, Redis, storage, queues, HTTP clients, provider SDKs, vector stores, rate limiting, idempotency, and similar runtime integrations called by the application.

Entrypoints and delivery mechanisms such as `app.main`, `app.api`, and future `app.worker` are not part of `app.infrastructure`. They are modeled separately as application edge modules. If a future entrypoint needs its own import-boundary treatment, that should be decided by a later ADR rather than folded into `app.infrastructure`.

2. `app.infrastructure` is removed from the `Layers` contract. The `Layers` contract governs only the layered core:

```text
app.main
app.api
app.core
app.auth | app.users | app.documents | app.rag | app.ai | app.ai_governance
app.llm | app.embeddings | app.prompts
app.platform
app.observability
app.shared
```

3. Infrastructure adapters may import the ports they implement from port-owning modules, including:

```text
app.platform.*
app.llm.ports
app.embeddings.ports
app.prompts.ports
app.auth.ports
app.users.ports
app.documents.ports
app.rag.ports
app.ai.ports
app.ai_governance.ports
```

They may also import `app.shared` and `app.observability`.

4. Only `app.core.wiring.*` may directly import `app.infrastructure.*`. This remains the sole approved runtime composition surface for infrastructure adapters.

5. `app.main` may reach infrastructure only transitively through the sanctioned composition path:

```text
app.main.app_factory
  -> app.core.lifespan
  -> app.core.wiring.<adapter_area>
  -> app.infrastructure.<adapter_area>
```

6. Infrastructure adapters must not import `app.main`, `app.api`, or `app.core`. They implement ports; they do not call back into the application composition layer.

7. Infrastructure adapters should not import other infrastructure adapters. Cross-adapter composition belongs in `app.core.wiring.*`.

8. The `core-wiring-only-infra` contract from ADR-0025 remains valid. It enforces that non-wiring modules do not directly import infrastructure while still allowing the sanctioned transitive path from `app.main` through `app.core.lifespan` and `app.core.wiring.*`.

9. A dedicated infrastructure boundary contract should govern imports from `app.infrastructure.*` into the core. Its intent is:

```text
app.infrastructure.* may import shared, observability, and port modules it implements.
app.infrastructure.* must not import app.main, app.api, app.core, or unrelated infrastructure adapters.
```

10. Dynamic imports, local imports, re-export shims, or `ignore_imports` entries used to hide infrastructure edges from static analysis are forbidden. Valid edges must be represented honestly in `.importlinter`.

11. Future adapter tasks must not edit `.importlinter` merely to support adapter-to-port imports. If `lint-imports` reports a violation for an adapter-to-port import after this ADR has landed, the correct response is to stop and report the contract mismatch, not to add exceptions or local workarounds.

## Consequences

### Positive

- The import model is easier to explain: there is a layered core, and infrastructure is outside it.
- The `Layers` contract remains a simple linear model of the core.
- Infrastructure adapters can implement ports without per-task `.importlinter` changes.
- The project matches the ports-and-adapters architecture more directly: adapters depend on abstract ports, while application code does not depend directly on adapters.
- Direct imports from application/domain/capability/platform/API/main code to infrastructure remain blocked.
- ADR-0023 remains intact: runtime composition still flows through `app.main`, `app.core.lifespan`, and `app.core.wiring.*`.
- ADR-0025 remains valid and complementary: the wiring-only infrastructure boundary still uses direct-import semantics.

### Neutral

- `app.infrastructure` no longer appears in the `Layers` contract. This is intentional. Infrastructure is not part of the layered core; it is an outer adapter ring governed by explicit infrastructure boundary contracts.
- The architecture now relies on named contracts rather than layer position to explain and enforce the infrastructure boundary.

### Negative

- The `Layers` contract alone no longer shows the complete application architecture. Readers must understand that infrastructure is governed separately.
- Dedicated infrastructure boundary contracts must be kept up to date when new top-level entrypoints or module groups are introduced.
- Import-linter configuration becomes slightly more explicit, but the mental model becomes simpler.

## Alternatives considered

### 1. Simply swap `app.platform` and `app.infrastructure`

This would allow platform adapter edges such as:

```text
app.infrastructure.redis.* -> app.platform.cache.ports
app.infrastructure.storage.* -> app.platform.storage.ports
app.infrastructure.queue.* -> app.platform.queue.ports
```

However, it would not allow capability/domain adapter edges such as:

```text
app.infrastructure.llm_providers.* -> app.llm.ports
app.infrastructure.embedding_providers.* -> app.embeddings.ports
app.infrastructure.vector_stores.* -> app.rag.ports
```

Rejected because it fixes only part of the adapter-to-port problem.

### 2. Place `app.infrastructure` inside the Layers contract directly below `app.core`

This would allow both mandatory directions:

```text
app.core.wiring.* -> app.infrastructure.*
app.infrastructure.* -> port-owning modules
```

However, it makes the architecture harder to understand. Infrastructure is conceptually an outer ring, but the layer stack would present it as sitting between core and domain/capability/platform modules.

Rejected because it is mechanically workable but cognitively surprising. The project should prefer a lower-complexity model that future developers and AI agents can understand quickly.

### 3. Place `app.infrastructure` at the very top of the Layers contract

This would allow infrastructure to import every port-owning layer. However, it would place `app.core` below infrastructure, making the sanctioned edge invalid:

```text
app.core.wiring.* -> app.infrastructure.*
```

That would require exceptions to allow the composition path.

Rejected because it breaks the approved runtime binding model and would reintroduce exception debt.

### 4. Remove `app.infrastructure` from the Layers contract and govern it with explicit contracts

This is the accepted option.

It keeps the layered core simple and models infrastructure as a true outer adapter ring. Infrastructure imports ports; only wiring imports infrastructure; ordinary application modules do not import infrastructure directly.

### 5. Add per-task `ignore_imports` exceptions

This would mean adding exceptions for each adapter-to-port edge as tasks land.

Rejected because it creates permanent exception debt, normalizes bypassing the contract, and forces every adapter task to relitigate the same architectural issue.

### 6. Move ports into `app.infrastructure`

This would make infrastructure imports easy, but it would invert the ports-and-adapters model. Ports belong to the layer that owns the capability or platform concern, not to the concrete adapter layer.

Rejected because it conflicts with ADR-0018.

### 7. Use dynamic imports, local imports, or re-export shims

Examples include:

```python
importlib.import_module("app.infrastructure.redis.cache")
```

or hiding an infrastructure import behind an intermediate module.

Rejected because this hides real dependency edges from static analysis and bypasses the quality gates established by ADR-0011.

## Implementation notes

The `Layers` contract should model the layered core only:

```text
app.main
app.api
app.core
app.auth | app.users | app.documents | app.rag | app.ai | app.ai_governance
app.llm | app.embeddings | app.prompts
app.platform
app.observability
app.shared
```

Infrastructure is governed separately.

The infrastructure boundary should express these rules:

```text
Only app.core.wiring.* may directly import app.infrastructure.*.

app.infrastructure.* may import:
- app.shared
- app.observability
- the port modules it implements

app.infrastructure.* must not import:
- app.main
- app.api
- app.core
- unrelated app.infrastructure adapters
```

The `core-wiring-only-infra` contract must use direct-import semantics:

```ini
allow_indirect_imports = True
```

This preserves the sanctioned transitive path:

```text
app.main
  -> app.core.lifespan
  -> app.core.wiring.*
  -> app.infrastructure.*
```

Future adapter tasks should treat the following as valid:

```text
app.infrastructure.<adapter> -> app.<owner>.ports
```

and the following as invalid:

```text
app.api.* -> app.infrastructure.*
app.domain_or_capability.* -> app.infrastructure.*
app.platform.* -> app.infrastructure.*
app.main.* -> app.infrastructure.*
app.infrastructure.<adapter> -> app.infrastructure.<other_adapter>
app.infrastructure.* -> app.core
app.infrastructure.* -> app.api
app.infrastructure.* -> app.main
```

## Five-rule summary

1. The layered core is enforced by the `Layers` contract.
2. Infrastructure is outside the layered core.
3. Infrastructure adapters may import the ports they implement.
4. Only `app.core.wiring.*` may import infrastructure adapters.
5. Adapters do not import application entrypoints, core composition code, or other adapters.

## Relationship to prior ADRs

- ADR-0011 remains the source of truth for enforcing module boundaries with `import-linter`.
- ADR-0018 remains the source of truth for the ports-and-adapters model.
- ADR-0023 remains the source of truth for composition-root ownership.
- ADR-0025 remains the source of truth for direct-import semantics on the wiring-only infrastructure boundary.
- This ADR clarifies how infrastructure must be represented in `.importlinter` so that ADR-0018 and ADR-0023 can both be enforced without exceptions or bypasses.
