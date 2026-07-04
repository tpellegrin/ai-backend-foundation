# ADR-0025: Direct-import semantics for the wiring-only-infrastructure contract

- **Status**: Accepted
- **Date**: 2026-07-04
- **Deciders**: Architecture review (T-701 blocker review)

## Context

`AGENTS.md §7` and [`docs/implementation/rules.md`](../implementation/rules.md) §3 rule 4 state that
`from app.infrastructure.* import ...` is forbidden everywhere except inside
`app/core/wiring/`. This is a **direct-import invariant**: it constrains what
a source file may *write*, not what a module may transitively *reach*.

[ADR-0023](0023-composition-root-ownership.md) designates `app.main` as the
composition **site**. The sanctioned composition flow is:

```
app.main.app_factory
    → app.core.lifespan
    → app.core.wiring.<capability>
    → app.infrastructure.<capability>
```

When T-701 attempted to materialize the first real edge on this flow, the
`.importlinter` contract `core-wiring-only-infra` failed. The contract listed
`app.main.**` and `app.api.**` in `source_modules` without setting
`allow_indirect_imports`. Import Linter's default for `forbidden` contracts
detects transitive paths, so the sanctioned ADR-0023 flow was reported as a
violation.

The initial T-701 implementation attempted to bypass the failure by
introducing `importlib.import_module("app.core.wiring.db")` inside
`app/core/lifespan.py`. Review rejected this on the grounds that hiding a
real edge from static analysis:

- violates [ADR-0011](0011-enforce-module-boundaries-with-import-linter.md)'s
  "no quiet bypass" clause,
- defeats `mypy --strict`,
- normalises a workaround pattern that would repeat across T-702/T-708,
  T-703, T-1212, T-1402, T-1503, worker wiring, and every provider adapter.

The mismatch was diagnosed as a contract that encodes the right invariant
with the wrong Import Linter knob: the direct-vs-transitive dimension it
currently spans is wrong; the transitive dimension it should not encode is
already covered by the `Layers` contract.

## Decision

1. The `core-wiring-only-infra` forbidden contract in `.importlinter` is
   clarified by setting `allow_indirect_imports = True`. It enforces the
   **direct-import ban only**: no source module listed in the contract may
   write a direct `from app.infrastructure...` import. Transitive paths that
   flow through `app.core.wiring.*` are permitted — and, for `app.main`, are
   required by ADR-0023.

2. The transitive dimension of the architecture is enforced — as it already
   was — by the `Layers` contract, which forbids any lower layer from
   importing any higher layer (and therefore from importing
   `app.core.wiring.*` and, through it, `app.infrastructure.*`).

3. **Dynamic imports of wiring modules from `lifespan.py` or any other
   file, and any re-export shim intended to hide a composition edge, are
   explicitly forbidden.** Static, top-of-file imports of
   `app.core.wiring.<x>` from `app.core.lifespan` are the only sanctioned
   form of the composition edge. Reviewers must reject:

   - `importlib.import_module("app.core.wiring.<x>")` in any file;
   - function-local imports of `app.core.wiring.*` used to route around
     Import Linter;
   - re-export shims (a second file that re-exports from
     `app.core.wiring.*`) intended to shorten or hide the composition edge.

4. `.importlinter` changes required by this decision:
   - Add exactly one line to `[importlinter:contract:core-wiring-only-infra]`:
     `allow_indirect_imports = True`.
   - Do not modify `source_modules` or `forbidden_modules` on this contract.
   - Do not add any `ignore_imports` entries.
   - Do not modify any other contract.

5. Task-spec updates required by this decision:
   - **T-701** owns the `.importlinter` flip in the same PR that materializes
     the first `app.core.wiring.* → app.infrastructure.*` edge. Its
     `Allowed files` gains `.importlinter`. The stale sentence "No
     `.importlinter` change is required" is removed and replaced with a
     reference to this ADR.
   - **T-708** references this ADR and explicitly forbids dynamic-import
     workarounds and re-export shims. `.importlinter` is **not** in T-708's
     `Allowed files` (the contract change lands with T-701).
   - **T-702, T-703, T-704** carry a one-line reference to this ADR; no
     other change.
   - Future wiring tasks (T-1212, T-1402, T-1503, worker wiring, provider
     adapters) inherit the same rule via the S07/S12/S14/S15 task template.

## Consequences

**Positive**:

- `AGENTS.md §7`, `docs/implementation/rules.md` §3 rule 4, and
  `.importlinter` now say the same thing.
- The sanctioned ADR-0023 composition flow passes `lint-imports` without
  weakening or ignoring any edge.
- Every future wiring task uses the same static-import pattern; no
  per-task `.importlinter` exception, no dynamic-import workaround, no
  exception debt.

**Negative**:

- The forbidden contract no longer catches hypothetical transitive
  reaches from `app.api`/`app.main` into `app.infrastructure` through
  intermediate modules other than `app.core.wiring.*`. Acceptable
  because:
  1. Such reaches still require a direct `from app.infrastructure...`
     somewhere, which is still banned by this same contract.
  2. `Layers` independently forbids the upward-facing edges needed to
     construct any such path from below `app.core`.

**Neutral**:

- Precedent already exists in the same file: the
  `no-cross-persistence` contract uses `allow_indirect_imports = True`
  for the same class of reason.

## Alternatives considered

- **`ignore_imports` per composition edge** — permanent exception debt;
  every new wiring task edits `.importlinter`; rejected.
- **Removing `app.main.**` from `source_modules`** — asymmetric
  weakening; silently permits a direct `from app.infrastructure...` in
  `app/main/*.py`; rejected.
- **Restructuring imports so `app.main` does not transitively reach
  infrastructure** — implementations reduce to dynamic-import in
  disguise, function-local imports (still edges to Import Linter, and
  correctly so), or a re-export shim (a second composition site, already
  rejected by ADR-0023 Alternatives); rejected.
- **Splitting wiring into low-level vs runtime packages** — does not
  solve the problem without also applying this ADR; rejected as pure
  overhead.

## Relationship to prior ADRs

- Refines [ADR-0011](0011-enforce-module-boundaries-with-import-linter.md)
  by making the direct-vs-transitive semantics of the
  `core-wiring-only-infra` contract explicit. No decision reversal.
- Reaffirms [ADR-0023](0023-composition-root-ownership.md): the
  composition flow from `app.main` down through `app.core.wiring.*` to
  `app.infrastructure.*` is a first-class, statically visible edge.

## Follow-ups

- Amend T-701 and T-708 task specs (in this same docs-only PR).
- Update `docs/dependency-graph.md`,
  `docs/phase-2-revision/03-revised-dependency-graph.md`,
  `docs/implementation/rules.md` §1, and `docs/implementation/review.md`
  (in this same docs-only PR).
- On T-701 re-open, verify `uv run lint-imports` passes with all
  contracts kept (no exclusions, no `--config` flag, no `ignore_imports`
  entries added).
