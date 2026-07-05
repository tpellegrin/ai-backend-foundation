# Implementation patterns

> Concrete implementation idioms approved for this repository.
> These are **not** contracts (see [`../../AGENTS.md`](../../AGENTS.md)) and **not** process
> (see [`./rules.md`](./rules.md)); they are the shape of code that reviewers approve
> without discussion.
>
> Companion files:
> - Contract layer (CI-enforceable): [`../../AGENTS.md`](../../AGENTS.md)
> - Execution discipline / stop signals: [`./rules.md`](./rules.md)
> - Final review checklist: [`./review.md`](./review.md)

## Precedence

- Patterns describe **preferred** implementation shapes, not mandatory contracts.
- If a task specification conflicts with a pattern, the **task specification takes precedence**.
- If the pattern seems better than the task spec, **update the task spec first** instead of silently deviating from either.

## Audience

- **Implementers** should use these as copyable shapes when writing new code.
- **Reviewers** should request these patterns unless there is a documented reason not to.

---

## Patterns to copy

### P-1. Injectable, immutable registries
- **Rule.** Registries are constructor-injected value objects. The composition
  root (later `app.core.wiring`) owns instantiation; the library only defines
  the shape.
- **Reference.** `app/observability/health.py::ProbeRegistry`.
- **Anti-pattern displaced.** AP-1 (module-level mutable singleton).
- **Rule of thumb.** If a symbol at module scope holds mutable state, it is wrong.

### P-2. Pure `build_*` factories
- **Rule.** Router/adapter/middleware assembly is a function that returns a
  fresh object, taking its dependencies as keyword-only parameters. No
  decorators wired at import time, no import-time side effects.
- **Reference.** `build_health_router(registry, *, is_ready)` in
  `app/observability/health.py`.
- **Anti-pattern displaced.** AP-2 (stateful `mark_startup_complete()` inside
  the library it configures).

### P-3. Reserved-field sanitization at the serialization boundary
- **Rule.** When merging caller-supplied dicts (`extras`, metadata, tags) into
  a canonical Pydantic model with `extra="allow"`, filter reserved keys
  **before** the `**` splat.
- **Reference.** `app/shared/problem_details.py::from_app_error` filters
  `AppError.extras` against `_RESERVED_FIELDS`.
- **Anti-pattern displaced.** AP-3 (unfiltered `**user_dict` into `extra="allow"`).
- **Test-name example.** `test_from_app_error_extras_cannot_override_reserved_fields`.

### P-4. Three-handler error surface (no "helpful" fourth)
- **Rule.** The API edge maps exactly `AppError`, `RequestValidationError`,
  and fallback `Exception` to Problem Details. Anything else (including
  `StarletteHTTPException`) intentionally falls through so misuse is visible.
- **Reference.** `app/api/errors.py::register_exception_handlers`.
- **Anti-pattern displaced.** AP-4 (adding an extra handler because a test
  raised the wrong exception type).
- **Test-name example.** `test_http_exception_is_not_normalized_to_problem_details`.

### P-5. Reject speculative future integrations
- **Rule.** Do not encode a subsystem shape that does not exist yet. If auth
  is T-701+, the access log emits `user_id=None` today — full stop.
- **Reference.** `AccessLogMiddleware` in `app/observability/middleware.py`.
- **Anti-pattern displaced.** AP-5 (`hasattr(user, "id")` / `isinstance(user, dict)`
  shape-guessing for an unshipped subsystem).
- **Test-name example.** `test_access_log_middleware_user_id_is_always_none_pre_auth`.

### P-6. Single-responsibility ASGI/Starlette middleware
- **Rule.** Each middleware does one thing (correlation, access log, security
  headers…), composes cleanly, and does not leak concerns across boundaries.
- **Reference.** `app/observability/correlation.py::CorrelationMiddleware`
  (only sets `request_id_var`) and `app/observability/middleware.py::AccessLogMiddleware`
  (only emits one `access_log` event).

### P-7. Logging style: structlog, one processor per concern
- **Rule.** Every processor is a small pure function of shape
  `(_logger, _method_name, event_dict) -> Mapping[str, Any]`. Configuration
  is one function (`configure_logging(level, json)`). No ad-hoc
  `logging.getLogger`, no `print`.
- **Reference.** `app/observability/logging.py` — `add_request_id`,
  `event_renamer`, `get_logger`.

### P-8. Test naming = behavior + boundary
- **Rule.** Test names read like specifications. Prefer long over cute; name
  the boundary being defended.
- **Examples.**
  - `test_http_exception_is_not_normalized_to_problem_details`
  - `test_from_app_error_extras_cannot_override_reserved_fields`
  - `test_access_log_middleware_user_id_is_always_none_pre_auth`
  - `test_access_log_middleware_no_header_side_effects` (also asserts T-502
    fields are *absent* — protects task boundary from silently drifting).

### P-9. Test structure: one file per module surface
- **Rule.**
  1. Every test file scopes to a single source module.
  2. Every test carries an explicit marker: `@pytest.mark.unit` or `@pytest.mark.api`.
  3. Fixtures build a fresh `FastAPI()` + `TestClient(..., raise_server_exceptions=False)`
     per test — no shared app.
  4. `request_id_var.set(...)` is wrapped in `try/finally` with `reset(token)`
     so contextvars never leak between tests.
- **Reference.** `app/api/tests/test_error_handlers.py`.

### P-10. Fakes/stubs live inline until a second consumer appears
- **Rule.** A fake stays in the test file that uses it. It is not promoted to
  `conftest.py` or a `tests/fakes/` folder until a real second consumer exists.
- **Reference.** `MockAppError` at the top of
  `app/api/tests/test_error_handlers.py`.
- **Anti-pattern displaced.** AP-6 (promoting a one-off fake into
  `conftest.py` before a second consumer exists). See also `rules.md` §4
  (allowed-files policy) and AGENTS.md §14.

### P-11. Leak-negative assertions on error paths
- **Rule.** When a body could leak secrets, assert the *absence* of specific
  markers, not just the presence of expected fields.
- **Reference.** `test_unhandled_error_mapping`:
  ```python
  body = response.text
  assert "secret-stacktrace-marker-should-not-leak" not in body
  assert "ValueError" not in body
  assert "Traceback" not in body
  ```
- **Anti-pattern displaced.** AP-9 (assertions that only check the happy shape).

### P-12. Docstrings explain *why the code is absent*, not just what is present
- **Rule.** When a shape is deliberately narrower than a naive reader would
  expect, the docstring must say so and point at the governing rule.
- **Reference.** Docstring of `register_exception_handlers` in
  `app/api/errors.py` (explains why `HTTPException` is *not* mapped), and
  docstring of `test_http_exception_is_not_normalized_to_problem_details`
  (points at AGENTS.md §12).

### P-13. Globally-unique test-file basenames for port tests
- **Rule.** Port test files under `app/platform/<module>/tests/` (and any
  other cross-module port location) use `test_<module>_ports.py` rather
  than the generic `test_ports.py`. pytest resolves test modules by
  basename; two files named `test_ports.py` in sibling packages cause an
  `import file mismatch` error the first time both packages are collected
  in the same session. Applies to future ports too, not just the current
  `platform/*` set.
- **Examples.** `test_storage_ports.py`, `test_cache_ports.py`,
  `test_queue_ports.py`, `test_rate_limit_ports.py`, `test_idempotency_ports.py`.
- **Anti-pattern displaced.** AP-10 (generic `test_ports.py` in every module).

### P-14. Ports and adapters: structural conformance
- **Rule.** Adapters (and test fakes) satisfy `Protocol` ports
  **structurally**, not by subclassing them. Do **not** write
  `class RedisCache(Cache):` / `class LocalBlobStorage(BlobStorage):` /
  `class OpenAIChatModel(ChatModel):`. Write the class without a Protocol
  base; `mypy --strict` will verify structural conformance, and
  `isinstance(instance, Port)` still works because ports are marked
  `@runtime_checkable`. This rule also applies to adapters that live
  outside `app.infrastructure.*` (e.g. `GovernanceService` structurally
  satisfies `app.llm.ports.GovernanceGate` per ADR-0024).

  **Driven vs. Entrypoint adapters.**
  - **Driven adapter:** A concrete integration called **by** the app (DB,
    Redis, storage, LLM SDK). Belongs under `app.infrastructure.*` and
    implements a port.
  - **Entrypoint adapter:** An external trigger calling **into** the app
    (FastAPI router, worker entrypoint, CLI command, scheduler). Modeled
    separately (e.g. `app.api`, `app.main`, `app.worker`) and does **not**
    belong under `app.infrastructure.*` by default.
- **Why.** Subclassing a `Protocol` couples the adapter to the port class
  object, invites accidental inheritance of default methods added later,
  and defeats the "structural conformance" contract that Protocol-based
  contract tests are meant to defend. Structural satisfaction is the
  entire point of ports-and-adapters (ADR-0018, ADR-0026).
- **Documented exception.** None in Phase 2. If a future adapter genuinely
  requires nominal inheritance (e.g. to inherit `abc.ABC`-style default
  method implementations), require an ADR that names the exception.
- **Reference.** Sibling test fakes under `app/platform/cache/tests/`,
  `app/platform/queue/tests/`, `app/platform/rate_limit/tests/`,
  `app/platform/idempotency/tests/` — none inherit from their respective
  Protocol; each is a plain class whose shape matches the port.
- **Anti-pattern displaced.** AP-11 (inheriting from a `Protocol` port).

### P-15. Provider-adapter task template
- **Rule.** Any task that introduces a new infrastructure adapter (Redis,
  local storage, Arq, `httpx`, OpenAI, Anthropic, Google, pgvector,
  future provider adapters, etc.) must satisfy **all** of the following,
  and the task spec must state each one explicitly:
  1. **Port implemented.** State the exact port module + class the
     adapter implements (e.g. `app.platform.cache.ports.Cache`,
     `app.llm.ports.ChatModel`).
  2. **Adapter module path.** Adapter lives under
     `app/infrastructure/<x>/…`. The SDK for the provider (`openai`,
     `anthropic`, `redis`, `arq`, `boto3`, `qdrant_client`, ...) is
     imported **only** in that adapter package.
  3. **Unique test basename.** Test file is `test_<adapter_name>.py`
     (e.g. `test_redis_cache.py`, `test_local_storage.py`,
     `test_openai_chat_model.py`), never a generic
     `test_cache.py`/`test_client.py`/`test_service.py`.
  4. **Structural conformance.** The adapter class does **not** inherit
     from its Protocol port (see **P-14**).
  5. **No `.importlinter` edits after ADR-0026.** Adapter-to-port imports
     are already allowed by the project-level adapter-ring contract; the
     task spec must **not** list `.importlinter` in its `Allowed files`
     for that direction. The only cases in which a provider-adapter task
     may edit `.importlinter` are (a) it introduces a genuinely new
     top-level module that must be added to the `Layers` contract (e.g.
     `app/worker.py` in T-1402), or (b) an ADR authorizes a scoped
     amendment. In both cases the amendment must be named in the task's
     `Allowed files` up front.
  6. **No SDK leakage.** Adapter translates provider SDK types into the
     domain / port types at its boundary. Provider SDK types must not
     appear in return values, parameters, exceptions, or logs outside the
     adapter package.
  7. **Observability.** Every external call is observable per AGENTS.md
     §13. LLM adapters additionally record `LLMCallObservation` with all
     eleven fields per AGENTS.md §11.
  8. **Contract test.** The adapter runs the port's contract test suite
     (parameterized). Integration tests using real infrastructure
     (Testcontainers Postgres / Redis / pgvector) live under
     `tests/integration/` and never fake the backend they claim to
     validate (AGENTS.md §5).
- **Reference.** Task specs [`T-702`](./tasks/T-702.md),
  [`T-704`](./tasks/T-704.md), [`T-1212`](./tasks/T-1212.md),
  [`T-1402`](./tasks/T-1402.md), [`T-1503`](./tasks/T-1503.md).
- **Anti-pattern displaced.** AP-11 (Protocol subclassing), AP-12
  (per-task `.importlinter` edits for adapter-to-port imports),
  AP-13 (generic adapter test basenames).

---

## Anti-patterns to avoid

Anti-patterns reviewers should reject. Each has previously caused a review finding in this repository.

- **AP-1.** Module-level mutable singletons (`registry = Registry()` at
  import time). Displaced by **P-1**.
- **AP-2.** Stateful `mark_startup_complete()` living inside the library it
  configures. Displaced by **P-2**.
- **AP-3.** `**user_dict` splat into a Pydantic model with `extra="allow"`
  without a reserved-key filter. Displaced by **P-3**.
- **AP-4.** Adding an extra error handler because a test raised the wrong
  exception type. Displaced by **P-4**.
- **AP-5.** `hasattr(x, "id") or isinstance(x, dict)` shape-guessing for a
  subsystem that has not shipped. Displaced by **P-5**.
- **AP-6.** Promoting a one-off fake into `conftest.py` before a second
  consumer exists. Displaced by **P-10**.
- **AP-7.** Reimplementing a stdlib / structlog processor when the built-in
  fits — *unless* the substitution is not purely mechanical. `event_renamer`
  was correctly kept because `structlog.processors.EventRenamer` renames a
  fixed source key and does not cover the "msg → event when event is empty"
  case.
- **AP-8.** Broad `except Exception:` in error paths that does not log via
  `structlog` with `exc_info` and mark the OTel span errored. See AGENTS.md §12.
- **AP-9.** Assertions that only check the happy shape and never assert the
  *absence* of leaked internals. Displaced by **P-11**.
- **AP-10.** Generic `test_ports.py` basenames in sibling port packages under
  `app/platform/*/tests/`. Causes pytest `import file mismatch` when two
  such files are collected together. Displaced by **P-13**.
- **AP-11.** Adapters (or test fakes) that inherit from their `Protocol`
  port — `class RedisCache(Cache):`, `class LocalBlobStorage(BlobStorage):`,
  `class OpenAIChatModel(ChatModel):`. Couples the adapter to the port
  class object and defeats structural conformance. Displaced by **P-14**.
- **AP-12.** Per-task `.importlinter` edits used to unblock an
  adapter-to-port import that ADR-0026 already permits (layer swap,
  `ignore_imports` addition, contract weakening). The correct action is
  to stop and report, then fix the contract shape via an ADR if the
  boundary really is wrong. Displaced by **P-15**.
- **AP-13.** Generic adapter test basenames (`test_cache.py`,
  `test_client.py`, `test_service.py`, `test_local.py`) that collide the
  moment a second adapter ships. Displaced by **P-15**.

---

## Maintaining this document

Update or review this catalog:

- After a review-fix introduces a reusable code shape.
- After the same review finding appears more than once.
- After a task exposes a recurring ambiguity that a pattern would have prevented.
- Before major new sections land — for example persistence, auth, LLM, RAG.
- During retrospective audits every 5–10 tasks.

Rules for edits:

- **Do not** add patterns for one-off decisions; wait for a second occurrence.
- **Do not** duplicate content from [`../../AGENTS.md`](../../AGENTS.md) (contracts) or
  [`./rules.md`](./rules.md) (execution discipline). Link, do not restate.
- Every new pattern must include:
  1. a one-line **rule**,
  2. a canonical **reference** file/symbol in the current tree,
  3. the **anti-pattern displaced**, if any.
  Optional: a representative test-name example.
- Prefer editing an existing pattern over adding a near-duplicate; patterns should stay small in number.
