# Revised Dependency Graph (Phase 2 Target)

> Supersedes `docs/dependency-graph.md` for Phase 2 onward.
> Adds the `platform` layer (ports) and the `ai_governance` module.
> Every edge listed here corresponds to an `importlinter` contract.

---

## 1. Layers (top imports from bottom, never the other way)

```
                 ┌────────────────────────────────────────────────────────┐
   L6  edge      │  app.main                                              │
                 │  app.api  (v1 mount, error handlers, idempotency, ...) │
                 └──────────────┬─────────────────────────────────────────┘
                                │
                 ┌──────────────▼─────────────────────────────────────────┐
   L5  comp.     │  app.core  (app_factory, container, di, wiring/*)      │
                 └──────────────┬─────────────────────────────────────────┘
                                │
                 ┌──────────────▼─────────────────────────────────────────┐
   L4  domain    │  app.auth  app.users  app.documents  app.rag  app.ai   │
                 │  app.ai_governance                                     │
                 └──────────────┬─────────────────────────────────────────┘
                                │
                 ┌──────────────▼─────────────────────────────────────────┐
   L3  cap.      │  app.llm  app.embeddings  app.prompts                  │
                 └──────────────┬─────────────────────────────────────────┘
                                │
                 ┌──────────────▼─────────────────────────────────────────┐
   L2  platform  │  app.platform.*    (PORTS ONLY)                        │
                 └──────────────┬─────────────────────────────────────────┘
                                │
                 ┌──────────────▼─────────────────────────────────────────┐
   L1  infra     │  app.infrastructure.*   (ADAPTERS ONLY)                │
                 │  (imported only by app.core.wiring.*)                  │
                 └──────────────┬─────────────────────────────────────────┘
                                │
                 ┌──────────────▼─────────────────────────────────────────┐
   L0  leaves    │  app.shared    app.observability                       │
                 └────────────────────────────────────────────────────────┘
```

**Layer rule**: a module at layer `Ln` may import from `< n` only. Same-layer imports are forbidden unless explicitly whitelisted below.

**Key shift vs. the original graph**:

- `platform` (ports) sits *above* `infrastructure` (adapters) and *below* every capability and domain module.
- Domain code now imports `app.platform.*` for cross-cutting ports.
- `infrastructure` is imported only by `app.core.wiring.*`.

---

## 2. Whitelisted edges

| From                       | May import from                                                                                       |
| -------------------------- | ----------------------------------------------------------------------------------------------------- |
| `app.shared`               | (nothing in `app.*`)                                                                                  |
| `app.observability`        | `app.shared`                                                                                          |
| `app.infrastructure.*`     | `app.shared`, `app.observability`, `app.platform.*` (to *implement* the ports)                        |
| `app.platform.*`           | `app.shared`                                                                                          |
| `app.llm`                  | `app.shared`, `app.observability`, `app.platform.*` *(owns `GovernanceGate` in `app.llm.ports`; does **not** import `app.ai_governance` — see ADR-0024)* |
| `app.embeddings`           | `app.shared`, `app.observability`, `app.platform.*`                                                   |
| `app.prompts`              | `app.shared`, `app.observability`, `app.platform.storage` *(optional, for DB-backed overrides)*       |
| `app.auth`                 | `app.shared`, `app.observability`, `app.platform.cache` *(token/blacklist)*                            |
| `app.users`                | `app.shared`, `app.observability`, `app.auth` *(read-only domain types only)*                          |
| `app.ai_governance`        | `app.shared`, `app.observability`, `app.platform.cache` *(quota counters)*                            |
| `app.documents`            | `app.shared`, `app.observability`, `app.platform.storage`, `app.platform.queue`, `app.embeddings` *(via port)* |
| `app.ai`                   | `app.shared`, `app.observability`, `app.platform.*`, `app.llm`, `app.prompts`, `app.ai_governance.ports` |
| `app.rag`                  | `app.shared`, `app.observability`, `app.platform.*`, `app.llm`, `app.embeddings`, `app.prompts`, `app.documents`, `app.ai_governance.ports` |
| `app.core`                 | everything below it — and **only** `app.core.wiring.*` imports `app.infrastructure.*`                  |
| `app.api`                  | `app.core`, `app.shared`, `app.observability`, each domain module's `api` submodule                    |
| `app.main`                 | `app.core`, `app.api`                                                                                  |

If an edge is not listed, it is forbidden.

### Important asymmetries

- `app.llm`, `app.embeddings`, `app.prompts` do not depend on each other.
- `app.ai` and `app.rag` do not depend on each other.
- `app.auth` does not depend on `app.users` (only the reverse, and only on domain types).
- `app.documents` depends on `app.embeddings` *port* and on `app.platform.queue` (for the ingestion job), never on Arq directly.
- `app.rag` depends on `app.documents` for `(document_id, chunk_id)` provenance types only (read-only domain types; no persistence).
- `app.llm` **does not** import `app.ai_governance`. `LlmService` types its governance dependency against `app.llm.ports.GovernanceGate` (see ADR-0024); the concrete implementation is `app.ai_governance.service.GovernanceService`, wired in `app.core.wiring.llm`. Domain-layer consumers of governance (e.g. `app.ai`, `app.rag`) may import `app.ai_governance.ports` directly — same-layer L4, already listed above.

---

## 3. Forbidden edges (explicit list)

- `app.<any> → app.infrastructure.*` — except `app.core.wiring.*`.
- `app.<any> → app.main` — main is the entrypoint, never an import target.
- `app.platform.* → app.infrastructure.*` — ports never know about adapters.
- `app.platform.* → app.llm | app.embeddings | app.prompts | app.<domain>` — platform is below everything else.
- `app.rag ↔ app.ai` — siblings; orchestration belongs above them, not lateral.
- `app.auth → app.users` — auth must not know about user profiles.
- `app.<module>.persistence → app.<other>.persistence` — each module owns its tables.
- `app.<module>.<*> → app.<other>.persistence` — never reach into another module's tables.
- `app.<module>.<*> → app.<other>.adapters` — never reach into another module's adapters.

---

## 4. Ports & Adapters: who owns what (revised)

| Port               | Defined in                          | Consumed by                                          | Adapter location                          |
| ------------------ | ----------------------------------- | ---------------------------------------------------- | ----------------------------------------- |
| `ChatModel`        | `app.llm.ports`                     | `app.ai`, `app.rag`, `app.llm.service`               | `app.infrastructure.llm_providers.*`      |
| `GovernanceGate`   | `app.llm.ports`                     | `app.llm.service`                                    | `app.ai_governance.service` (structural; wired in `app.core.wiring.llm` — ADR-0024) |
| `ModelRouter`      | `app.llm.ports`                     | `app.ai`, `app.rag`                                  | `app.llm.router` (default)                |
| `EmbeddingModel`   | `app.embeddings.ports`              | `app.rag`, `app.documents`                           | `app.infrastructure.embedding_providers.*`|
| `VectorStore`      | `app.rag.ports`                     | `app.rag`                                            | `app.infrastructure.vector_stores.*`      |
| `PromptRegistry`   | `app.prompts.ports`                 | `app.ai`, `app.rag`                                  | `app.prompts.registry` (default)          |
| `ConversationStore`| `app.ai.ports`                      | `app.ai`                                             | `app.ai.memory.*`                         |
| `ToolRegistry`     | `app.ai.ports`                      | `app.ai`                                             | `app.ai.tools.*`                          |
| `BlobStorage`      | **`app.platform.storage.ports`**    | `app.documents`, `app.ai`                            | `app.infrastructure.storage.*`            |
| `Cache`            | **`app.platform.cache.ports`**      | many                                                 | `app.infrastructure.redis.*`              |
| `TaskQueue`        | **`app.platform.queue.ports`**      | `app.documents`, `app.rag`, `app.ai`                 | `app.infrastructure.queue.arq`            |
| `RateLimiter`      | **`app.platform.rate_limit.ports`** | `app.api`                                            | `app.infrastructure.rate_limit.redis`     |
| `IdempotencyStore` | **`app.platform.idempotency.ports`**| `app.api`                                            | `app.infrastructure.idempotency.redis`    |
| `UsageRepository`  | `app.ai_governance.ports`           | `app.ai_governance.service`                          | `app.ai_governance.persistence`           |
| `BudgetPolicyStore`| `app.ai_governance.ports`           | `app.ai_governance.service`                          | `app.ai_governance.persistence`           |
| `IdentityProvider` | `app.auth.ports`                    | `app.auth`                                           | `app.auth.adapters.*`                     |
| `PasswordHasher`   | `app.auth.ports`                    | `app.auth`                                           | `app.auth.adapters.argon2_hasher`         |
| `TokenSigner`      | `app.auth.ports`                    | `app.auth`                                           | `app.auth.adapters.jwt_signer`            |
| `Clock`            | `app.shared.clock`                  | all                                                  | `app.shared.clock` (system, test)         |

The cells in **bold** are the ones that moved from `app.infrastructure.*` to `app.platform.*` — the fix for C-1.

---

## 5. `importlinter.toml` contracts (Phase 2)

```toml
[importlinter]
root_packages = ["app"]

# Contract 1: Layered architecture
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
    "app.infrastructure",
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

# Contract 5: Only app.core.wiring may import infrastructure
[[importlinter.contracts]]
name = "Only core.wiring imports infrastructure"
type = "forbidden"
source_modules = [
    "app.shared", "app.observability", "app.platform",
    "app.llm", "app.embeddings", "app.prompts",
    "app.auth", "app.users", "app.documents", "app.rag", "app.ai", "app.ai_governance",
    "app.api",
]
forbidden_modules = ["app.infrastructure"]

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

```
                            main
                              │
                              ▼
                             api ─────────────────────────────────────────────┐
                              │                                               │
                              ▼                                               ▼
                            core ◄── (only place that imports infrastructure) │
                              │                                       (per-module api.py)
   ┌──────────┬──────────────┬┴───────────┬────────────┬──────────────┐
   ▼          ▼              ▼            ▼            ▼              ▼
  auth      users        documents       rag           ai       ai_governance
   │          │              │            │            │              │
   │          │              │            │            │              │
   │          │              ├────────────┼────────────┼──────────────┤
   │          │              ▼            ▼            ▼              ▼
   │          │           prompts     embeddings      llm        (uses ports only)
   │          │              │            │            │
   │          │              └────────────┼────────────┘
   │          │                           │
   │          │                           ▼
   │          │                       platform/* (ports)
   │          │                           │
   ▼          ▼                           ▼
 shared    shared                  infrastructure.* (adapters, wired only by core)
                                           │
                                           ▼
                                    observability
                                           │
                                           ▼
                                        shared
```

Read arrows as "imports". Capability and domain modules speak to the outside world through `platform.*` ports; adapters are injected by `core.wiring.*`.
