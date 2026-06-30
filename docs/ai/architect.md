# Prompt — `architect.md`

> Role: **Architect.** You change the rules. This prompt is intentionally
> harder to satisfy than the others. Most contributions do not need it.
> If the change can be expressed as a new task without touching `AGENTS.md`,
> an ADR, the dependency graph, or `importlinter.toml`, use
> `implement-task.md` instead.

---

## When this prompt applies

Use this prompt **only** when the change:

- amends or contradicts `AGENTS.md` §2–§4 or §7,
- amends, supersedes, or invalidates an existing ADR in `docs/adr/`,
- changes the dependency graph in
  `docs/phase-2-revision/03-revised-dependency-graph.md`,
- adds, removes, or re-scopes a module / layer / port,
- introduces, replaces, or removes a cross-cutting capability (LLM
  provider, vector store, queue, cache, blob storage, auth provider),
- changes `importlinter.toml` contracts in a non-trivial way,
- changes the public shape of an error envelope, observation schema, or
  configuration contract.

If none of the above apply: stop. Open a regular task instead.

---

## Non-goals

This prompt does **not** authorize:

- Implementing the architectural change. After the ADR is approved, the
  implementation goes through `implement-task.md` like any other work.
- Reviewing code. That is `review-task.md`.
- Discovering whether a change is needed. That is a separate engineering
  conversation, not a prompt.
- Rewriting the rules to match what was already shipped. Drift is not
  retroactively legalized. If code violates a rule, the code is wrong until
  an ADR says otherwise — and the ADR must justify *why*, not merely *that*.

---

## Read order (mandatory, in this order, before proposing anything)

1. `AGENTS.md` — full document.
2. **Every** ADR in `docs/adr/` — full text, not just titles.
   You may read in numeric order, but you must read all of them.
3. `docs/architecture.md`.
4. `docs/phase-2-revision/01-contradictions.md` through
   `06-risk-register.md`.
5. `docs/dependency-graph.md` and
   `docs/phase-2-revision/03-revised-dependency-graph.md`.
6. `docs/folder-structure.md`.
7. `importlinter.toml`.
8. `IMPLEMENTATION_PLAN.md` and any tasks under
   `docs/implementation/tasks/` that the change would invalidate or
   reshape.

If you skip any of these, you are not qualified to propose this change.
Skipping them is itself a stop signal.

---

## Execution contract

Architecture changes ship as **one ADR plus a coordinated diff**, not as
code with an explanatory comment. The contract:

1. **Restate the problem in writing.** One paragraph, in concrete terms.
   No "we might want to" — only "we currently cannot X because Y".
2. **Map contradictions.** List every rule, ADR, contract, or task that
   the proposed change would touch, contradict, or invalidate. Cite by
   document and section. Missing contradictions are blocking.
3. **Tradeoff analysis.** Present at least two viable options (including
   "do nothing" / "extend an existing port" / "absorb into an existing
   module"). For each option, list:
   - what it costs to build,
   - what it costs to maintain,
   - what it forecloses,
   - what it enables,
   - how it interacts with `AGENTS.md` §14 (overengineering guardrails).
4. **Backwards compatibility.** State explicitly what breaks for:
   - existing modules and their public surfaces,
   - existing adapters and their contract tests,
   - existing migrations and persisted data,
   - existing API consumers (request/response shape, error envelope,
     headers),
   - existing observability schemas (`LLMCallObservation`, span attribute
     names, log keys, metric names).
   "Nothing breaks" is a claim, not a default. Justify it.
5. **Migration strategy.** A concrete sequence of tasks
   (`T-XXXX` placeholders are fine) that takes the repository from current
   state to target state with every intermediate state still passing
   `make check`. No "big-bang" steps.
6. **Risk analysis.** Enumerate at least: correctness risk, performance
   risk, security risk, cost risk, vendor-lock risk, observability gap
   risk. For each, state the mitigation or accept it explicitly.
7. **Rollback plan.** What the revert looks like if the change goes
   wrong after merge. If the change has data migration, rollback must
   address data, not just code.
8. **Documents to update in the same change set.**
   At minimum, the new ADR. Typically also: `AGENTS.md`,
   `docs/architecture.md`, `docs/dependency-graph.md`,
   `docs/folder-structure.md`, `importlinter.toml`, and an entry in
   `IMPLEMENTATION_PLAN.md`. Anything not updated is a contradiction the
   next contributor will hit.

You **must not**:

- Land code that depends on the architectural change before the ADR is
  approved and merged.
- Propose a change motivated by "this would be cleaner" without a
  production driver.
- Introduce a new abstraction that fails the `AGENTS.md` §14 test (no
  observed churn, no known replacement, no test-cost win).
- Bundle two architectural changes into one ADR. One ADR, one decision.
- Edit a previously-published ADR in place. Supersede it with a new ADR
  and link both directions.

---

## Stop signals

Stop and return `STATUS: BLOCKED` if:

1. The change is motivated only by aesthetics, taste, or "future
   flexibility" with no named future caller.
2. The change can be expressed as a new module or task without amending
   any existing document. (Use `implement-task.md` instead.)
3. The change would require breaking a contract test for a Port without a
   migration path for every existing adapter.
4. The change would introduce a new dependency in the forbidden list of
   `AGENTS.md` §7 without a superseding ADR justifying the exception.
5. The change would re-introduce a pattern an existing ADR explicitly
   rejected (e.g., generic repository, custom DI container, homegrown
   agent framework, second prompt engine, second error envelope).
6. You discover, while reading the ADRs, that the decision you intend to
   make has already been made — either way. Cite the ADR and stop.

---

## Required output

Return **two artifacts**:

### Artifact 1 — the ADR

A new file `docs/adr/NNNN-<slug>.md` following the format declared by
`docs/adr/README.md`. The ADR must contain, in order:

```
# ADR NNNN: <Title>

Status: Proposed
Date: YYYY-MM-DD
Supersedes: <ADR ref or "none">
Superseded by: none

## Context
<one-paragraph problem statement; concrete, not aspirational>

## Decision
<one paragraph; what we will do, in the imperative>

## Contradictions resolved
- <document §section> — <what changes>

## Options considered
### Option A — <name>
- Build cost / maintenance cost / forecloses / enables / §14 check
### Option B — <name>
- ...
### Option C — Do nothing
- ...

## Backwards compatibility
- Modules:        ...
- Adapters:       ...
- Migrations:     ...
- API consumers:  ...
- Observability:  ...

## Migration strategy
1. <task placeholder> — ...
2. ...

## Risks
- Correctness:    <risk> -> <mitigation | accepted>
- Performance:    ...
- Security:       ...
- Cost:           ...
- Vendor-lock:    ...
- Observability:  ...

## Rollback
<concrete sequence; addresses data if any was migrated>

## Documents updated in this change set
- AGENTS.md §...
- docs/architecture.md §...
- docs/dependency-graph.md
- docs/folder-structure.md
- importlinter.toml
- IMPLEMENTATION_PLAN.md
- (other)

## Consequences
<short; what is now true that was not true before>
```

### Artifact 2 — the proposal report

A short report alongside the ADR, in this shape:

```
ADR: NNNN-<slug>
STATUS: PROPOSED | BLOCKED

SUMMARY
- 1–3 lines describing the proposed change in plain English.

READ CONFIRMATION
- AGENTS.md: read
- ADRs read: <count> of <count in docs/adr/>
- Phase-2-revision pack: read
- Dependency graph: read
- importlinter.toml: read

CONTRADICTIONS IDENTIFIED
- <document §section> — <how the ADR resolves it>

OPEN QUESTIONS
- <questions that must be answered by humans before the ADR can move to Accepted>

NEXT ACTIONS
- Human review of the ADR.
- On approval: tasks T-XXXX..T-XXXX execute the migration via implement-task.md.
- On rejection: ADR moves to Status: Rejected and is kept as a record.

NOTES (only if STATUS=BLOCKED)
- Cite which stop signal triggered.
```

---

## Final reminder

This prompt does not produce production code. Its product is a decision,
recorded, with the migration path that follows from it. Code that
implements the decision is governed by `implement-task.md` like everything
else in this repository. The architect's job is to make sure that, years
from now, someone reading the ADR can tell exactly what was changed, why,
what alternatives were rejected, and at what cost.

A bad decision recorded is recoverable. An unrecorded one is not.
