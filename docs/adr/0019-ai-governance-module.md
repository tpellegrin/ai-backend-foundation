# ADR-0019: Introduce `app/ai_governance/` for cost, quota, and policy enforcement

- **Status**: Accepted
- **Date**: 2026-06-30
- **Deciders**: Architecture review

## Context

The original architecture required every LLM call to **record** provider, model, tokens, latency, cost, prompt id and version. That is observation. Nothing in the module tree owned the **enforcement** of token budgets, per-tenant cost caps, model allowlists/denylists, or provider fallback policies. Uncontrolled LLM spend is the single most predictable failure mode of AI products in production: one runaway loop or one misconfigured prompt is enough to cause a financial incident overnight. Discovering this *after* go-live and retrofitting the enforcement point across `llm`, `ai`, and `rag` is expensive; adding the interface up front is cheap.

## Decision

Create a new domain module `app/ai_governance/` that owns:

- **Domain types**: `BudgetPolicy` (per-tenant daily/monthly USD + tokens), `ModelAllowlist`, `UsageEntry`, `AllowDecision`.
- **Ports**: `UsageRepository`, `BudgetPolicyStore`.
- **Service** (`service.py`):
    - `check_call_allowed(*, tenant_id, model, est_tokens) -> AllowDecision` — returns `Allow`, `Soft` (with downgrade suggestion), or `Deny` (with reason).
    - `record_usage(*, observation)` — persists `UsageEntry` and emits `AIUsageAuditEvent`.
    - `pick_fallback(model) -> Model | None` — provider/model fallback policy.
- **Persistence**: tables `usage_entries`, `budget_policies`, `model_allowlists`.
- **API (Phase 2, read-only)**: `GET /api/v1/governance/budgets`, `GET /api/v1/governance/usage`.
- **Events**: `AIUsageAuditEvent` emitted for every recorded usage.

`app.llm.service` consults `check_call_allowed` **before** invoking any provider and calls `record_usage` after every call (success or error). Other modules consume only `app.ai_governance.ports` (interface types); the service implementation is wired by `app/core/wiring/governance.py`.

Phase 2 ships the minimum policy: hard-deny when the monthly budget is exceeded; soft-warn at 80% (response header `X-Budget-Warning`). Per-user budgets, soft-degradation to cheaper models, and SIEM sinks are Phase 3.

## Consequences

**Positive**

- Cost is enforceable, not only observable.
- The enforcement point is **one** place that every LLM call traverses. Adding a new policy is local.
- Audit events for AI usage are first-class artifacts.

**Negative**

- One extra module to learn and maintain.
- Every LLM call now has a pre-flight DB/cache touch. We mitigate via Redis-cached counters (`app.platform.cache`) and a short TTL.

**Neutral**

- The Phase 2 policy is intentionally minimal. The interface is the deliverable.

## Alternatives considered

- **Put cost checks inside `app.llm.service`.** Rejected: `llm` is a capability module; budget policy is a domain concern with its own persistence and audit. Mixing them violates separation of concerns and forces `llm` to grow tables.
- **Implement only logging now and enforcement later.** Rejected: this is exactly the trap that produces the predictable failure mode. Recording-only is theater unless paired with enforcement.
- **A library, not a module.** Rejected: it owns persistence and emits events; it deserves a module.
