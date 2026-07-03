# ADR-0024: Define LLM-owned governance gate contract

- **Status**: Accepted
- **Date**: 2026-07-03
- **Deciders**: Architecture review

## Context

Phase 2 requires every LLM provider call to be preceded by a governance check
(`ai_governance.service.check_call_allowed`) and followed by a usage record
(`ai_governance.service.record_usage`). [ADR-0019](0019-ai-governance-module.md)
established `app/ai_governance/` as a **domain-layer** module because it owns
tables, events, and an HTTP surface. The revised Phase 2 dependency graph
(`docs/phase-2-revision/03-revised-dependency-graph.md`) places domain modules
one layer above capability modules (`app.llm`, `app.embeddings`, `app.prompts`).

Task **T-1102** originally specified that `app.llm.service.LlmService` would
import `GovernanceGate` from `app.ai_governance.ports`. That import is a
lower-layer (capability) module reaching into a higher-layer (domain) module.
The `.importlinter` layered contract does not distinguish
`app.ai_governance.ports` from the rest of `app.ai_governance`, and no
`ignore_imports` entry exists — nor should one be added. As written, T-1102
would break `make check` on landing and force us either to weaken the layered
contract with a per-edge exception or to reshape the graph under time
pressure. [ADR-0018](0018-platform-ports-layer.md) already rejected per-edge
exceptions as the mechanism for a structurally similar problem (C-1: ports
co-located with adapters).

The invariant that cannot move: **`LlmService` must be the single provider-call
path and must consult governance before invoking a provider** (AGENTS.md,
ADR-0019, Phase 2 acceptance criteria).

## Decision

The governance gate Protocol needed by `LlmService` is defined **inside the
consumer capability**:

- `app/llm/ports.py` owns `GovernanceGate(Protocol)` with the two async methods
  `check_call_allowed(...)` and `record_usage(...)` that `LlmService` calls.
- The value objects it exchanges (`AllowDecision`, `BudgetExceededError`,
  `ModelNotAllowedError`) live in `app/shared/governance.py` /
  `app/shared/errors.py`. Only **pure cross-boundary contract types** belong
  there: frozen dataclasses, enums, and `AppError` subclasses with no
  governance policy, no persistence, no orchestration, and no dependencies
  on any other `app.*` module beyond `app.shared` itself. Governance domain
  logic (budget evaluation, allowlist checks, usage aggregation, audit trail)
  stays in `app.ai_governance` and never migrates into `app.shared`.
- `app.ai_governance` remains a full domain module (ADR-0019 untouched). It
  owns `BudgetPolicy`, `UsageEntry`, `UsageRepository`, `BudgetPolicyStore`,
  its persistence, its events, and its read-only HTTP API. This ADR does
  **not** authorize `app.ai_governance` to re-export a duplicate
  `GovernanceGate` Protocol; the sole Protocol is in `app.llm.ports`. If a
  second consumer of the gate ever emerges, its addition is a separate
  design decision, not a pre-approved side effect of this ADR.
- `app.ai_governance.service.GovernanceService` implements the two methods and
  therefore **structurally** satisfies `app.llm.ports.GovernanceGate`. It does
  not import from `app.llm`. There is no nominal `implements` relationship;
  the binding is made in wiring.
- `app.core.wiring.llm` constructs `LlmService` and passes the concrete
  governance service as the `governance` argument. This is the only place
  `app.llm` and `app.ai_governance` meet at import time; core wiring is
  already permitted to import from anywhere.
- Provider adapters (`app.infrastructure.llm_providers.*`) must **not** call
  governance directly. They implement `ChatModel` only.
- `app.rag` and `app.ai` must **not** bypass `LlmService` for provider calls.
  Their access to LLMs is through `app.llm.service` exclusively. This ADR
  does not grant `app.rag`, `app.ai`, or any other domain-layer module a
  new same-layer import allowance into `app.ai_governance`; any such edge
  remains governed by the existing dependency graph and must be justified
  on its own terms.

This flips the direction of the arrow. `app.llm → app.ai_governance` is
deleted from the dependency graph; `app.core.wiring.llm → app.ai_governance`
is the only remaining edge.

Task-graph consequence: **T-1102 no longer depends on T-1100 for the
Protocol type** — the Protocol is defined in T-1101 (`app.llm.ports`) using
value objects from `app.shared`. Runtime wiring of `LlmService` still
depends on the concrete `app.ai_governance` module (T-1100's domain and
persistence surface, plus the S12 governance-service task), so the wiring
task in S12 continues to require T-1100 as a prerequisite; that dependency
does not propagate back to T-1102.

## Consequences

**Positive**

- The layered `import-linter` contract stays intact with **zero
  `ignore_imports`**. Mechanical boundary enforcement is preserved.
- `app.llm` truly depends only on things below it. It is a self-contained
  capability that can be reasoned about, tested, and even lifted into a
  separate distribution without dragging `ai_governance` along.
- Port ownership becomes consistent with the rest of the graph: the primary
  consumer of a Protocol defines it (`ChatModel`, `VectorStore`,
  `PromptRegistry`, `IdentityProvider`, `PasswordHasher`, `TokenSigner` all
  follow this pattern in the revised dependency graph).
- ADR-0019 is fully preserved. `ai_governance` remains a domain module with
  its own persistence, events, and API.
- ADR-0018 is fully preserved. `app.platform` is not diluted with a
  non-infrastructure port.
- The invariant "governance runs before every provider call" is enforced at
  a single choke point (`LlmService`) that both types the port and calls it.

**Negative**

- Contributors must understand structural typing (`Protocol`) at the wiring
  boundary. AGENTS.md, this ADR, and the wiring code document it explicitly.
- Cross-boundary value types (`AllowDecision`, `BudgetExceededError`,
  `ModelNotAllowedError`) live in `app.shared` rather than in the module
  whose vocabulary they belong to. This is an accepted trade-off: keeping
  them pure and dependency-free is what makes the inversion possible.

**Neutral**

- If, in the future, a second capability-layer module needs to consult
  governance, the Protocol may be promoted to
  `app.platform.governance.ports`. That promotion is a mechanical rename
  and does not invalidate this decision.

## Alternatives considered

- **Keep the capability→domain import and add `ignore_imports` in
  `.importlinter`.** Rejected: establishes a precedent for per-edge
  exceptions that ADR-0018 already rejected under C-1. An unenforced
  layered contract is wallpaper.
- **Reclassify `ai_governance` as a capability.** Rejected: contradicts
  ADR-0019; governance owns tables, events, and an HTTP surface — those are
  domain concerns and capabilities are not permitted to grow them.
- **Move `GovernanceGate` into `app.platform.governance.ports`.** Rejected
  for Phase 2: ADR-0018 scopes `platform` to cross-cutting
  **infrastructure-shaped** ports (Cache, Queue, BlobStorage, RateLimiter,
  IdempotencyStore) whose adapters live in `app.infrastructure.*`.
  `GovernanceGate`'s "adapter" is a domain service, not an infrastructure
  adapter. Reachable later if a second capability-layer consumer appears.
- **Split `ai_governance` into a lower `contracts` package and an upper
  domain package.** Rejected: fragments the public surface of a single
  conceptual module across two `__init__.py` files for a single Protocol.
- **Event-bus indirection with a governance veto.** Rejected: we have
  deliberately not built an app-wide event bus (AGENTS.md anti-patterns),
  and veto semantics on events make the "governance ran before provider"
  invariant hard to prove.

## Compliance

- `.importlinter`: **no changes**. All existing contracts stay green.
- `docs/phase-2-revision/03-revised-dependency-graph.md`: the
  `app.llm → app.ai_governance.ports` allowance is removed; the ports table
  gains a `GovernanceGate` row owned by `app.llm.ports`.
- `docs/implementation/tasks/T-1100.md`, `T-1101.md`, `T-1102.md`: patched
  per this ADR (Protocol moves from `app.ai_governance.ports` to
  `app.llm.ports`; cross-boundary value objects move to
  `app.shared.governance` / `app.shared.errors`; T-1102 no longer depends
  on T-1100, while the S12 wiring task retains its T-1100 dependency).
- `docs/implementation/roadmap.md`: T-1100 description updated to reflect
  the new ownership.
