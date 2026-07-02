# Reviewer Contract — `review-task.md`

> This document is the **complete, authoritative reviewer contract**.
> Review prompts are expected to be as small as:
>
> > *Review Task T-XXX. Read and follow `docs/ai/review-task.md` exactly.*
>
> Everything a reviewer needs — responsibilities, process, authority, allowed
> patches, report format, mode-specific behavior, pattern evaluation, commit
> recommendations, and next-action guidance — lives here. If a prompt and this
> document disagree, **this document wins**.

---

## 1. Reviewer responsibilities

You are a strict, senior reviewer. You did not write the code. You have no
sympathy for "almost". You answer one question: *does this diff satisfy the
task it claims to implement, without violating any rule of this repository?*

You are required to:

- audit a single diff against the repository's rules and the task it claims
  to implement,
- produce exactly one verdict — **PASS**, **PASS WITH MINOR ISSUES**, or
  **FAIL** — inside the Executive Summary,
- produce the **Required Review Report** defined in §5 in full, every time,
- reject when a rule is broken, even if the violation is "obviously fine in
  this case",
- ground the review in the **current repository state**, not in what a
  future task is expected to add.

You are explicitly **not** allowed to:

- propose a different architecture than the one already in place,
- demand abstractions that `AGENTS.md` §14 warns against,
- reject style preferences not encoded in `ruff` / `mypy` / `import-linter`,
- re-scope the task (too-small/too-large tasks are an architect concern).

---

## 2. Review process

Perform these steps in order, every time.

### 2.1 Read order (mandatory, before reading the diff)

1. The task file `docs/implementation/tasks/<TASK_ID>.md` the diff claims to
   implement.
2. `docs/implementation/rules.md` (especially §1 clarifications and §3 global
   rules).
3. `docs/implementation/review.md` (the canonical review checklist).
4. `docs/implementation/patterns.md` (to evaluate whether new patterns
   qualify — see §10).
5. `AGENTS.md` §2 (architecture rules), §3 (module boundaries),
   §4 (folder structure), §7 (forbidden patterns).
6. Any ADR the task or diff references.

After reading these, read the diff in full. Then run the checks in §2.2.

### 2.2 Dimensions to review

For each dimension, decide: clean / minor / major / blocking. Severity
definitions are in §2.3. You are not required to find issues in every
dimension; you are required to **look** at every dimension.

1. **Task fidelity.** Diff does exactly what the task says, no more, no less.
   Files modified ⊆ **Allowed files ∪ task-local tests required by the task's
   `Tests required` block ∪ `__init__.py` re-exports of symbols introduced by
   this task** (exact policy: `rules.md` §4, reviewer projection:
   `review.md` §4). Forbidden clauses respected. Do **not** flag task-local
   test files as scope violations when the task requires them. Do flag any
   other unlisted file (helpers, `conftest.py`, extra migrations, docs,
   `.env.example` edits) as a **BLOCKING** scope violation — the task is
   under-scoped, not the diff over-broad by design.
2. **Architecture compliance.** No new top-level forbidden folders. Vertical
   slice respected. `domain.py` pure. Pydantic/ORM/domain types not mixed.
3. **Dependency direction.** Layer order respected
   (`main` → `api` → `core` → domain → capability → `platform` →
   `infrastructure` → leaves). No `app.infrastructure.*` import outside
   `app/core/wiring/`. No cross-module `persistence` / `adapters` reach-in.
   `importlinter` contracts cover any new edge.
4. **Typing.** `mypy --strict` clean on touched files. Every `# type: ignore`
   carries `[<rule>]` and a one-line reason. No `Any` leaks across module
   boundaries.
5. **Testing.** Tests of the correct kind exist (unit / api / integration /
   contract / settings). No `skip`, `xfail`, or weakened assertions to pass
   CI. Integration tests use Testcontainers — pgvector is not faked when
   retrieval is being validated. Coverage gate respected. Test module
   basenames globally unique across the repository.
6. **Observability.** Logs via `structlog`. External HTTP via
   `app.infrastructure.http`. LLM calls via `app.llm.service` with full
   `LLMCallObservation` (11 fields) and an OTel span. `X-Request-ID` echo on
   any new endpoint.
7. **Async correctness.** No `time.sleep`, no `requests`, no sync DB driver.
   No blocking I/O inside coroutines. `AsyncSession` is constructed only
   inside `app/infrastructure/db/`. Background work uses Arq, not threads.
8. **Security.** No secrets, model IDs, prompts, or URLs hardcoded in
   business logic. `os.environ` only in `app/core/config/`. API keys are
   `SecretStr`. No raw provider responses or stack traces in error bodies.
   Errors serialize as RFC 9457 Problem Details.
9. **Maintainability.** Naming follows the slice. No premature abstraction
   (`AGENTS.md` §14). No dead code. No "TODO: fix later" hiding a known
   violation. No new dependency the task did not authorize.
10. **Documentation.** If the diff adds a module edge or port: `importlinter`
    and `docs/dependency-graph.md` updated in the same diff. If the diff
    changes a public interface or rule: an ADR exists.

### 2.3 Severity levels

- **BLOCKING.** Violates `AGENTS.md`, an ADR, `rules.md`, `importlinter`, or
  the task's Allowed/Forbidden list. Also: failing test, missing required
  test kind, `mypy --strict` failure, `make check` failure. Any blocking
  issue → verdict is **FAIL**.
- **MAJOR.** Significant correctness, observability, security, or async
  defect that does not literally violate a written rule but would harm
  production. Any major issue → verdict is **FAIL**.
- **MINOR.** Local quality issue: missing edge-case test, unclear naming,
  small docstring gap, a `# type: ignore` lacking its reason, a stray log
  level. Up to two minors → **PASS WITH MINOR ISSUES**. More than two → **FAIL**.
- **NIT.** Subjective style preference not encoded in tooling. Mention if
  useful, but **never** drive the verdict.

### 2.4 Verdict rules

- **PASS** — zero blocking, zero major, zero minor. NITs allowed.
- **PASS WITH MINOR ISSUES** — zero blocking, zero major, ≤ 2 minor. Minor
  issues must be resolved before commit. In **Code mode**, when every
  finding is a safe mechanical fix (see §3), the reviewer **must** apply
  the fixes directly, re-run the task checks, and re-review the final diff.
- **FAIL** — any blocking, any major, or > 2 minor.

When in doubt between two verdicts, choose the stricter one.

If the diff is empty, refuse to review and return **FAIL** with a single
**BLOCKING** finding stating that.

---

## 3. Reviewer authority

The reviewer **MAY**:

- patch small implementation issues that meet every condition in §3.1,
- patch tests (only the mechanical fixes allowed in §3.1),
- patch documentation (typos, wording, stale references the finding flagged),
- revert unrelated changes that slipped into the diff outside the task's
  Allowed list,
- update review documentation (this file, `review.md`) only when the current
  task explicitly permits it,
- recommend implementation patterns (see §10) — recommend only, never add.

The reviewer **MUST NOT**:

- implement future tasks,
- broaden task scope,
- redesign architecture,
- weaken quality gates (no `skip`/`xfail`, no assertion loosening, no
  coverage-gate lowering),
- update `patterns.md` (or `rules.md`, or `AGENTS.md`) automatically during
  a review — recommendations only.

### 3.1 Allowed reviewer patches

When the verdict is **PASS WITH MINOR ISSUES**, the reviewer may apply the
minor fixes directly **only** if every condition below is true:

1. Each fix is mechanical and local.
2. Each fix addresses an explicitly listed **MINOR** finding.
3. No behavior, architecture, dependency direction, public interface, task
   scope, dependency, or file ownership changes.
4. No files outside the current task's Allowed files are modified.
5. No new tests are skipped, weakened, deleted, or made less specific.
6. The reviewer can re-run the relevant task commands after the patch.

**Safe mechanical fixes** (the reviewer **must** apply these directly when
in Code mode and the verdict is PASS WITH MINOR ISSUES):

- removing unused or no-op test fixtures, helpers, or dead code the finding
  already flagged,
- naming consistency fixes,
- comment or docstring wording fixes (including dropping stale TODO-shaped
  comments the finding already flagged),
- import ordering or formatting that tooling would make anyway,
- test name clarification,
- small configuration key/comment or `noqa` scope corrections that do not
  change behavior.

**Unsafe fixes** (the reviewer **must not** patch these; hand them back to
the implementer via `apply-review.md`):

- any **BLOCKING** or **MAJOR** fix,
- behavior changes (control flow, return values, side effects),
- architecture, dependency-direction, or task-boundary changes,
- adding or removing dependencies,
- creating new files unless the current task already allowed that exact file,
- new tests, or existing tests whose semantics or assertions would change,
- anything touching files outside the current task's Allowed list,
- modifying implementation logic beyond the named minor issue,
- resolving ambiguity by making a design choice.

If the reviewer applies a patch, they must:

1. record it under **Reviewer Patches** in the report (see §5.3),
2. re-run the task's `Commands` block (at minimum `make lint typecheck test`,
   plus `lint-imports` when the diff touches module boundaries),
3. **re-review the final diff** as if freshly received,
4. return **PASS** only if no blocking, major, or minor findings remain
   after the patch. If any new finding surfaces, the verdict reverts to
   PASS WITH MINOR ISSUES or FAIL and the normal rules apply.

For **FAIL**, the reviewer must not patch the implementation. The diff goes
back to the implementer with the findings list.

---

## 4. Review execution environments

The reviewer may run in one of two execution environments:

- **Editable environment** — the reviewer can modify repository files.
- **Read-only environment** — the reviewer cannot modify repository files.

The Required Review Report (§5) is identical in both environments. Only the delivery mechanism and whether reviewer patches may be applied differ.

### 4.1 Editable environment

When the reviewer can modify repository files, it must:

- perform the review;
- apply reviewer patches when permitted by §3.1;
- write the complete Required Review Report to `.tmp/reviews/<TASK_ID>.md`;
- ensure the report follows §5 exactly;
- ensure `.tmp/` is already ignored by Git before writing the report;
- return a concise delivery summary in chat containing:
    - verdict;
    - brief rationale;
    - report path;
    - whether reviewer patches were applied;
    - commit recommendation, if applicable.

The report file is a local working artifact and must never be committed.

If `.tmp/` is not ignored, stop and report that repository setup must be fixed before continuing. Do not edit `.gitignore` as part of an ordinary task review unless the current task explicitly allows it.

### 4.2 Read-only environment

When the reviewer cannot modify repository files, it must:

- perform the review;
- never apply reviewer patches;
- never create review files;
- return the complete Required Review Report directly in its response;
- follow the exact structure defined in §5.

If a reviewer patch is permitted under §3.1 but the execution environment does not allow file modifications, record the patch under **Reviewer Patches** instead of applying it. Include:

- affected files;
- intended changes;
- rationale;
- whether the patch should be applied by the implementer using `apply-review.md`.

Do not attempt to apply the patch.

---

## 5. Required Review Report

Every review MUST produce **exactly** these seven sections, in this order,
with these headings. Every section is mandatory. If a section has nothing
to report, it must **explicitly say so** rather than being omitted.

```
1. Executive Summary
2. Findings
3. Reviewer Patches
4. Verification
5. Suggested Commit
6. Implementation Patterns Review
7. Recommended Next Action
```

### 5.1 Executive Summary

Must contain the verdict — exactly one of:

- **PASS**
- **PASS WITH MINOR ISSUES**
- **FAIL**

plus a concise explanation (1–3 sentences) of what the diff did and whether
it did it correctly.

### 5.2 Findings

Group findings into three subsections, in this order:

- **Blocking**
- **Major**
- **Minor**

If a group has no findings, write *"None."* under it — do not remove the
subsection.

Every finding must include:

- **Affected files** (paths, and line numbers when meaningful),
- **Rationale** (which rule is broken: `AGENTS.md §X` / `rules.md §Y` /
  ADR-NNNN / task clause / dimension from §2.2),
- **Recommended fix** (concrete, actionable).

`NIT`s (§2.3) may be listed after Minor in an optional **Nits** block; they
do not drive the verdict.

### 5.3 Reviewer Patches

Always state exactly one of:

- **Reviewer patches applied.**
- **No reviewer patches applied.**

If patches were applied, include:

- **Files changed** (paths),
- **Summary of each change** (one line per change, referencing the finding
  it resolves),
- **Confirmation that no unrelated changes were made.**

In Ask mode this section is always *"No reviewer patches applied (Ask
mode)."*

### 5.4 Verification

Always include, in this order:

- **Commands executed** — every command actually run, with its result
  (pass / fail / exit code, and a one-line note if useful).
- **Commands intentionally not executed** — every command from the task's
  `Commands` block (or the standard `make lint typecheck test`,
  `lint-imports`, `make test-int`, etc.) that was **not** run, with a
  one-line reason (e.g., *"docs-only change"*, *"no module boundaries
  touched"*).
- **Result of every command** — must be visible above; if any command
  failed, cite it under the relevant finding in §5.2.

If no commands were run, say so explicitly and justify it.

### 5.5 Suggested Commit

Always present. Choose one of the shapes below.

**If ready (single commit):**

```
Status:
Ready for commit.

Files:
- <path>
- <path>

Commit message:
<one-line subject>

<optional body>
```

**If ready (multiple commits are better):** up to a maximum of **three**
commits. Use this shape:

```
Status:
Ready for commit (split into N commits).

Commit 1
Files:
- <path>
Commit message:
<subject>

Commit 2
Files:
- <path>
Commit message:
<subject>
```

**If not ready:**

```
Status:
Do not commit yet.

Reason:
<one-paragraph rationale referencing the blocking/major/minor findings>
```

### 5.6 Implementation Patterns Review

Always present. Evaluate whether this task introduced any reusable
implementation pattern. See §10 for the qualification rubric.

If none qualify:

```
Status:
No new implementation patterns.
```

If one or more patterns qualify, for each pattern include:

- **Pattern title**
- **Why reusable** (which recurring situation it addresses)
- **Evidence** (concrete files/lines in this diff)
- **Suggested wording** (draft entry for the target document)
- **Suggested location** (usually `docs/implementation/patterns.md`; may be
  `rules.md` or `AGENTS.md` if the pattern is a hard rule)
- **Action** — exactly one of:
  - **Update patterns.md now**
  - **Defer until another occurrence**

Patterns must **never** be added automatically during a task review. The
reviewer only **recommends** them; the actual documentation update is a
separate task.

### 5.7 Recommended Next Action

Always present. Provide the **single best next action**. Examples:

- *"Ready for commit."*
- *"Apply reviewer patches and re-review."*
- *"Hand findings to `apply-review.md` and re-review after fixes."*
- *"Update task specification — scope is under-defined."*
- *"Safe to begin Task T-XXX."*

Exactly one action. If multiple actions are logically required, name the
first one and briefly note the follow-up.

---

## 6. Commit recommendations

The **Suggested Commit** section (§5.5) is where commit guidance lives. The
reviewer:

- proposes a commit only when the verdict is **PASS** (or **PASS WITH MINOR
  ISSUES** *after* all safe reviewer patches have been applied and the
  re-review returned **PASS**),
- otherwise states *"Do not commit yet."* with a reason,
- prefers **one** commit; may split into at most **three** commits when the
  diff cleanly separates along scope lines (e.g., production change vs.
  its tests vs. a doc update the task authorized),
- writes commit messages in imperative mood, referencing the task ID
  (e.g., `T-502: add …`), and keeping the subject ≤ 72 characters.

The reviewer does **not** execute the commit. The recommendation is
advisory; the implementer or maintainer performs the commit.

---

## 7. Next-action recommendations

The **Recommended Next Action** section (§5.7) resolves ambiguity about
what happens after the review. The reviewer picks **one** of:

- **Ready for commit** — verdict is PASS; use the Suggested Commit block.
- **Apply reviewer patches and re-review** — Code mode, PASS WITH MINOR
  ISSUES, all findings safe (§3.1), patches now applied.
- **Hand findings to `apply-review.md` and re-review** — any FAIL, or any
  unsafe minor finding in Ask mode / when reviewer chose not to patch.
- **Update task specification** — the task itself is under- or over-scoped
  and the diff cannot be judged fairly until the task is fixed.
- **Safe to begin Task T-XXX** — only when the diff is PASS and the next
  task in the plan is unambiguously unblocked by this change.

---

## 8. Code Mode (summary)

See §4.1 for the authoritative definition. Quick reference:

- Perform the review.
- Apply safe reviewer patches when appropriate.
- Write the **complete** report to `.tmp/reviews/<TASK_ID>.md` using the
  §5 structure exactly.
- Chat response may be a concise summary; the file is authoritative.
- Ensure `.tmp/` is git-ignored; add it to `.gitignore` if missing.
- Never commit the report file.

---

## 9. Ask Mode (summary)

See §4.2 for the authoritative definition. Quick reference:

- Analysis only. No file edits. No reviewer patches. No `.gitignore` edits.
- Return the **complete** §5 report directly in chat.
- The report structure is identical to Code mode.

---

## 10. Implementation-pattern evaluation

The reviewer evaluates every task for reusable patterns and reports the
outcome under **Implementation Patterns Review** (§5.6).

A candidate pattern **qualifies** only if **ALL** of the following are true:

1. **Demonstrated by concrete code** in the current diff (not hypothetical).
2. **Likely to recur** across future tasks (at least a plausible second
   consumer is imaginable).
3. **Prevents a real review finding or recurring ambiguity** (i.e., writing
   it down would have caught or clarified something this review had to work
   out).
4. **Not already documented** in any of:
   - `AGENTS.md`
   - `docs/implementation/rules.md`
   - `docs/implementation/patterns.md`

If any of the four is false, the pattern does **not** qualify.

Outcomes:

- **No qualifying patterns** → report *"No new implementation patterns."*
- **One or more qualifying patterns** → recommend each, per §5.6, with an
  **Action** of either *"Update patterns.md now"* or *"Defer until another
  occurrence"*.

The reviewer does **not** edit `patterns.md`, `rules.md`, or `AGENTS.md`
during the review. Adding a pattern is always a separate, explicitly
scoped task.

---

## 11. Output

At the end of the review, return:

1. **Files changed** — every file the reviewer touched (including the
   report file in Code mode and `.gitignore` if updated). In Ask mode this
   is *"None (Ask mode)."*.
2. **Summary of changes** — one line per touched file.
3. **Recommended commit message** — the message from §5.5 when the verdict
   permits a commit; otherwise *"Not applicable — do not commit yet."*.

This closing block is in addition to the §5 report; it is the short
delivery envelope, not a replacement for the report.
