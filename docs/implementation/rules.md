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
- **`ai_governance` domain/ports precede `app.llm.service`.** A standalone task T-1100 (ai_governance domain + ports only) executes before T-1102. The remaining ai_governance tasks (T-1201..T-1206) stay in S12 as scheduled.

---

## 2. Global rules (apply to every task; no exceptions)

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
24. **"Allowed files" includes the test files named in "Tests required".** Whenever a task's `Allowed files` says `tests` (shorthand) or omits an explicit test path, the implementer is **required** (and thereby authorized) to create the test files listed in that same task's `Tests required` block under the canonical locations: co-located unit/contract tests at `app/<module>/tests/test_<name>.py`, API tests at `tests/api/test_<name>.py`, integration tests at `tests/integration/test_<name>.py`. No other files may be created.
25. **The "standard four" Commands block** referenced by many tasks is exactly:
    ```
    make fmt
    make lint
    make typecheck
    make test
    ```
    This block is only valid for tasks that depend (transitively) on T-103 (Makefile). T-101 and T-102 use the `uv run ...` equivalents listed in their own Commands block.

---

## 3. Allowed-files discipline

- You may create/modify **only** files explicitly listed in the current task's `Allowed files` block, **plus** `app/<module>/__init__.py` re-exports when re-exporting a new symbol added in the same task. Editing any other file is a failure.
- When `Allowed files` says `tests` (shorthand) or omits an explicit test path, you are required (and authorized) to create the test files listed under the same task's `Tests required` block, at their canonical locations (see Global rule #24).
- Forbidden imports/files/patterns listed under `Forbidden` must not appear. If you believe you need them, **stop and report** — do not modify other files to make it work.
- Never add files under top-level forbidden folder names: `models/`, `schemas/`, `routers/`, `services/`, `repositories/`, `utils/`, `common/`, `helpers/`.

---

## 4. Command discipline

- Run **every** command listed under the current task's `Commands` block. A task is **not done** until they all succeed.
- At minimum, run `make lint typecheck test`. Run `make test-int` and `make check` when the task lists them.
- Tasks T-101 and T-102 predate the Makefile (T-103) and use the `uv run ...` equivalents declared in their own `Commands` blocks.
- After T-103, all later tasks may use `make ...`.
- **Do not bypass quality gates.** No `# type: ignore` without rule code + one-line reason. No `noqa` without a code. No `@pytest.mark.skip` to silence failure. No deleting failing tests. No `-DskipTests`-style escapes.
- When introducing a new allowed cross-module edge, update `importlinter.toml` **and** `docs/dependency-graph.md` **in the same task**.

---

## 5. Stop signals (request guidance — do not improvise)

Stop and request guidance when any of the following is true:

- A contract would need to be weakened to make a test or build pass.
- A forbidden import seems required to satisfy the task.
- A test from a previous task is failing after your change.
- A dependency listed in the task's `Depends on` block is not yet complete.
- The task's `Implementation requirements`, `Allowed files`, `Forbidden`, or `Acceptance criteria` are ambiguous, contradictory, or appear to require redesign.

The lower-complexity model is **not authorized** to make architectural decisions. If the plan is wrong or incomplete, report — do not "fix it".

---

## 6. Instructions for the lower-complexity implementation model

You are an executor, not a designer. Follow these rules without exception:

1. **One task at a time.** Pick the next unfinished task from the task index in [`../../IMPLEMENTATION_PLAN.md`](../../IMPLEMENTATION_PLAN.md) (lowest task id within the earliest unfinished section). Do not skip ahead. Do not interleave.
2. **Read `AGENTS.md` and this `rules.md` before every task.** If anything is ambiguous, stop and report — do not invent behavior.
3. **Respect "Allowed files".** You may create/modify only files explicitly listed for the current task, plus `app/<module>/__init__.py` re-exports when re-exporting a new symbol added in the same task. Editing any other file is a failure.
4. **Respect "Forbidden".** Forbidden imports/files/patterns must not appear. If you think you need them, stop and report.
5. **Implement the "Implementation requirements" literally.** Do not optimize, generalize, or add abstractions. Do not add features not listed.
6. **Write the listed tests.** Tests must fail before the implementation and pass after.
7. **Run the listed Commands.** A task is not done until they all succeed. Always run `make lint typecheck test` at minimum. Run `make test-int` and `make check` when listed.
8. **Do not bypass quality gates.** No `# type: ignore` without rule code + one-line reason. No `noqa` without a code. No `@pytest.mark.skip` to silence failure. No deleting failing tests.
9. **Update `importlinter.toml` and `docs/dependency-graph.md` in the same task** when introducing a new allowed edge.
10. **Report after each task:** files created/modified, tests added, commands executed, all command outputs (or final status), and any unresolved issues. If a task can't be completed without violating a rule, **stop and report** — do not modify other files to make it work.
11. **Never invent prompts.** All prompts live in `app/prompts/library/*.yaml` (T-1002 is the only Phase 2 prompt).
12. **Never call provider SDKs directly.** All providers are accessed via `app.llm.service` / `app.embeddings.service` and adapters wired in `app.core.wiring.*`.
13. **Stop signals.** Stop and request guidance when: (a) a contract would need to be weakened, (b) a forbidden import seems required, (c) a test from a previous task is failing after your change, (d) a dependency listed in "Depends on" is not yet complete.

Final reminder: the lower-complexity model is **not authorized** to make architectural decisions. If the plan is wrong or incomplete, report — do not "fix it".
