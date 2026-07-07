# Revised Dependency Graph (Phase 2 Target)

> Supersedes `docs/dependency-graph.md` for Phase 2 onward.
> Adds the `platform` layer (ports) and the `ai_governance` module.
> Models `app.infrastructure` as an **outer adapter ring** for driven adapters (ADR-0026), not as a lower layer.
> Every edge listed here corresponds to an `importlinter` contract.

---

## 1. Layered core plus outer adapter ring (ADR-0026)

The architecture is a **layered core** wrapped by an **outer driven-adapter ring**
(`app.infrastructure.*`). Adapters import inward to the ports they
implement; the composition root (`app.core.wiring.*`) is the only module
that imports adapters back into the runtime. No other module imports
`app.infrastructure.*` directly.

For Phase 2, `app.infrastructure` is the only modeled outer adapter ring for
driven adapters: database, Redis, storage, queues, HTTP clients, LLM providers,
embedding providers, vector stores, rate limiting, idempotency, and similar
runtime integrations. Entrypoints such as `app.main`, `app.api`, and future
`app.worker` remain modeled as application edge layers unless a later ADR
changes that.

```text
                    ┌────────────────────────────────────────────────────────────────┐
                    │  OUTER DRIVEN-ADAPTER RING                                     │
                    │  app.infrastructure.*   (redis, storage, queue, http, db,      │
                    │                          llm_providers, embedding_providers,   │
                    │                          vector_stores, rate_limit,            │
                    │                          idempotency, ...)                     │
                    │                                                                │
                    │   Adapters import inward to the ports they implement:          │
                    │   app.infrastructure.<adapter> → app.<owner>.ports             │
                    │                                                                │
                    │        ▲                                                       │
                    │        │ imported ONLY by app.core.wiring.*                    │
                    │        │ (ADR-0023, ADR-0025, ADR-0026)                        │
                    │        │                                                       │
                    │        │        LAYERED CORE & ENTRYPOINTS                     │
                    │   ┌────┴─────────────────────────────────────────────────┐     │
                    │   │  L6  edge     app.main (Entrypoint)                  │     │
                    │   │               app.api  (Delivery edge)               │     │
                    │   ├──────────────────────────────────────────────────────┤     │
                    │   │  L5  comp.    app.core  (wiring/*, lifespan, ...)    │     │
                    │   ├──────────────────────────────────────────────────────┤     │
                    │   │  L4  domain   app.auth  app.users  app.documents     │     │
                    │   │               app.rag  app.ai  app.ai_governance     │     │
                    │   ├──────────────────────────────────────────────────────┤     │
                    │   │  L3  cap.     app.llm  app.embeddings  app.prompts   │     │
                    │   ├──────────────────────────────────────────────────────┤     │
                    │   │  L2  platform app.platform.*   (PORTS & MAPPING)     │     │
                    │   ├──────────────────────────────────────────────────────┤     │
                    │   │  L0  leaves   app.shared    app.observability        │     │
                    │   └──────────────────────────────────────────────────────┘     │
                    │                                                                │
                    │   Valid adapter direction:                                     │
                    │   app.infrastructure.* ───── imports ports ─────► L2..L4       │
                    └────────────────────────────────────────────────────────────────┘
```

**Direction rules** (ADR-0026):

- **Inside the layered core**: a module at layer `Ln` may import from lower layers. Same-layer imports are allowed only when explicitly listed in the whitelisted-edge table or permitted by a dedicated contract. Otherwise, sibling modules should remain independent.
- **Adapter ring → core (inward)**: `app.infrastructure.*` may import from any port-owning layer it implements — `app.platform.*` (L2), any capability (L3: `app.llm`, `app.embeddings`, `app.prompts`), any domain (L4: `app.auth`, `app.users`, `app.documents`, `app.rag`, `app.ai`, `app.ai_governance`). It may also import from the platform mapping foundation (`app.platform.db`) and from `app.shared` and `app.observability`.
- **Core → adapter ring (outward)**: forbidden **except** from `app.core.wiring.*`. `app.main` reaches infrastructure **only transitively** via `app.core.lifespan → app.core.wiring.<x> → app.infrastructure.<x>` (ADR-0023). This direct-import ban is enforced by two forbidden contracts (`core-wiring-only-infra` and `infrastructure-only-via-core-wiring`) using direct-import semantics (ADR-0025 and ADR-0026).
- **Cross-adapter**: adapters should not import other adapters. `app.core.wiring.*` composes them.

**Key shift vs. the original graph**:

- `app.infrastructure` is an **outer ring for driven adapters**, not a lower layer. It imports inward to ports; only `app.core.wiring.*` imports it back into the runtime.
- `platform` (ports) sits below domain/capability consumers *inside the core*, but is imported *from outside* by adapters in the infrastructure ring.
- Domain and capability code imports `app.platform.*` and, where applicable, its own module’s `.ports` for cross-cutting protocols.
- Adapter-to-port imports (`adapter → any port it implements`) do not require any per-task `.importlinter` change after ADR-0026.

---

## 2. Whitelisted edges

| From | May import from |
| --- | --- |
| `app.shared` | (nothing in `app.*`) |
| `app.observability` | `app.shared` |
| `app.infrastructure.*` | `app.shared`, `app.observability`, and any port module it implements: `app.platform.*`, `app.llm.ports`, `app.embeddings.ports`, `app.prompts.ports`, `app.rag.ports`, `app.ai.ports`, `app.ai_governance.ports`, `app.auth.ports`, `app.users.ports`, `app.documents.ports` (adapter → port; ADR-0026) |
| `app.platform.*` | `app.shared` |
| `app.llm` | `app.shared`, `app.observability`, `app.platform.*` *(owns `GovernanceGate` in `app.llm.ports`; does **not** import `app.ai_governance` — see ADR-0024)* |
| `app.embeddings` | `app.shared`, `app.observability`, `app.platform.*` |
| `app.prompts` | `app.shared`, `app.observability`, `app.platform.storage` *(optional, for DB-backed overrides)* |
| `app.auth` | `app.shared`, `app.observability`, `app.platform.cache` *(token/blacklist)* |
| `app.users` | `app.shared`, `app.observability`, `app.auth` *(read-only domain types only)* |
| `app.ai_governance` | `app.shared`, `app.observability`, `app.platform.cache` *(quota counters)* |
| `app.documents` | `app.shared`, `app.observability`, `app.platform.storage`, `app.platform.queue`, `app.embeddings` *(via port)* |
| `app.ai` | `app.shared`, `app.observability`, `app.platform.*`, `app.llm`, `app.prompts`, `app.ai_governance.ports` |
| `app.rag` | `app.shared`, `app.observability`, `app.platform.*`, `app.llm`, `app.embeddings`, `app.prompts`, `app.documents`, `app.ai_governance.ports` |
| `app.core` | everything below it — and **only** `app.core.wiring.*` imports `app.infrastructure.*` |
| `app.api` | `app.core`, `app.shared`, `app.observability`, each domain module’s `api` submodule |
| `app.main` | `app.core`, `app.api` |

If an edge is not listed, it is forbidden.

### Important asymmetries

- `app.llm`, `app.embeddings`, `app.prompts` do not depend on each other.
- `app.ai` and `app.rag` do not depend on each other.
- `app.auth` does not depend on `app.users` (only the reverse, and only on domain types).
- `app.documents` depends on `app.embeddings` *port* and on `app.platform.queue` (for the ingestion job), never on Arq directly.
- `app.rag` depends on `app.documents` for `(document_id, chunk_id)` provenance types only (read-only domain types; no persistence).
- `app.llm` **does not** import `app.ai_governance`. `LlmService` types its governance dependency against `app.llm.ports.GovernanceGate` (see ADR-0024); the concrete implementation is `app.ai_governance.service.GovernanceService`, wired in `app.core.wiring.llm`. Domain-layer consumers of governance (for example, `app.ai`, `app.rag`) may import `app.ai_governance.ports` directly because that edge is explicitly listed above.

### Sanctioned composition edge (ADR-0023, ADR-0025)

The composition flow

```text
app.main.app_factory
    → app.core.lifespan
    → app.core.wiring.<capability>
    → app.infrastructure.<capability>
```

is a **first-class, statically visible transitive path**. The
`core-wiring-only-infra` `import-linter` contract enforces a
**direct-import ban only** (see
[ADR-0025](../adr/0025-direct-import-semantics-for-core-wiring-only-infra.md)):
only `app.core.wiring.*` may write `from app.infrastructure... import ...`.
Transitive reach from `app.main` through `app.core.wiring.*` is permitted
and required by ADR-0023.

The transitive dimension of the architecture is enforced by the `Layers`
contract, which forbids lower layers from importing `app.core.wiring.*`
and, through it, `app.infrastructure.*`.

Dynamic imports (`importlib.import_module("app.core.wiring.<x>")`),
function-local imports of wiring from `lifespan.py`, or re-export shims
used to hide the composition edge from static analysis are forbidden. See
`docs/implementation/rules.md` §1 and `docs/implementation/review.md` §2.

---

## 3. Forbidden edges (explicit list)

- `app.<any> → app.infrastructure.*` — except `app.core.wiring.*`.
- `app.<any> → app.main` — main is the entrypoint, never an import target.
- `app.platform.* → app.infrastructure.*` — ports never know about adapters.
- `app.platform.* → app.llm | app.embeddings | app.prompts | app.<domain>` — platform is below everything else in the layered core.
- `app.rag ↔ app.ai` — siblings; orchestration belongs above them, not lateral.
- `app.auth → app.users` — auth must not know about user profiles.
- `app.<module>.persistence → app.<other>.persistence` — each module owns its tables.
- `app.<module>.<*> → app.<other>.persistence` — never reach into another module’s tables.
- `app.<module>.<*> → app.<other>.adapters` — never reach into another module’s adapters.
- `app.infrastructure.<adapter> → app.infrastructure.<other_adapter>` — adapters should not compose each other directly; composition belongs in `app.core.wiring.*`.

---

## 4. Ports & Adapters: who owns what (revised)

| Port | Defined in | Consumed by | Adapter location |
| --- | --- | --- | --- |
| `ChatModel` | `app.llm.ports` | `app.ai`, `app.rag`, `app.llm.service` | `app.infrastructure.llm_providers.*` |
| `GovernanceGate` | `app.llm.ports` | `app.llm.service` | `app.ai_governance.service` (structural; wired in `app.core.wiring.llm` — ADR-0024) |
| `ModelRouter` | `app.llm.ports` | `app.ai`, `app.rag` | `app.llm.router` (default) |
| `EmbeddingModel` | `app.embeddings.ports` | `app.rag`, `app.documents` | `app.infrastructure.embedding_providers.*` |
| `VectorStore` | `app.rag.ports` | `app.rag` | `app.infrastructure.vector_stores.*` |
| `PromptRegistry` | `app.prompts.ports` | `app.ai`, `app.rag` | `app.prompts.registry` (default) |
| `ConversationStore` | `app.ai.ports` | `app.ai` | `app.ai.memory.*` |
| `ToolRegistry` | `app.ai.ports` | `app.ai` | `app.ai.tools.*` |
| `BlobStorage` | **`app.platform.storage.ports`** | `app.documents`, `app.ai` | `app.infrastructure.storage.*` |
| `Cache` | **`app.platform.cache.ports`** | many | `app.infrastructure.redis.*` |
| `TaskQueue` | **`app.platform.queue.ports`** | `app.documents`, `app.rag`, `app.ai` | `app.infrastructure.queue.arq` |
| `RateLimiter` | **`app.platform.rate_limit.ports`** | `app.api` | `app.infrastructure.rate_limit.redis` |
| `IdempotencyStore` | **`app.platform.idempotency.ports`** | `app.api` | `app.infrastructure.idempotency.redis` |
| `UsageRepository` | `app.ai_governance.ports` | `app.ai_governance.service` | `app.ai_governance.persistence` |
| `BudgetPolicyStore` | `app.ai_governance.ports` | `app.ai_governance.service` | `app.ai_governance.persistence` |
| `IdentityProvider` | `app.auth.ports` | `app.auth` | `app.auth.adapters.*` |
| `PasswordHasher` | `app.auth.ports` | `app.auth` | `app.auth.adapters.argon2_hasher` |
| `TokenSigner` | `app.auth.ports` | `app.auth` | `app.auth.adapters.jwt_signer` |
| `Clock` | `app.shared.clock` | all | `app.shared.clock` (system, test) |

The cells in **bold** are platform ports: cross-cutting abstractions that infrastructure adapters implement.

---

## 5. `importlinter.toml` contracts (Phase 2)

```toml
[importlinter]
root_packages = ["app"]

# Contract 1: Layered core and entrypoints (governs the pure business-logic
# hierarchy and application edge; app.infrastructure is modeled as an
# outer driven-adapter ring and is governed by explicit boundary
# contracts 5a/5b/5c below).
[[importlinter.contracts]]
name = "Layers"
type = "layers"
layers = [
    "app.main",
    "app.api",
    "app.core",
    "app.auth | app.users | app.documents | app.rag | app.ai | app.ai_governance",
    "app.llm | app.embeddings | app.prompts",
    "app.platform",
    "app.observability",
    "app.shared",
]

# Contract 2: Capability siblings are independent
[[importlinter.contracts]]
name = "Capabilities are independent"
type = "independence"
modules = ["app.llm", "app.embeddings", "app.prompts"]

# Contract 3: ai and rag are independent
[[importlinter.contracts]]
name = "ai and rag are independent"
type = "independence"
modules = ["app.ai", "app.rag"]

# Contract 4: auth must not depend on users
[[importlinter.contracts]]
name = "auth does not import users"
type = "forbidden"
source_modules = ["app.auth"]
forbidden_modules = ["app.users"]

# Contract 5a: Only app.core.wiring may import infrastructure directly
# (ADR-0025 direct-import semantics — the sanctioned transitive path
# `app.main -> app.core.lifespan -> app.core.wiring.<x> -> app.infrastructure.<x>`
# remains allowed via `allow_indirect_imports = true`).
[[importlinter.contracts]]
name = "Only core.wiring imports infrastructure"
type = "forbidden"
source_modules = [
    "app.shared", "app.observability", "app.platform",
    "app.llm", "app.embeddings", "app.prompts",
    "app.auth", "app.users", "app.documents", "app.rag", "app.ai", "app.ai_governance",
    "app.api", "app.main",
    "app.core.lifespan", "app.core.container", "app.core.config", "app.core.di", "app.core.tests"
]
forbidden_modules = ["app.infrastructure"]
allow_indirect_imports = true

# Contract 5b: Infrastructure driven-adapter ring boundary (ADR-0026).
# Ensures that adapters do not call back into application entrypoints
# or core.
[[importlinter.contracts]]
name = "Infrastructure adapter-ring boundary"
type = "forbidden"
source_modules = ["app.infrastructure"]
forbidden_modules = ["app.main", "app.api", "app.core"]
allow_indirect_imports = true

# Contract 5c: Infrastructure adapters are independent (ADR-0026).
[[importlinter.contracts]]
name = "Infrastructure adapters are independent"
type = "independence"
modules = [
    "app.infrastructure.db",
    "app.infrastructure.redis",
    "app.infrastructure.storage",
    "app.infrastructure.queue",
    "app.infrastructure.llm_providers",
    "app.infrastructure.embedding_providers",
    "app.infrastructure.vector_stores",
]

# Contract 6: Platform never imports infrastructure or anything above it
[[importlinter.contracts]]
name = "Platform is below everything except shared"
type = "forbidden"
source_modules = ["app.platform"]
forbidden_modules = [
    "app.infrastructure",
    "app.llm", "app.embeddings", "app.prompts",
    "app.auth", "app.users", "app.documents", "app.rag", "app.ai", "app.ai_governance",
    "app.api", "app.core", "app.main",
]

# Contract 7: No cross-module persistence/adapters imports
[[importlinter.contracts]]
name = "No cross-module persistence imports"
type = "forbidden"
source_modules = ["app"]
forbidden_modules = [
    "app.auth.persistence", "app.users.persistence",
    "app.documents.persistence", "app.rag.persistence",
    "app.ai.persistence", "app.ai_governance.persistence",
    "app.auth.adapters", "app.ai.tools", "app.ai.memory",
]
allow_indirect_imports = true
ignore_imports = [
    "app.auth.* -> app.auth.persistence",
    "app.users.* -> app.users.persistence",
    "app.documents.* -> app.documents.persistence",
    "app.rag.* -> app.rag.persistence",
    "app.ai.* -> app.ai.persistence",
    "app.ai_governance.* -> app.ai_governance.persistence",
    "app.auth.* -> app.auth.adapters",
    "app.ai.* -> app.ai.tools",
    "app.ai.* -> app.ai.memory",
    "app.core.wiring.* -> *",
    "alembic.* -> *",
]
```

> The exact TOML schema is the import-linter v2 syntax; the contract names and intents are the source of truth.

---

## 6. ASCII module graph (revised target)

Read arrows as **imports**.

```text
                            main
                              │
                              ▼
                             api ─────────────────────────────────────────────┐
                              │                                               │
                              ▼                                               ▼
                            core ── imports only from wiring ──► infrastructure.*
                              │                              ▲          │
                              │                              │          │
   ┌──────────┬──────────────┬┴───────────┬────────────┬─────┴────────┐ │
   ▼          ▼              ▼            ▼            ▼              ▼ │
  auth      users        documents       rag           ai       ai_governance
   │          │              │            │            │              ▲
   │          │              │            │            │              │
   │          │              ├────────────┼────────────┼──────────────┘
   │          │              ▼            ▼            ▼
   │          │           prompts     embeddings      llm
   │          │              │            │            │
   │          │              └────────────┼────────────┘
   │          │                           │
   │          │                           ▼
   │          │                       platform/* (ports & mapping)
   │          │                           ▲
   │          │                           │
   │          │              infrastructure.* imports ports it implements
   ▼          ▼
 shared    shared

observability ───────────────────────────► shared
infrastructure.* ────────────────────────► observability
infrastructure.* ────────────────────────► shared
```

The key directions are:

```text
core.wiring.* -> infrastructure.*
infrastructure.* -> platform/capability/domain ports
domain/capability/api/main -> never directly to infrastructure.*
```

Capability and domain modules speak to the outside world through ports; adapters are injected by `app.core.wiring.*`.

---

## 7. Practical examples

Allowed:

```text
app.infrastructure.redis.cache -> app.platform.cache.ports
app.infrastructure.storage.local -> app.platform.storage.ports
app.infrastructure.llm_providers.openai -> app.llm.ports
app.infrastructure.embedding_providers.openai -> app.embeddings.ports
app.infrastructure.vector_stores.pgvector -> app.rag.ports
app.core.wiring.cache -> app.infrastructure.redis.cache
```

Forbidden:

```text
app.api.routes -> app.infrastructure.redis.cache
app.rag.service -> app.infrastructure.vector_stores.pgvector
app.platform.cache.ports -> app.infrastructure.redis.cache
app.main.app_factory -> app.infrastructure.db.engine
app.infrastructure.redis.cache -> app.infrastructure.storage.local
```
