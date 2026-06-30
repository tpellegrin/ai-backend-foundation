# ADR-0018: Introduce `app/platform/` for cross-cutting ports

- **Status**: Accepted
- **Date**: 2026-06-30
- **Deciders**: Architecture review

## Context

Phase 1's dependency graph forbade any module (other than `app.core`) from importing `app.infrastructure.*`. The same document, however, located the ports `BlobStorage`, `Cache`, and `TaskQueue` under `app.infrastructure.storage.ports`, `app.infrastructure.redis.ports`, and `app.infrastructure.queue.ports`. Domain modules (`documents`, `rag`, `ai`) were named as consumers of those ports. The two rules cannot be enforced simultaneously: `Protocol` definitions are normal Python objects and a `from app.infrastructure.x.ports import Y` statement is, mechanically, an import from `app.infrastructure.*`. `import-linter` would either fire on every consumer or every consumer would need a per-file ignore — which destroys the boundary entirely.

This is contradiction **C-1** in `docs/phase-2-revision/01-contradictions.md`.

## Decision

Introduce a new top-level package `app/platform/` whose **only** responsibility is to host cross-cutting **ports** (Python `Protocol`s and the small value types they need). Concrete adapter implementations remain in `app/infrastructure/*` and are wired exclusively by `app/core/wiring/*`.

```
app/platform/
├── storage/ports.py         # BlobStorage protocol
├── cache/ports.py           # Cache protocol
├── queue/ports.py           # TaskQueue protocol + Job descriptor
├── rate_limit/ports.py      # RateLimiter protocol
└── idempotency/ports.py     # IdempotencyStore protocol
```

Rules:

- `app/platform/` imports `app.shared` only. It does not import anything else.
- Any module **except** `app.platform` and `app.shared` may import `app.platform.*`.
- `app.infrastructure.*` implements the ports defined in `app.platform.*`. Adapters are imported only by `app.core.wiring.*`.
- A corresponding `import-linter` contract enforces the above (see `docs/phase-2-revision/03-revised-dependency-graph.md` §5).

## Consequences

**Positive**

- The rule "domain code does not import infrastructure" can finally be enforced mechanically.
- Adapters can be swapped (local FS → S3, in-memory Cache → Redis, no-op queue → Arq) without touching consumers.
- Ports gain a clear, dependency-free home that is easy to test and easy to read.

**Negative**

- One additional top-level package and one additional layer in the dependency graph.
- Contributors must learn the platform/infrastructure split. AGENTS.md documents it explicitly.

**Neutral**

- Adapters that are *module-specific* (e.g. `auth/adapters/argon2_hasher.py`) remain inside the consuming module. Only cross-cutting ports move to `platform/`.

## Alternatives considered

- **Whitelist `from app.infrastructure.*.ports import ...` per consumer.** Rejected: fragile, per-file ignores accumulate, and we lose mechanical enforcement.
- **Define each cross-cutting port inside its primary consumer.** Rejected: `TaskQueue` and `Cache` have no single primary consumer; putting them anywhere creates an arbitrary asymmetry.
- **Keep the rule and accept the contradiction with an "advisory" boundary.** Rejected: an unenforced boundary is wallpaper.
