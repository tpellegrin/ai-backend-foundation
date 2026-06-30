# AI Operating Procedures

> The repository is the source of truth. These prompts only orchestrate the
> knowledge that already lives in `AGENTS.md`, `docs/implementation/rules.md`,
> `docs/implementation/review.md`, `docs/implementation/tasks/T-*.md`, and
> `docs/adr/`.
>
> If a prompt below contradicts those documents, the documents win.
> Update the documents first, then the prompts.

---

## 1. What this folder is

`docs/ai/` is the **AI operating manual** for this repository. It standardizes
how *any* LLM — Claude, GPT, Gemini, or a model that does not exist yet —
contributes code, reviews it, applies review findings, or evolves the
architecture.

The prompts are deliberately short. They do not restate the rules; they point
at the canonical rule files and require the model to load and obey them.

---

## 2. The four roles

| Role               | Prompt                | Purpose                                                  |
| ------------------ | --------------------- | -------------------------------------------------------- |
| Implementer        | `implement-task.md`   | Execute **one** task end-to-end, exactly as written.     |
| Reviewer           | `review-task.md`      | Audit a diff against the rules; return PASS / MINOR / FAIL. |
| Review applier     | `apply-review.md`     | Apply only the approved review findings, nothing else.   |
| Architect          | `architect.md`        | Change architecture. High bar. ADR required.             |

There are intentionally **no other prompts**. Anything else (planning,
brainstorming, naming, refactoring, summarizing) is either:

- a subset of one of the four (use that prompt), or
- a conversation that should not produce a commit (do not write a prompt for it).

---

## 3. Recommended models

The prompts are model-agnostic. The recommendations below reflect the cost /
capability trade-off as of this writing. Adjust freely; do not change the
prompts to match a model's quirks.

| Prompt              | Recommended primary             | Acceptable alternatives             |
| ------------------- | ------------------------------- | ----------------------------------- |
| `implement-task.md` | Gemini Flash, Claude Sonnet     | GPT-5 (coding), GPT-5-mini          |
| `review-task.md`    | Claude Opus, GPT-5 (reasoning)  | Gemini Pro with thinking mode       |
| `apply-review.md`   | Same model that implemented     | Any implementer-tier model          |
| `architect.md`      | Claude Opus, GPT-5 (reasoning)  | Any frontier reasoning model        |

Rule of thumb: **never let an implementer-tier model approve its own work.**
The reviewer must be a different model, or at minimum a different session with
no carry-over context.

---

## 4. The standard workflow

```
┌──────────────────────┐
│ Pick a task          │  docs/implementation/tasks/T-XXX.md
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ implement-task.md    │  implementer model
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ review-task.md       │  reviewer model (different from implementer)
└──────────┬───────────┘
           │
     ┌─────┴──────┐
     │            │
   PASS       MINOR / FAIL
     │            │
     │            ▼
     │   ┌──────────────────────┐
     │   │ apply-review.md      │  implementer model
     │   └──────────┬───────────┘
     │              │
     │              ▼
     │   ┌──────────────────────┐
     │   │ review-task.md       │  reviewer model (re-review)
     │   └──────────┬───────────┘
     │              │
     │              ▼
     │            PASS
     │              │
     └──────┬───────┘
            ▼
       Commit / PR
```

Re-review is mandatory after any code change. Do not commit a diff the
reviewer has not seen in its final form.

---

## 5. When to use `architect.md`

Use it only when the change cannot be expressed as an existing task and would
violate, extend, or invalidate one of:

- `AGENTS.md` (sections 2–4),
- an existing ADR,
- the dependency graph in `docs/phase-2-revision/03-revised-dependency-graph.md`,
- `importlinter.toml` contracts.

If the change can be expressed as a new task without touching those documents,
write a new `docs/implementation/tasks/T-XXX.md` and use `implement-task.md`
instead. `architect.md` is for evolving the rules themselves.

---

## 6. Principles these prompts enforce

1. **Knowledge lives in the repo, not in prompts.** Prompts reference
   documents; they never duplicate their content.
2. **One task at a time.** No model is allowed to "also fix" something it
   noticed in passing. That work becomes a separate task.
3. **Boundaries are non-negotiable.** Allowed-files, forbidden imports, and
   dependency direction are enforced before the change is considered done.
4. **Stop on contradiction.** If a task contradicts the rules, the implementer
   reports it and halts. It does not choose a side.
5. **Two-model review.** Implementation and review happen in different
   sessions, ideally with different models.
6. **Every change is observable.** Tests, type-check, lint, and
   `import-linter` all run before completion. `make check` is the gate.
7. **The architect prompt is intentionally hard.** Architectural change is a
   deliberate act, never a side effect.

---

## 7. Maintaining these prompts

- Edit a prompt only when the *role* changes. If a rule changes, update
  `rules.md` / `review.md` / `AGENTS.md` instead — the prompt will pick it up
  automatically because it references those files.
- If you add a new canonical document the prompts should know about, add it to
  the **Read order** section of every prompt that needs it. Do not embed its
  contents.
- If a prompt grows past ~150 lines, it has started duplicating the repo.
  Refactor it back to references.
- Prompt changes require an ADR only if they change *what role exists* or
  *what gate must be satisfied*. Wording tweaks do not.
