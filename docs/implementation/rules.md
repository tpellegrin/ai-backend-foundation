# Implementation Rules — Phase 2 of `ai-backend-foundation`

> Authoritative execution rules for the implementing (lower-complexity) model.
> These rules are binding. They must not be re-interpreted or re-designed.
> Source of architectural truth: `AGENTS.md`, `docs/phase-2-revision/02..07`, `docs/adr/0018..0022`.
>
> Companion files:
> - Plan overview, dependency map, task index: [`../../IMPLEMENTATION_PLAN.md`](../../IMPLEMENTATION_PLAN.md)
> - Per-task specs: [`./tasks/`](./tasks/)
> - Reviewer instructions + final review checklist: [`./review.md`](./review.md)

---

## 1. Phase-2 clarifications the implementing model must honor

These resolve known cross-cutting ambiguities. They override any literal reading of an individual task that would conflict with them.

- **C-2 clarification.** OTel exporters and providers are constructed inside `app/core/wiring/`. `app/observability/` only exposes config types, middleware factories, and the `request_id_var` context var. Do not import OTel exporters from `app/observability/`.
- **C-4 clarification.** One type per role per module. `domain.py` → frozen dataclasses (Pydantic only for validation-heavy value objects). `api.py` → Pydantic v2 request/response. `persistence.py` → SQLAlchemy mapped. **Never** mix.
- **S3 storage adapter is Phase 3.** Phase 2 ships **only** the local-FS `BlobStorage` adapter. Settings, `.env.example`, docker-compose, and wiring must not assume S3 in Phase 2. Task T-705 is removed; `aioboto3` does not enter Phase 2.
- **Container is incremental.** `app/core/container.py` (T-504) starts with the **minimal** set of fields wired by tasks already completed. Each later wiring task (T-708, T-1212, T-1402, T-1503) **appends** its field. A task may not reference a Container field that has not yet been added.
- **Makefile arrives in T-103.** Tasks T-101 and T-102 must not invoke `make ...` in their `Commands` block; they use the equivalent `uv run` commands directly. Every later task may use `make ...`.
- **`importlinter` runs at every phase.** Contracts in T-107 validate cleanly against an empty/skeleton `app/` package (T-107 creates a minimal `app/__init__.py` so `lint-imports` has a target). The same contracts continue to apply unchanged after every later task adds modules.
- **`import-linter` config filename is `.importlinter`** at the repository root, INI format. This is one of the three filenames `import-linter` auto-discovers (the others being `setup.cfg` and `pyproject.toml`). A standalone `importlinter.toml` is **not** auto-discovered and is forbidden — it forces a `--config` flag that drifts between Makefile, pre-commit, CI, and tests. Configuration must also **not** be inlined into `pyproject.toml` (T-102 owns that file). Every invocation site — Makefile, pre-commit, CI, the `tests/test_imports.py` shell-out — must use the bare command `uv run lint-imports` (no `--config` flag). T-107 introduces the file; later tasks may only append contracts.
- **`ai_governance` domain/ports precede `app.llm.service`.** A standalone task T-1100 (ai_governance domain + ports only) executes before T-1102. The remaining ai_governance tasks (T-1201..T-1206) stay in S12 as scheduled.

---

## 2. Repository State Awareness

The implementation of Phase 2 is a sequential process. The following rules govern how to handle the evolving state of the repository:

1. **Early tasks intentionally operate on an incomplete repository.** Not all tooling (MyPy, coverage, etc.) will pass perfectly in the first few tasks. This is expected.
2. **Future files must never be created early.** Do not create `app/__init__.py`, `app/main.py`, or any other file listed in a future task just to make a linter or test runner happy.
3. **Command failures caused by repository incompleteness should be reported, not worked around.** If `mypy` fails because the `app/` package doesn't exist yet (before T-107), report the failure and explain that the package is not yet part of the plan. Do not create the package early.
4. **Task boundaries always take precedence over making commands pass.** Your primary obligation is to satisfy the current task's requirements and allowed files, not to achieve a green build by pulling in future work.
5. **Coverage expectations evolve.** A 80% coverage gate is impossible when zero lines of production code exist. In such cases, report the coverage result (even if 0%) and proceed if the tests required for the current task pass.
6. **Empty `import-linter` layers/sources are valid.** `import-linter`'s `layers`, `forbidden`, and `independence` contracts are vacuously satisfied when their referenced packages contain no imports. However, to avoid scaffolding empty folders early, use optional layer syntax `(app.module_name)` in the `layers` contract for any module that does not yet exist. Future `ignore_imports` entries must not be preloaded; they must be added only in the task that introduces the real import edge. Dummy imports and dummy package markers (`app/shared/__init__.py`, etc.) are strictly forbidden.

---

## 3. Global rules (apply to every task; no exceptions)

These rules are enforced by `import-linter`, `ruff`, `mypy --strict`, and human review. A task is **not done** if it violates any of them.

1. Do not redesign architecture. If a task seems to require redesign, **stop and report unresolved issue**.
2. Do not introduce new top-level folders. Top-level forbidden folder names: `models/`, `schemas/`, `routers/`, `services/`, `repositories/`, `utils/`, `common/`, `helpers/`.
3. Do not introduce new third-party dependencies unless the current task explicitly authorizes it.
4. **`from app.infrastructure.* import ...` is forbidden everywhere except inside `app/core/wiring/`.**
5. Provider SDKs (`openai`, `anthropic`, `google.generativeai`, `cohere`, `voyageai`, `qdrant_client`, `boto3`/`aioboto3`, `redis`, `arq`, `pydantic_ai`) may be imported **only** in their dedicated adapter file. `pydantic_ai` is reserved for `app/ai/agent_runner.py` (Phase 3 — skeleton only in Phase 2).
6. Do not create generic `Repository<T>` abstractions.
7. Do not return SQLAlchemy mapped objects from `service.py` or `api.py`. Translate to domain or API types at the boundary.
8. `os.environ` / `os.getenv` may be read only inside `app/core/config/`.
9. No inline prompt strings in `service.py`/`pipeline.py`. All prompts live in `app/prompts/library/<id>_v<n>.yaml`.
10. No direct LLM provider calls outside `app/infrastructure/llm_providers/`. All LLM calls flow through `app.llm.service`, which **must** call `app.ai_governance.service.check_call_allowed` first and emit `LLMCallObservation`.
11. No `except Exception: pass`, no bare `except:`, no swallowed errors. Re-raise or record.
12. No hardcoded secrets, model ids, prompt strings, or URLs in business logic.
13. No `print(` in `app/`. Use `structlog` via `app.observability.logging`.
14. No `requests`, `urllib.request`, `psycopg2`, or `time.sleep` in `app/`. Use `httpx`, `asyncpg`, `asyncio.sleep`.
15. Every `# type: ignore` must carry a rule code and a one-line reason: `# type: ignore[<rule>]  # <reason>`.
16. Every API error response is RFC 9457 Problem Details produced by `app/api/errors.py`. Never raise `HTTPException` below `api.py`. Never include stack traces, SQL, secrets, or raw provider responses in error bodies.
17. Every API response carries `X-Request-ID` (echo of inbound header, otherwise newly generated UUIDv4).
18. Every external HTTP call goes through `app/infrastructure/http/`.
19. Coverage gate: `--cov-fail-under=80` on `app/`. Tests must not be skipped or weakened to pass.
20. Do not fake pgvector in tests that claim to validate retrieval. Use Testcontainers Postgres + pgvector.
21. Do not add TODO comments as substitutes for implementation.
22. A module's public surface is **only** what its `__init__.py` re-exports. Other modules must import from `__init__.py`, not from internal files (except `api.py` for the API mounting layer and `persistence.py` mapped classes only within the same module).
23. Each task must update `importlinter.toml` if it introduces a new allowed edge. Each task must keep `make check` passing.
24. **"Allowed files" always includes the task-local test files required by "Tests required".** See §4 for the full policy: task-local tests are allowed at their canonical locations; module `__init__.py` may be edited **only** to re-export a public symbol introduced by the current task; nothing else (helpers, `conftest.py`, migrations, config keys, docs) is implicitly in scope — the task spec must name every support file, otherwise stop and report.
25. **The "standard four" Commands block** referenced by many tasks is exactly:
    ```
    make fmt
    make lint
    make typecheck
    make test
    ```
    This block is only valid for tasks that depend (transitively) on T-103 (Makefile). T-101 and T-102 use the `uv run ...` equivalents listed in their own Commands block.

---

## 4. Allowed-files discipline

The `Allowed files` block is the exhaustive list of files an implementer may create or modify for a task, with three narrowly scoped exceptions codified below. Anything else is a scope violation and must be reported (`Stop signals`, §6), not silently added.

**Policy — what is always allowed on top of the literal `Allowed files` list:**

1. **Task-local tests required by the task itself.** Every test file listed under the task's `Tests required` block is allowed, at the canonical locations:
   - co-located unit / contract tests → `app/<module>/tests/test_<name>.py`
   - API tests → `tests/api/test_<name>.py` (or `app/<module>/tests/test_api.py` when the task explicitly says so)
   - integration tests (Testcontainers, DB, Redis, Arq, pgvector) → `tests/integration/test_<name>.py`

   This applies whether `Allowed files` uses the shorthand `tests`, names the test file explicitly, or omits it entirely. If `Tests required` refers to a test that lives in a **different** task ("see T-XXX", "regression test in T-YYY"), do **not** create it under the current task — that test file belongs to the other task's `Allowed files`.

2. **Module `__init__.py` re-exports — only when required.** You may edit `app/<module>/__init__.py` **only** to re-export a public symbol introduced by the current task. You may not edit an `__init__.py` for any other reason (imports for side effects, reordering, comments, unused re-exports). If the current task adds no new public symbol, do not touch `__init__.py`. If the task creates a new module directory, its `__init__.py` must be listed explicitly under `Allowed files`.

3. **Nothing else is implicitly allowed.** No helpers, shared fixtures, `conftest.py`, package `__init__.py` files, migrations, `.env.example` keys, docs, or configuration are implicitly in scope. If the task genuinely needs any such support file, that file **must** appear by name in the task's `Allowed files`. If it does not, the task is under-scoped: **stop and report** — do not add the file.

**Other allowed-files rules:**

- Forbidden imports/files/patterns listed under `Forbidden` must not appear. If you believe you need them, **stop and report** — do not modify other files to make it work.
- Never add files under top-level forbidden folder names: `models/`, `schemas/`, `routers/`, `services/`, `repositories/`, `utils/`, `common/`, `helpers/`.
- Reviewers **must** treat task-local test files required by `Tests required` as in-scope, per bullet 1 above, and must not flag them as scope violations. Reviewers **must** flag any file that is not covered by the literal `Allowed files` list or by bullets 1–2 above.

---

## 5. Command discipline

- **Expected vs. Implementation Failures.** Explicitly distinguish between failures caused by your implementation (which must be fixed) and expected failures caused by the current incomplete state of the repository (which should be reported).
- If a required command fails because future tasks have not yet been implemented: **stop, explain why, report it, do not create future code, and do not weaken architecture.**

- Run **every** command listed under the current task's `Commands` block. A task is **not done** until they all succeed.
- At minimum, run `make lint typecheck test`. Run `make test-int` and `make check` when the task lists them.
- Tasks T-101 and T-102 predate the Makefile (T-103) and use the `uv run ...` equivalents declared in their own `Commands` blocks.
- After T-103, all later tasks may use `make ...`.
- **Do not bypass quality gates.** No `# type: ignore` without rule code + one-line reason. No `noqa` without a code. No `@pytest.mark.skip` to silence failure. No deleting failing tests. No `-DskipTests`-style escapes.
- When introducing a new allowed cross-module edge, update `.importlinter` **and** `docs/dependency-graph.md` **in the same task**.
- Do not add `--config <path>` to any `lint-imports` invocation (Makefile target, pre-commit hook, CI step, or test shell-out). Rely on auto-discovery of `.importlinter`. Adding an explicit path hides config-filename mistakes and creates drift between invocation sites.

---

## 6. Stop signals (request guidance — do not improvise)

Stop and request guidance when any of the following is true:

- A contract would need to be weakened to make a test or build pass.
- A forbidden import seems required to satisfy the task.
- A test from a previous task is failing after your change.
- A dependency listed in the task's `Depends on` block is not yet complete.
- The task's `Implementation requirements`, `Allowed files`, `Forbidden`, or `Acceptance criteria` are ambiguous, contradictory, or appear to require redesign.

The lower-complexity model is **not authorized** to make architectural decisions. If the plan is wrong or incomplete, report — do not "fix it".

---

## 7. Instructions for the lower-complexity implementation model

You are an executor, not a designer. Follow these rules without exception:

1. **One task at a time.** Pick the next unfinished task from the task index in [`../../IMPLEMENTATION_PLAN.md`](../../IMPLEMENTATION_PLAN.md) (lowest task id within the earliest unfinished section). Do not skip ahead. Do not interleave.
2. **Read `AGENTS.md` and this `rules.md` before every task.** If anything is ambiguous, stop and report — do not invent behavior.
3. **Respect "Allowed files".** You may create/modify only files explicitly listed for the current task, plus `app/<module>/__init__.py` re-exports when re-exporting a new symbol added in the same task. Editing any other file is a failure.
4. **Respect "Forbidden".** Forbidden imports/files/patterns must not appear. If you think you need them, stop and report.
5. **Implement the "Implementation requirements" literally.** Do not optimize, generalize, or add abstractions. Do not add features not listed.
6. **Write the listed tests.** Tests must fail before the implementation and pass after.
7. **Run the listed Commands.** A task is not done until they all succeed. Always run `make lint typecheck test` at minimum. Run `make test-int` and `make check` when listed.
8. **Do not bypass quality gates.** No `# type: ignore` without rule code + one-line reason. No `noqa` without a code. No `@pytest.mark.skip` to silence failure. No deleting failing tests.
9. **Update `.importlinter` and `docs/dependency-graph.md` in the same task** when introducing a new allowed edge.
10. **Report after each task:** files created/modified, tests added, commands executed, all command outputs (or final status), and any unresolved issues. If a task can't be completed without violating a rule, **stop and report** — do not modify other files to make it work.
11. **Never invent prompts.** All prompts live in `app/prompts/library/*.yaml` (T-1002 is the only Phase 2 prompt).
12. **Never call provider SDKs directly.** All providers are accessed via `app.llm.service` / `app.embeddings.service` and adapters wired in `app.core.wiring.*`.
13. **Stop signals.** Stop and request guidance when: (a) a contract would need to be weakened, (b) a forbidden import seems required, (c) a test from a previous task is failing after your change, (d) a dependency listed in "Depends on" is not yet complete.
14. **Repository State Awareness.** Adhere to the rules in Section 2. Never create future files or weaken the architecture to satisfy tooling. Report expected failures due to repo incompleteness.

Final reminder: the lower-complexity model is **not authorized** to make architectural decisions. If the plan is wrong or incomplete, report — do not "fix it".
