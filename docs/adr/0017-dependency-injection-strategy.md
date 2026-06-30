# ADR-0017: Dependency injection strategy

- **Status**: Accepted
- **Date**: 2026-06-29

## Context

Dependency injection is how the architecture's promises (replaceable providers, testable modules, no global mutable state) actually hold up in code. Python has many DI libraries (`dependency-injector`, `punq`, `wired`, `kink`, `lagom`). Most introduce magic, runtime resolution at import time, or implicit globals. We can do better with less.

## Decision

We use a **two-tier** approach: a tiny composition root + FastAPI's `Depends` for request scope.

1. **Composition root** (`app.core.container`): a plain `@dataclass(slots=True, frozen=True)` `Container` holding **singletons** assembled at startup:
   ```python
   @dataclass(slots=True, frozen=True)
   class Container:
       settings: AppSettings
       db_engine: AsyncEngine
       session_factory: async_sessionmaker[AsyncSession]
       redis: Redis
       cache: Cache
       blob_storage: BlobStorage
       task_queue: TaskQueue
       chat_model: ChatModel
       embedding_model: EmbeddingModel
       vector_store: VectorStore
       prompt_registry: PromptRegistry
       password_hasher: PasswordHasher
       token_signer: TokenSigner
       clock: Clock
       # …
   ```
   The Container is built once in `app.core.lifespan` and attached to `app.state.container`.

2. **Request scope** via FastAPI `Depends` (`app.core.di`):
   - `get_container(request) -> Container`
   - `get_session(container) -> AsyncIterator[AsyncSession]` (one session per request, commit/rollback at the service boundary)
   - `get_current_user(...)`, `get_tenant_context(...)`, etc.
   - Each module exposes its own `deps.py` building on these.

3. **No service locator inside business logic.** Services receive dependencies as constructor arguments or function parameters. Modules never import the `Container` directly; the API layer pulls things out of it and passes them in.

4. **Tests** override dependencies via FastAPI's `app.dependency_overrides` for HTTP tests, and via simple constructor injection for unit tests. The `Container` itself can be replaced with a test container that wires fakes/in-memory adapters.

5. **No global mutable state.** Logging and tracing context use contextvars; everything else is passed explicitly.

## Consequences

**Positive**: zero magic, full IDE/type support, trivial to read; tests are obvious; the wiring is a single file you can read top-to-bottom; we are free of an external DI framework's release schedule.
**Negative**: explicitness costs a little extra typing in the composition root; we trade it for clarity.
**Neutral**: large `Container` dataclasses can grow; if they ever become unwieldy we split into nested containers per concern (db, ai, infra). Not yet.

## Alternatives considered

- **`dependency-injector`**: powerful but introduces magic providers and import-time wiring; the surface area is wider than we need.
- **`punq` / `kink`**: smaller, but still service-locator shaped; we prefer constructor injection.
- **Pure global singletons**: rejected — destroys testability.
- **Letting FastAPI `Depends` carry singletons via `lru_cache`**: works for small apps; couples singleton lifetime to import time and makes startup ordering implicit. We prefer an explicit lifespan-built container.
