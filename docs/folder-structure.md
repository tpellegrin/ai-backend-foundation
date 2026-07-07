# Folder Structure

> Folder names describe **what the code is about**, never **what file type it is**.
> Top-level folders inside `app/` are domains and capabilities, not technical roles.

This document is the canonical reference. If the tree below disagrees with the codebase, the codebase is wrong.

---

## Root

```
ai-backend-boilerplate/
├── app/                        # all production code lives here
├── tests/                      # cross-cutting and e2e tests (module-local tests live inside each module)
├── docs/                       # architecture docs and ADRs
│   ├── architecture.md
│   ├── folder-structure.md     # this file
│   ├── technology-decisions.md
│   ├── dependency-graph.md
│   └── adr/
├── deploy/                     # Dockerfile(s), compose files, k8s manifests (later)
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── docker-compose.override.yml
│   └── otel-collector-config.yaml
├── scripts/                    # one-off operational scripts (seed, migrate-helper, eval runners)
├── alembic/                    # migration env + versions (one history for the whole app)
│   ├── env.py
│   └── versions/
├── .github/workflows/          # CI (lint, type, test, build)
├── pyproject.toml              # uv-managed; ruff, mypy, pytest config live here
├── uv.lock
├── Makefile
├── .pre-commit-config.yaml
├── .env.example
├── .gitignore
├── .editorconfig
├── importlinter.toml           # boundary enforcement (see ADR-0011)
└── README.md
```

> Phase 1 ships only `README.md`, `docs/`. Everything else is materialized in Phase 2.

---

## `app/` — production code

```
app/
├── main/                       # composition **site** (per ADR-0023): builds the app and owns Container construction
│   ├── __init__.py             # ASGI entrypoint: `app = create_app()` (T-506)
│   ├── app_factory.py          # create_app(): constructs Container + empty ProbeRegistry, wires routers, middlewares, lifespan (T-505)
│   └── tests/                  # test_app_factory.py: middleware order, CORS, readiness, container identity
│
├── core/                       # composition **library**: building blocks the site (`app.main`) composes
│   ├── config/                 # Pydantic BaseSettings: AppSettings + per-concern settings
│   ├── lifespan.py             # startup/shutdown: reads app.state.container (installed by create_app) and mutates it in place
│   ├── container.py            # small dataclass holding singletons (db, redis, providers); constructed by create_app in app.main
│   ├── di.py                   # FastAPI dependency providers that expose container pieces
│   └── wiring/                 # the only place allowed to import from app.infrastructure.*
│
├── shared/                     # leaf utilities used by every module; depends on nothing in app/
│   ├── errors.py               # base AppError hierarchy; mapped to Problem Details in api edge
│   ├── problem_details.py      # RFC 9457 model
│   ├── pagination.py           # Cursor + Page[T] types
│   ├── ids.py                  # ULID/UUID7 helpers, typed Id[T]
│   ├── clock.py                # Clock protocol + system adapter
│   ├── result.py               # Result / Either-style helpers used sparingly
│   ├── types.py                # NewTypes, TypedDicts, common aliases
│   └── pydantic.py             # shared Pydantic base models, configs, validators
│
├── observability/              # logging, tracing, metrics, middlewares
│   ├── logging.py              # structlog configuration
│   ├── tracing.py              # OTel tracer/exporter setup
│   ├── metrics.py              # OTel meter setup; standard meters
│   ├── correlation.py          # request-id contextvar + middleware
│   ├── middleware.py           # access log + correlation + exception → problem details
│   └── health.py               # /healthz, /readyz, /livez routers and probes registry
│
├── platform/                       # cross-cutting PORTS and mapping foundation
│   ├── db/                         # shared SQLAlchemy Base + MetaData + mapping types
│   ├── storage/                    # BlobStorage port + value types
│   ├── cache/                      # Cache port
│   ├── queue/                      # TaskQueue port + Job descriptor
│   ├── rate_limit/                 # RateLimiter port
│   └── idempotency/                # IdempotencyStore port
│
├── infrastructure/             # third-party adapters and engines, owned by no single domain
│   ├── db/                     # async engine, sessionmaker, database lifecycle
│   ├── redis/                  # async Redis client factory + Cache adapter
│   ├── http/                   # shared httpx client with retries, timeouts, OTel instrumentation
│   ├── storage/                # BlobStorage port + local & S3 adapters
│   ├── queue/                  # TaskQueue port + Arq adapter (Phase 3)
│   ├── llm_providers/          # ChatModel adapters: openai, anthropic, gemini, openai_compatible
│   ├── embedding_providers/    # EmbeddingModel adapters: openai, voyage, cohere
│   └── vector_stores/          # VectorStore adapters: pgvector, qdrant (future)
│
├── auth/                       # identity, JWT, password hashing, current-user dependency
│   ├── domain.py               # User identity value objects, credentials, token claims
│   ├── ports.py                # IdentityProvider, TokenSigner, PasswordHasher (Protocols)
│   ├── service.py              # login, refresh, logout, password change use cases
│   ├── api.py                  # /api/v1/auth/* router and request/response models
│   ├── persistence.py          # refresh-token table queries
│   ├── policies.py             # authorization policies (RBAC + resource checks)
│   ├── deps.py                 # get_current_user, require_scope dependencies
│   ├── adapters/               # argon2 hasher, pyjwt signer, local identity provider
│   └── tests/
│
├── users/                      # user accounts, profiles (intentionally separate from auth)
│   ├── domain.py
│   ├── service.py
│   ├── api.py
│   ├── persistence.py
│   ├── deps.py
│   └── tests/
│
├── prompts/                    # versioned prompt registry
│   ├── domain.py               # Prompt, PromptVersion, RenderedPrompt types
│   ├── ports.py                # PromptRegistry protocol
│   ├── registry.py             # default in-memory + filesystem-loading registry
│   ├── library/                # actual prompt artifacts (yaml/jinja2 + Pydantic schemas)
│   │   └── README.md           # how to add a prompt
│   ├── evals/                  # golden datasets + harness hooks
│   ├── api.py                  # admin endpoints to list/inspect prompts (read-only)
│   └── tests/
│
├── llm/                        # LLM chat abstraction
│   ├── domain.py               # Message, ToolCall, ChatResult, ChatChunk, Usage, Cost
│   ├── ports.py                # ChatModel protocol; ModelRouter protocol
│   ├── router.py               # default ModelRouter (config-driven)
│   ├── observability.py        # LLMCallObservation + span/metric helpers
│   ├── service.py              # high-level call_chat / call_structured helpers
│   └── tests/                  # contract tests adapters must pass
│
├── embeddings/                 # embedding abstraction
│   ├── domain.py               # Vector, EmbeddingResult
│   ├── ports.py                # EmbeddingModel protocol
│   ├── service.py              # batch embedding helper
│   └── tests/
│
├── ai/                         # agents, conversation memory, tools, MCP-ready
│   ├── domain.py               # Conversation, Turn, Tool descriptors
│   ├── ports.py                # ConversationStore, ToolRegistry
│   ├── agents/                 # PydanticAI Agent definitions (one file per agent)
│   ├── tools/                  # typed tool functions; each tool is one file
│   ├── memory/                 # ConversationStore adapters (postgres, redis)
│   ├── streaming.py            # SSE helpers for token streams
│   ├── service.py              # run_agent, stream_agent use cases
│   ├── api.py                  # /api/v1/ai/* router (chat, stream, runs)
│   └── tests/
│
├── documents/                  # document ingestion and chunking
│   ├── domain.py               # Document, Chunk, ChunkStrategy
│   ├── ports.py                # DocumentParser, Chunker
│   ├── parsers/                # pdf, html, markdown, txt
│   ├── chunkers/               # recursive, token-aware, structural
│   ├── service.py              # ingest pipeline (parse → normalize → chunk)
│   ├── persistence.py
│   ├── api.py
│   └── tests/
│
├── rag/                        # retrieval-augmented generation pipeline
│   ├── domain.py               # Query, Citation, RetrievedChunk, Answer
│   ├── ports.py                # VectorStore protocol
│   ├── pipeline.py             # composable stages (search, rerank, cite, answer)
│   ├── service.py              # high-level retrieve() and answer() use cases
│   ├── api.py                  # /api/v1/rag/* router
│   └── tests/
│
└── api/                        # cross-cutting API concerns only (not per-domain routers)
    ├── v1.py                   # mounts all v1 routers from domain modules under /api/v1
    ├── errors.py               # exception handlers → Problem Details
    ├── pagination.py           # query param parsers shared across endpoints
    ├── idempotency.py          # Idempotency-Key middleware/dependency
    ├── rate_limit.py           # RateLimiter dependency
    └── security_headers.py     # security headers middleware
```

### Rules per module

- **`__init__.py`** must export only the **public surface** of the module (its service entrypoints and a few domain types). Everything else is private.
- **`domain.py` / `domain/`** is **pure**: no FastAPI, no SQLAlchemy, no httpx imports. Tested without I/O.
- **`ports.py`** holds **outbound** Protocols owned by the module. The module never imports adapters; the composition root injects them.
- **`api.py`** is the only place HTTP types (request/response Pydantic models) exist. Domain types never reach the wire.
- **`persistence.py`** is the only place SQLAlchemy mapped classes for this module exist. Mapped classes never leak past the module boundary.
- **`adapters/`** inside a module is for adapters that are clearly specific to that module (e.g., `auth/adapters/argon2_hasher.py`). Cross-cutting adapters live in `app/infrastructure/`.
- **`deps.py`** holds FastAPI `Depends` providers, never business logic.
- **`tests/`** co-located. Cross-module e2e tests live in the top-level `tests/`.

### Why some things live where they do

- **`auth/` vs `users/` are separate.** Authentication concerns (credentials, tokens, sessions) change on a different clock than user profile concerns (display name, avatar, preferences). Coupling them is a known mistake.
- **`prompts/` is a top-level module, not a subfolder of `ai/` or `llm/`.** Prompts are products; they have versions, owners, evals, and an API surface independent of who consumes them.
- **`llm/` does not own provider adapters.** It owns the **port** and the **router**. Adapters live in `infrastructure/llm_providers/` because they are infrastructure concerns, swapped at composition time.
- **`rag/` owns the `VectorStore` port** because RAG is the consumer that defines the semantics. Adapters live in `infrastructure/vector_stores/`.
- **`api/` exists at the top level for cross-cutting HTTP concerns only.** Per-domain routers live in each module's `api.py`. `app/api/v1.py` only **mounts** them.

### Forbidden patterns

- A top-level folder named `models/`, `schemas/`, `routers/`, `services/`, `utils/`, `common/`, or `helpers/`.
- `from app.infrastructure.llm_providers.openai import ...` anywhere outside `app/core/wiring/` or `app/infrastructure/`.
- `from app.<module>.persistence import ...` outside `app/<module>/` and `alembic/`.
- `import os; os.environ[...]` outside `app/core/config/`.
- A SQLAlchemy `Session` or `AsyncSession` constructed anywhere outside `app/infrastructure/db/`.
- A `print()` in production code. Ever.

These will be enforced mechanically by `import-linter` and Ruff rules in Phase 2.
