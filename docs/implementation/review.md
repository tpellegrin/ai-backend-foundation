# Review — Phase 2 of `ai-backend-foundation`

> Authoritative review reference for the reviewer model and human reviewers.
> Use this file alongside the per-task `Review checklist` block in each [`./tasks/T-XXX.md`](./tasks/) and the global rules in [`./rules.md`](./rules.md).
>
> Companion files:
> - Plan overview, dependency map, task index: [`../../IMPLEMENTATION_PLAN.md`](../../IMPLEMENTATION_PLAN.md)
> - Implementation rules + stop signals + lower-complexity model instructions: [`./rules.md`](./rules.md)
> - Per-task specs: [`./tasks/`](./tasks/)

---

## 1. Instructions for the reviewer model

You are a strict reviewer. Approve only when every item below is true.

1. **AGENTS.md compliance.** Re-check every rule in [`./rules.md`](./rules.md) §2 (Global rules) and `AGENTS.md` §2/§7 against the diff. Any violation → reject.
2. **ADR compliance.** Re-check ADRs 0018 (platform), 0019 (ai_governance), 0020 (golden path), 0021 (rename), 0022 (Arq). Any deviation → reject.
3. **Imports.** Manually verify (and confirm `lint-imports` confirms):
   - No `app.infrastructure.*` import outside `app.core.wiring.*`.
   - No SDK import outside its adapter file.
   - No cross-module persistence/adapters reach-in.
4. **Layers.** Domain code does not import FastAPI, SQLAlchemy, httpx, or any SDK.
5. **Tests.** Every change is covered by a test of the right kind (unit / api / integration / contract). No xfail, skip, or weakening. Coverage ≥ 80%.
6. **Types.** `mypy --strict` clean on `app/`. Every `# type: ignore` carries a rule code and a one-line reason.
7. **Observability.** All logs via structlog. Every external HTTP via `app/infrastructure/http/`. Every LLM call records an `LLMCallObservation` with all 11 fields and opens an OTel span.
8. **Errors.** All errors are `AppError` subclasses and serialize as RFC 9457 Problem Details at the edge. No stack traces, SQL, secrets, or provider raw bodies in error bodies.
9. **Scope discipline.** No new top-level folders, no new dependencies beyond the task's allow-list, no out-of-scope features. **Reject broad, clever, or architecture-changing changes.** No implementation from future tasks was introduced simply to satisfy tooling. If unsure whether something is in scope: reject. Apply the allowed-files policy in `rules.md` §4 literally — see §4 of this document for its reviewer projection.
10. **Documentation.** New edges in the dependency graph or new ports require `importlinter.toml` and dep-graph doc updates in the same PR.
11. **ADR for architectural deltas.** Any change that affects a public interface, dependency, or rule requires an ADR.

When approving, the reviewer model must explicitly confirm: *"Verified against AGENTS.md, ADRs 0018–0022, importlinter contracts, and the review checklist of `docs/implementation/review.md`."*

---

## 2. Final review checklist (used by human and reviewer model on every PR)

- Architecture
  - [ ] No new top-level folder under `app/` outside the established set.
  - [ ] No `app.infrastructure.*` import outside `app.core.wiring.*`.
  - [ ] No `app.platform.*` → `app.infrastructure.*` import.
  - [ ] No SDK import outside its dedicated adapter file.
  - [ ] No `os.environ` outside `app/core/config/`.
  - [ ] No cross-module persistence/adapters imports.
  - [ ] No implementation from future tasks was introduced simply to satisfy tooling.
- Types & layering
  - [ ] `domain.py` is pure; no FastAPI / SQLAlchemy / httpx / SDK imports.
  - [ ] `service.py` returns domain types only.
  - [ ] `api.py` returns Pydantic response models only; never ORM objects.
  - [ ] `persistence.py` mapped classes never leave the module.
- LLM
  - [ ] No inline prompt strings.
  - [ ] Every LLM call goes through `app.llm.service`.
  - [ ] Governance gate consulted **before** the provider call.
  - [ ] `LLMCallObservation` has all 11 fields populated.
- Errors
  - [ ] No `except Exception: pass` or bare `except`.
  - [ ] All raised errors subclass `AppError`.
  - [ ] No raw provider responses or stack traces in error bodies.
  - [ ] Every error response is `application/problem+json`.
  - [ ] Error handlers must not silently encourage `HTTPException` from below `api.py` (only `AppError`, `RequestValidationError`, and the fallback `Exception` are mapped to Problem Details).
- Observability
  - [ ] All logs via `structlog` (no `print`, no ad-hoc `logging.getLogger`).
  - [ ] Every response carries `X-Request-ID`.
  - [ ] External HTTP via `app/infrastructure/http/` only.
- Tests
  - [ ] Unit + API + integration tests added per task table.
  - [ ] Contract tests parameterized for new adapters.
  - [ ] No skipped/xfailed tests left in tree.
  - [ ] Coverage ≥ 80% on `app/`.
- Migrations
  - [ ] Single Alembic head.
  - [ ] `alembic upgrade head` and `downgrade base` both succeed.
- Imports
  - [ ] `lint-imports` exit 0.
  - [ ] No new contract `ignore_imports` entries beyond the contracts established in T-107.

---

## 3. Architecture compliance checklist

Use this checklist as a final gate after the per-PR checklist (§2). A PR may not merge if any line below is false.

- Layering (top→bottom): `main` → `api` → `core` → domain (`auth|users|documents|rag|ai|ai_governance`) → capability (`llm|embeddings|prompts`) → `platform` → `infrastructure` → leaves (`shared`, `observability`). A module at layer `N` imports only from layers `< N`.
- **Only `app.core.wiring.*` may import from `app.infrastructure.*`.** Nowhere else. Ever.
- Domain code imports **ports** from `app.platform.*`, never adapters.
- `app.llm`, `app.embeddings`, `app.prompts` are siblings and **do not** import each other.
- `app.ai` and `app.rag` are siblings and **do not** import each other.
- `app.auth` does **not** import `app.users`.
- `app.users` may import `app.auth` read-only domain types only (not `auth.persistence`, not `auth.adapters`).
- A module's public surface is exactly what its `__init__.py` re-exports — no other entry points.
- No module imports another module's `persistence.py` or `adapters/`.
- Infrastructure adapters never leak into domain code.
- Business logic does not depend on FastAPI, SQLAlchemy, provider SDKs, or HTTP concepts.
- SQLAlchemy ORM classes never cross the persistence boundary.
- Pydantic models live at the API edge (`api.py`) and for validation-heavy domain value objects only. **Never** mix ORM / API / domain in one class.
- Every external call is observable.
- Every LLM call records `LLMCallObservation` with: provider, model, prompt_id, prompt_version, tokens_in, tokens_out, latency_ms, cost_usd, status, request_id, tenant_id (11 fields).
- Every LLM call consults `app.ai_governance.service.check_call_allowed(...)` **before** invoking the provider.
- Prompts are versioned artifacts in `app/prompts/library/`. No inline prompt strings in business logic.
- RAG answers include citations. No exceptions.
- New cross-module edges are reflected in `importlinter.toml` **and** `docs/dependency-graph.md` in the **same PR**.

---

## 4. Allowed-files policy (reviewer projection of `rules.md` §4)

Reviewers must judge scope against the following, in this exact order:

1. **Literal `Allowed files` list.** Every file in the diff must be either literally listed there or covered by bullets 2–3 below.
2. **Task-local test files required by `Tests required`.** A test file at its canonical location (`app/<module>/tests/test_<name>.py`, `tests/api/test_<name>.py`, or `tests/integration/test_<name>.py`) is in scope whenever `Tests required` in the same task calls for it, whether `Allowed files` uses the shorthand `tests`, names the file explicitly, or omits it. **Do not flag such tests as scope violations.** If the required test lives in a different task ("see T-XXX"), it does **not** belong to the current diff — flag it as a scope violation there. Reviewers must also **reject** any new test file whose basename duplicates another test module already in the repository — see `rules.md` §4 for the unique-basename policy.
3. **`app/<module>/__init__.py` re-exports of a symbol introduced by the current task.** Any other change to an `__init__.py` (side-effect imports, reordering, reintroducing unused re-exports, touching an unrelated module's `__init__.py`) is a scope violation.

Everything else — helpers, shared fixtures, `conftest.py`, migrations, `.env.example` keys, docs, additional config keys — is out of scope unless the task lists the file by name. If the diff needs such a file to succeed, the correct verdict is **FAIL**: the task is under-scoped and must be revised, not silently patched.

**Reviewer patch authority reminder.** Reviewer patches under `docs/ai/review-task.md` are still bounded by the current task's `Allowed files` **and** the three bullets above; they do not extend scope. A reviewer must not add a support file to close a minor finding.

**Current-codebase review.** Ground every judgment in the actual repository state at the time of the diff. Do not reject on the basis of a future task's expected outcome, and do not accept a change that anticipates a future task by pulling files in early.

---

## 5. Final golden-path acceptance test (summary)

The acceptance bar for closing Phase 2 is **mechanically** the union of:

1. `make check` returns 0 on a clean checkout.
2. `lint-imports` reports zero violations.
3. `tests/integration/test_golden_path.py` passes (T-1701) using the **fake** LLM provider in CI.
4. `tests/integration/test_observation_fields.py` proves all 11 `LLMCallObservation` fields are present (T-1702).
5. `tests/integration/test_trace_continuity.py` proves a continuous trace across `rag.ask → embeddings.embed → vector_store.search → llm.chat` (T-1703).
6. `tests/integration/test_governance.py` proves `LLM_MONTHLY_BUDGET_USD=0` yields RFC 9457 `409 budget-exceeded` with zero provider calls (T-1206 + T-1603).
7. Auth refresh-reuse test (T-908) proves family revocation and audit emit.
8. Every error path in API tests returns Problem Details and `X-Request-ID`.
9. Manual smoke against `make up` with a real OpenAI key reproduces the golden-path against the real provider (operator-run, optional but recommended before tag).
