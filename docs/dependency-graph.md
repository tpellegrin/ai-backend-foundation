# Module Dependency Graph

> **Superseded by** [`phase-2-revision/03-revised-dependency-graph.md`](phase-2-revision/03-revised-dependency-graph.md).
>
> This document predates the Phase 2 revision pack and is retained for historical
> reference only. It does not model `app.platform` as its own layer and its
> allowed-edge table is out of date. For the authoritative dependency graph (and
> the one mirrored by `.importlinter`), read the revised graph linked above.
> New contributors: follow the revised graph; do not add rules here.

> The dependency graph is part of the architecture. It will be enforced mechanically (see [ADR-0011](adr/0011-enforce-module-boundaries-with-import-linter.md)).

A clean dependency graph is what makes a codebase *navigable* in year three. We define it explicitly here; CI rejects PRs that violate it.

---

## 1. Layers (top imports from bottom, never the other way)

```
                    ┌────────────────────────────────────────────┐
        L5  edge    │  app.main                                  │
                    │  app.api  (v1 mount, error handlers, …)    │
                    └──────────────┬─────────────────────────────┘
                                   │ imports
                    ┌──────────────▼─────────────────────────────┐
        L4  comp.   │  app.core  (container, lifespan, di, wiring)│
                    └──────────────┬─────────────────────────────┘
                                   │
                    ┌──────────────▼─────────────────────────────┐
        L3  domain  │  app.auth  app.users  app.ai  app.rag      │
                    │  app.documents                             │
                    └──────────────┬─────────────────────────────┘
                                   │
                    ┌──────────────▼─────────────────────────────┐
        L2  cap.    │  app.llm  app.embeddings  app.prompts      │
                    └──────────────┬─────────────────────────────┘
                                   │
                    ┌──────────────▼─────────────────────────────┐
        L1  infra   │  app.infrastructure.*                      │
                    └──────────────┬─────────────────────────────┘
                                   │
                    ┌──────────────▼─────────────────────────────┐
        L0  leaves  │  app.shared    app.observability            │
                    └────────────────────────────────────────────┘
```

**Rule of thumb**: a module at level `Ln` may import from levels `< n` only. Same-level cross-imports are forbidden by default and require an ADR to introduce.

---

## 2. Allowed edges (whitelist)

| From                      | May import from                                                                                  |
| ------------------------- | ------------------------------------------------------------------------------------------------ |
| `app.shared`              | (nothing in `app.*`)                                                                             |
| `app.observability`       | `app.shared`                                                                                     |
| `app.infrastructure.*`    | `app.shared`, `app.observability`                                                                |
| `app.llm`                 | `app.shared`, `app.observability`                                                                |
| `app.embeddings`          | `app.shared`, `app.observability`                                                                |
| `app.prompts`             | `app.shared`, `app.observability`                                                                |
| `app.auth`                | `app.shared`, `app.observability`                                                                |
| `app.users`               | `app.shared`, `app.observability`, `app.auth` *(read-only domain types only)*                    |
| `app.documents`           | `app.shared`, `app.observability`, `app.embeddings` *(via port)*                                 |
| `app.ai`                  | `app.shared`, `app.observability`, `app.llm`, `app.prompts`                                      |
| `app.rag`                 | `app.shared`, `app.observability`, `app.llm`, `app.embeddings`, `app.prompts`, `app.documents`   |
| `app.core`                | everything below it (composition **library**; `app.core.wiring.*` is **the only** place adapters are wired) |
| `app.api`                 | `app.core`, `app.shared`, `app.observability`, and each domain module's `api` submodule                     |
| `app.main`                | `app.core`, `app.api` — composition **site** (`create_app()`); owns initial `Container`/`ProbeRegistry` construction (see [ADR-0023](adr/0023-composition-root-ownership.md)) |

**Reading this table**: if an edge isn't listed, it isn't allowed.

### Composition split (ADR-0023)

- **Composition site** = `app.main`. `create_app()` lives in `app/main/app_factory.py`, imports both `app.core` and `app.api`, constructs the initial `Container` (with `settings` and an empty `ProbeRegistry`), and installs it on `app.state.container` before attaching the lifespan.
- **Composition library** = `app.core`. Provides `container.py`, `lifespan.py`, `di.py`, and `wiring/*`. `app.core.lifespan` reads and mutates `app.state.container` in place; it never constructs a new `Container` or `ProbeRegistry`, and never reassigns `app.state.container`.
- **Do not** add an `app.core → app.api` edge. The Layers contract in `importlinter.toml` is not to be weakened. If a task appears to require it, the task is wrong, not the contract.
- **Sanctioned composition edge (ADR-0023, [ADR-0025](adr/0025-direct-import-semantics-for-core-wiring-only-infra.md))**: `app.main.app_factory → app.core.lifespan → app.core.wiring.<capability> → app.infrastructure.<capability>` is a first-class, statically visible transitive path. The `core-wiring-only-infra` `import-linter` contract enforces a **direct-import ban only** (see [ADR-0025](adr/0025-direct-import-semantics-for-core-wiring-only-infra.md)): only `app.core.wiring.*` may write `from app.infrastructure...`. Transitive reach from `app.main` through `app.core.wiring.*` is permitted and required. Dynamic imports (`importlib.import_module`) or re-export shims used to hide this edge from static analysis are forbidden — see `docs/implementation/rules.md` §1 and `docs/implementation/review.md` §2.

### Important asymmetries

- `app.llm`, `app.embeddings`, `app.prompts` do **not** depend on each other. They are siblings. `app.ai` and `app.rag` are the composers.
- No domain module ever imports from `app.infrastructure.*`. Adapters are injected at the composition root via Protocols defined in the consuming module's `ports.py`.
- `app.users` may use `app.auth` domain types (e.g. `UserId`, `Principal`) but **not** its persistence or services. The opposite direction is forbidden: `app.auth` knows nothing about user profiles.
- `app.documents` may use the `EmbeddingModel` port type from `app.embeddings` to type its ingest pipeline; the **adapter** is still injected.

---

## 3. Forbidden edges (explicit, common-mistake list)

- `app.<any> → app.infrastructure.*` (except `app.core`)
- `app.rag → app.ai` or `app.ai → app.rag` (siblings; orchestration belongs in a higher composer, not lateral imports)
- `app.auth → app.users` (auth must not know about user profiles)
- `app.<any>.persistence → app.<other>.persistence` (each module owns its tables; cross-table queries belong in a query module owned by the consumer or in views)
- Any module importing from `app.api` or `app.core` (only the edge layer composes; layers below it must remain composable)
- Anything importing `app.main`

---

## 4. Ports & Adapters: who owns what

| Port              | Defined in            | Consumed by                                                | Adapter location                          |
| ----------------- | --------------------- | ---------------------------------------------------------- | ----------------------------------------- |
| `ChatModel`       | `app.llm.ports`       | `app.ai`, `app.rag`, `app.llm.service`                     | `app.infrastructure.llm_providers.*`      |
| `ModelRouter`     | `app.llm.ports`       | `app.ai`, `app.rag`                                        | `app.llm.router` (default)                |
| `EmbeddingModel`  | `app.embeddings.ports`| `app.rag`, `app.documents`                                 | `app.infrastructure.embedding_providers.*`|
| `VectorStore`     | `app.rag.ports`       | `app.rag`                                                  | `app.infrastructure.vector_stores.*`      |
| `PromptRegistry`  | `app.prompts.ports`   | `app.ai`, `app.rag`                                        | `app.prompts.registry` (default)          |
| `ConversationStore`| `app.ai.ports`       | `app.ai`                                                   | `app.ai.memory.*`                         |
| `ToolRegistry`    | `app.ai.ports`        | `app.ai`                                                   | `app.ai.tools.*`                          |
| `BlobStorage`     | `app.platform.storage.ports` | `app.documents`, `app.ai`                            | `app.infrastructure.storage.*`            |
| `Cache`           | `app.platform.cache.ports`   | many                                                 | `app.infrastructure.redis.*`              |
| `TaskQueue`       | `app.platform.queue.ports`   | `app.documents`, `app.rag`, `app.ai`                 | `app.infrastructure.queue.*`              |
| `IdentityProvider`| `app.auth.ports`      | `app.auth`                                                 | `app.auth.adapters.*`                     |
| `PasswordHasher`  | `app.auth.ports`      | `app.auth`                                                 | `app.auth.adapters.argon2_hasher`         |
| `TokenSigner`     | `app.auth.ports`      | `app.auth`                                                 | `app.auth.adapters.jwt_signer`            |
| `Clock`           | `app.shared.clock`    | all                                                        | `app.shared.clock` (system, test)         |

`BlobStorage`, `Cache`, and `TaskQueue` are the rare exceptions where the port lives in `platform/` because they are cross-cutting and no single domain has stronger ownership. They are otherwise treated like any other port.

---

## 5. Test code

- A module's `tests/` may import from its own module freely and from `app.shared` / `app.observability`.
- Cross-module e2e tests live in top-level `tests/` and may import from `app.core` and from any domain module's public surface (the `__init__.py` re-exports).
- Tests **may not** import from another module's `persistence.py` or `adapters/`.

---

## 6. Mechanical enforcement

In Phase 2 we add `importlinter.toml` with contracts equivalent to this document. CI fails on violation. Example contracts:

- **Layers**: `shared`, `observability` < `infrastructure` < `llm/embeddings/prompts` < `auth/users/ai/rag/documents` < `core` < `api` < `main`.
- **Independence**: `llm`, `embeddings`, `prompts` are mutually independent.
- **Independence**: `ai` and `rag` are mutually independent.
- **Forbidden**: any module other than `core` imports from `infrastructure`.
- **Forbidden**: any module imports another module's `persistence` or `adapters`.

A new edge requires (a) updating this document and (b) updating `importlinter.toml`. Same PR.

---

## 7. ASCII module graph (current target)

```
            main
             │
             ▼
            api ──────────────────────────────┐
             │                                │
             ▼                                ▼
            core                       (per-domain api.py)
             │
   ┌─────────┼─────────┬──────────┬──────────┬──────────┐
   ▼         ▼         ▼          ▼          ▼          ▼
  auth     users    documents    ai         rag     (future: evaluations)
   │         │         │          │          │
   │         │         │          ├──────────┤
   │         │         │          ▼          ▼
   │         │         │         prompts    embeddings
   │         │         │          │          │
   │         │         └──────────┘          │
   │         │                               │
   │         │              ┌────────────────┘
   │         │              ▼
   │         │             llm
   │         │              │
   ▼         ▼              ▼
  shared   shared          shared
                                ▲
                                │
                          observability
                                ▲
                                │
                       infrastructure.* (wired only by core)
```

Read arrows as "imports". Where two arrows fan into the same node, both consumers depend on the shared node.
