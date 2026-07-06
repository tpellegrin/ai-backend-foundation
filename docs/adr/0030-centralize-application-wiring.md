# ADR-0030: Centralize application wiring and container boundaries

- Status: Accepted
- Date: 2026-07-05
- Supersedes: none
- Superseded by: none
- Related: ADR-0023 (composition-root ownership), ADR-0026 (infrastructure as an outer adapter ring), ADR-0027 (pragmatic ports-and-adapters), ADR-0028 (module-local use-case orchestration), ADR-0029 (framework and provider types at the edges)

## Context

The project uses a pragmatic ports-and-adapters architecture with a layered application core and infrastructure modeled as an outer driven-adapter ring.

The accepted boundary model is:

```text
Entrypoints call the application.
Use cases coordinate behavior.
Ports describe external needs.
Infrastructure implements ports.
Wiring chooses concrete implementations.
```

ADR-0023 established that runtime composition belongs to the application composition path: `app.main` creates the app, `app.core.lifespan` drives startup and shutdown, and `app.core.wiring.*` is the approved surface where concrete adapters are bound into the application.

ADR-0026 clarified that `app.infrastructure` is outside the layered core. Infrastructure adapters may import the ports they implement, but ordinary application modules must not import concrete infrastructure directly.

ADR-0028 proposed that non-trivial workflows should be represented as explicit module-local use cases.

ADR-0029 proposed that framework-specific and provider-specific types should stay at the edges.

Together, these decisions create a new implementation concern: if object construction is not clearly governed, concrete adapters can still leak through the system even if the top-level architecture is correct.

The main risks are:

- `app.core.wiring` becoming a vague pile of unrelated factory functions;
- `app.api` constructing concrete infrastructure adapters directly;
- FastAPI dependency providers becoming a hidden application-wide DI container;
- the application container becoming a service locator used from arbitrary modules;
- use cases hiding dependencies through globals or module-level singletons;
- infrastructure resources being created in multiple places with inconsistent lifecycle rules.

This ADR defines the wiring and container boundary so the architecture remains pleasant to work with as the system grows.

## Decision

Application wiring must be centralized, explicit, and boring.

The project will use `app.core.wiring.*` as the only approved package for constructing concrete infrastructure adapters and composing runtime application objects from those adapters.

The wiring model has three levels:

1. **Resource wiring**
2. **Adapter wiring**
3. **Use-case wiring**

The application may use a small typed application container, but the container must not become a global service locator.

FastAPI dependency injection may be used at the API edge, but it must delegate to approved application wiring or container access. It must not become the place where infrastructure adapters are manually constructed.

## Wiring levels

### 1. Resource wiring

Resource wiring creates long-lived or lifecycle-managed technical resources.

Examples include:

- database engine;
- database session maker;
- Redis client;
- HTTP client;
- OpenAI or provider SDK client;
- storage client;
- queue client;
- tracer, meter, and logger providers;
- health probe registry.

Resource wiring belongs under `app.core.wiring.*`.

Example modules:

```text
app.core.wiring.resources
app.core.wiring.db
app.core.wiring.redis
app.core.wiring.http
```

Resource wiring may import `app.infrastructure.*` when concrete infrastructure resources are required.

Resource lifecycle must be coordinated through `app.core.lifespan` or approved wiring helpers.

### 2. Adapter wiring

Adapter wiring wraps resources into port implementations.

Examples:

```text
Redis client -> RedisCache
database session maker -> SqlDocumentRepository
OpenAI client -> OpenAIChatModel
embedding provider client -> OpenAIEmbeddingModel
pgvector/session maker -> PgVectorStore
local filesystem config -> LocalBlobStorage
```

Adapter wiring belongs under `app.core.wiring.*`.

Example modules:

```text
app.core.wiring.cache
app.core.wiring.storage
app.core.wiring.queue
app.core.wiring.llm
app.core.wiring.embeddings
app.core.wiring.vector_store
```

Adapter wiring may import:

- infrastructure adapter implementations;
- the ports those adapters implement;
- settings required to build those adapters;
- resource wiring helpers.

Adapter wiring must not be duplicated in API handlers, domain modules, capability modules, or platform modules.

### 3. Use-case wiring

Use-case wiring composes application workflows from ports and project-owned services.

Examples:

```text
AnswerQuestionWithRag(
    vector_store=...,
    chat_model=...,
    prompt_registry=...,
    governance_gate=...,
)

IngestDocument(
    blob_storage=...,
    embedding_model=...,
    vector_store=...,
    document_repository=...,
    queue=...,
)
```

Use-case wiring belongs under `app.core.wiring.*`.

Example modules:

```text
app.core.wiring.documents
app.core.wiring.rag
app.core.wiring.ai_governance
```

Use-case wiring may depend on adapter wiring, ports, settings, and module-local use-case classes or factories.

Use-case wiring must be the place where concrete runtime implementations are assembled into application workflows.

## Container boundary

The application container is a small typed record, preferably a frozen `dataclass` (or an equivalent typed record), constructed exactly once during application startup/lifespan.

The container may hold:

- settings;
- lifecycle-managed resource references;
- adapter instances that implement ports;
- use-case factories or accessors;
- health probe registry and observability providers.

The container is not:

- a registry;
- a runtime lookup table;
- a service locator;
- a factory-of-factories.

Only the following modules may access the application container directly:

```text
app.main.*
app.core.lifespan
app.core.wiring.*
app.api.dependencies.*
```

A future `app.worker.*` entrypoint may be added to this whitelist only when introduced by a later task or ADR. It is not part of this ADR.

Domain modules, capability modules, platform modules, and infrastructure adapters must not retrieve dependencies from the container.

Use cases must receive dependencies explicitly through constructors or function arguments.

## FastAPI dependency boundary

FastAPI dependency injection is allowed at the API edge.

Acceptable uses include:

- current user or auth context;
- request ID or correlation context;
- pagination;
- request-scoped metadata;
- retrieving a use case from the application container through an approved API dependency provider.

FastAPI dependency providers must not manually construct concrete infrastructure adapters.

Good:

```python
@router.post("/rag/answer")
async def answer_question(
    request: AnswerQuestionRequest,
    use_case: AnswerQuestionWithRag = Depends(get_answer_question_use_case),
) -> AnswerQuestionResponse:
    result = await use_case.execute(...)
    return AnswerQuestionResponse.from_result(result)
```

Where `get_answer_question_use_case` delegates to an approved container or wiring surface.

Bad:

```python
@router.post("/rag/answer")
async def answer_question(request: AnswerQuestionRequest) -> AnswerQuestionResponse:
    redis = Redis(...)
    cache = RedisCache(redis)
    openai = OpenAI(...)
    chat_model = OpenAIChatModel(openai)
    use_case = AnswerQuestionWithRag(chat_model=chat_model, ...)
    ...
```

API modules translate HTTP into application calls. They do not assemble infrastructure.

## Rules

1. `app.core.wiring.*` is the only approved package for constructing concrete infrastructure adapters.

2. `app.core.wiring.*` may import `app.infrastructure.*`.

3. `app.api.*` must not import `app.infrastructure.*`.

4. `app.main` must not import `app.infrastructure.*`. `app.main` creates the FastAPI application and delegates lifecycle to `app.core.lifespan`. `app.core.lifespan` and `app.core.wiring.*` own runtime construction.

5. `app.core.lifespan` may coordinate lifecycle by calling approved `app.core.wiring.*` functions.

6. Use cases must receive dependencies explicitly.

7. Use cases must not retrieve dependencies from the application container.

8. The application container must not be used as a global service locator.

9. FastAPI dependency providers may retrieve already-wired application objects, but must not become infrastructure factories.

10. Infrastructure adapters must not construct unrelated adapters.

11. Resource creation must be centralized so lifecycle, cleanup, health checks, and observability remain consistent.

12. If a task needs a new runtime dependency, it must add or update the appropriate wiring module rather than constructing the dependency ad hoc.

## Wiring module naming

Resource and adapter wiring modules are named by the technical concern they compose:

```text
app.core.wiring.db
app.core.wiring.cache
app.core.wiring.storage
app.core.wiring.queue
app.core.wiring.llm
app.core.wiring.embeddings
app.core.wiring.vector_store
app.core.wiring.http
```

Use-case wiring modules mirror the name of the owning domain/capability module:

```text
app.core.wiring.rag           # composes app.rag use cases
app.core.wiring.documents     # composes app.documents use cases
app.core.wiring.ai_governance # composes app.ai_governance use cases
```

Wiring modules contain construction, configuration reading, and lifecycle registration only. Wiring modules must not contain business logic.

## Testing rule

Once the application container exists, CI should include a wiring smoke test that constructs the full application container against test settings on every run. The test does not exercise routes; it only proves the object graph assembles. This catches wiring drift before it reaches integration tests.

## Relationship to ADR-0029

ADR-0029 governs which framework and provider types are allowed at which edges. Wiring modules are the only inner surface permitted to import concrete provider SDKs and infrastructure adapters at construction time. See ADR-0029 for the delivery-edge vs driven-adapter-edge split.

## Consequences

### Positive

- Keeps object construction predictable.
- Makes adapter replacement easier.
- Keeps API handlers focused on HTTP translation.
- Keeps use-case dependencies explicit and testable.
- Prevents the application container from spreading through the codebase.
- Keeps resource lifecycle centralized.
- Makes health probes and readiness checks easier to reason about.
- Supports import-linter enforcement of infrastructure boundaries.
- Makes the architecture easier for both human developers and AI agents to follow.

### Neutral

- `app.core.wiring.*` becomes an important architectural surface.
- New adapters usually require both an infrastructure module and a wiring module.
- Some small factory functions may feel repetitive.

### Negative

- More explicit wiring code is required.
- Developers must resist the convenience of constructing dependencies directly inside API handlers.
- If wiring modules are not kept organized by concern, `app.core.wiring` can become cluttered.
- A poorly designed container could still become a service locator if review discipline fails.

## Alternatives considered

### 1. Let API dependency providers construct everything

FastAPI dependency injection can construct complex dependency graphs.

Rejected.

This would make the API layer responsible for infrastructure assembly. It would also spread construction logic across route modules and dependency providers, weakening the composition-root boundary.

FastAPI dependencies should remain an API-edge mechanism, not the project’s core composition model.

### 2. Use a third-party dependency injection framework

A dedicated DI framework could manage object construction automatically.

Rejected for now.

The project does not yet need the additional abstraction, runtime indirection, or framework-specific configuration. A small typed container and explicit wiring functions are easier to inspect, test, and enforce.

This may be reconsidered later if manual wiring becomes demonstrably painful.

### 3. Use a global service locator

A global container could be imported anywhere and used to retrieve dependencies on demand.

Rejected.

This hides dependencies, makes tests harder to understand, and weakens the explicit constructor-based style expected for use cases and services.

### 4. Construct infrastructure adapters directly where needed

Application modules could instantiate adapters directly when they need them.

Rejected.

This violates the ports-and-adapters boundary and would allow concrete provider details to leak into API, domain, capability, or platform code.

### 5. Centralize wiring in one large module

The project could place all wiring in a single file such as:

```text
app.core.wiring
```

Rejected.

A single large wiring module would become hard to navigate. Wiring should be centralized by package but organized by concern.

Accepted shape:

```text
app.core.wiring.cache
app.core.wiring.storage
app.core.wiring.llm
app.core.wiring.embeddings
app.core.wiring.vector_store
app.core.wiring.documents
app.core.wiring.rag
```

### 6. Use explicit wiring modules organized by concern

Accepted.

This keeps construction centralized without making one file responsible for the entire application graph.

## Implementation notes

A typical adapter flow should look like:

```text
app.platform.cache.ports.Cache
        ↑ implemented by
app.infrastructure.redis.cache.RedisCache
        ↑ constructed by
app.core.wiring.cache
        ↑ used by
app.core.wiring.<use_case_area>
        ↑ exposed to API through
app.api.dependencies.<area>
```

A typical use-case flow should look like:

```text
app.api.routes.rag
        ↓ calls
app.rag.use_cases.answer_question.AnswerQuestionWithRag
        ↓ depends on
app.rag.ports.VectorStore
app.llm.ports.ChatModel
app.prompts.ports.PromptRegistry
app.ai_governance.ports.GovernanceGate
        ↑ implemented by
app.infrastructure.*
        ↑ bound by
app.core.wiring.rag
```

The API layer should see use cases, commands, results, request models, and response models.

The API layer should not see Redis clients, OpenAI SDK clients, SQLAlchemy engines, storage SDKs, or pgvector implementation details.

## Testing guidance

Use cases should be testable with fakes or stubs for their ports.

API tests may override API dependency providers to supply fake use cases.

Infrastructure adapter tests may use real or containerized dependencies when appropriate.

Wiring tests should verify that the expected concrete objects are assembled without requiring API handlers to know about those concrete objects.

A useful testing split is:

```text
Unit tests:
  use cases with fake ports

API tests:
  route behavior with dependency overrides

Infrastructure tests:
  adapter contract behavior against real or testcontainer dependencies

Wiring tests:
  object graph construction and health/readiness registration
```

## Review guidance

A reviewer should reject a change if:

- an API route imports `app.infrastructure.*`;
- a domain, capability, or platform module imports `app.infrastructure.*`;
- a use case pulls dependencies from the container;
- a module creates Redis, OpenAI, SQLAlchemy, storage, queue, or vector-store clients outside approved wiring/infrastructure surfaces;
- a FastAPI dependency provider manually assembles concrete infrastructure adapters;
- a new adapter is added without an approved wiring path;
- wiring is added to an unrelated module because it was convenient;
- resource lifecycle is duplicated in multiple places.

A reviewer should allow a change if:

- concrete adapter construction is added under `app.core.wiring.*`;
- API dependencies only retrieve already-wired use cases or request-scoped edge concerns;
- use cases receive explicit constructor dependencies;
- infrastructure adapters remain behind ports;
- resource cleanup is owned by lifespan or approved wiring helpers.

## Relationship to Import Linter

Import Linter should enforce the boundary mechanically where practical:

- ordinary application modules must not directly import `app.infrastructure.*`;
- only `app.core.wiring.*` may directly import `app.infrastructure.*`;
- `app.infrastructure.*` must not import `app.main`, `app.api`, or `app.core`;
- infrastructure adapters should not import other infrastructure adapters.

This ADR does not replace ADR-0026. It specifies how runtime object construction should happen inside the boundary established by ADR-0026.

## Relationship to future ADRs

This ADR intentionally does not decide:

- whether persistence modules should use Repository or Unit of Work;
- whether application events or a message bus should be introduced;
- whether background jobs should use direct queue dispatch, application events, or an outbox;
- whether a third-party DI framework should ever be adopted.

Those decisions require more concrete implementation pressure and should be handled by later ADRs.

## Summary

The project chooses explicit wiring over hidden dependency construction.

`app.core.wiring.*` owns runtime assembly. Use cases receive explicit dependencies. API handlers translate HTTP. Infrastructure implements ports. The application container supports composition but must not become a global service locator.
