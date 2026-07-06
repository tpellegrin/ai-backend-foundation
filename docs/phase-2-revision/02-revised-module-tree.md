# Revised Module Tree (Phase 2 Target)

> Supersedes the tree in `docs/folder-structure.md` for Phase 2 onward.
> Changes vs. the original are marked with `# NEW`, `# MOVED`, or `# CHANGED`.

```
ai-backend-foundation/                          # CHANGED: renamed from ai-backend-boilerplate
├── AGENTS.md                                   # NEW: enforceable AI coding rules
├── README.md
├── pyproject.toml
├── uv.lock
├── Makefile
├── Dockerfile                                  # CHANGED: moved to root for docker build context simplicity
├── docker-compose.yml                          # CHANGED: moved to root
├── docker-compose.override.yml
├── .pre-commit-config.yaml
├── .env.example
├── .gitignore
├── .editorconfig
├── importlinter.toml                           # contracts defined in §03
├── .github/workflows/
├── alembic/
│   ├── env.py
│   └── versions/
├── deploy/                                     # CHANGED: ops-only (k8s, otel collector config)
│   └── otel-collector-config.yaml
├── scripts/                                    # one-off operational scripts
├── docs/
│   ├── architecture.md
│   ├── folder-structure.md
│   ├── dependency-graph.md
│   ├── technology-decisions.md
│   ├── phase-2-revision/                       # NEW: this revision pack
│   └── adr/
└── app/
    ├── main.py
    │
    ├── core/                                   # composition root only
    │   ├── config/                             # Pydantic Settings (only place reading os.environ)
    │   ├── app_factory.py
    │   ├── lifespan.py
    │   ├── container.py
    │   ├── di.py
    │   └── wiring/                             # NEW: where ports are bound to adapters
    │       ├── llm.py                          # ChatModel + ModelRouter wiring
    │       ├── embeddings.py
    │       ├── vector_store.py
    │       ├── storage.py
    │       ├── cache.py
    │       ├── queue.py
    │       ├── governance.py
    │       └── observability.py
    │
    ├── shared/                                 # leaf utilities, no app.* deps
    │   ├── errors.py
    │   ├── problem_details.py
    │   ├── pagination.py
    │   ├── ids.py
    │   ├── clock.py
    │   ├── result.py
    │   ├── types.py
    │   └── pydantic.py
    │
    ├── observability/                          # leaf; only app.shared dep
    │   ├── logging.py
    │   ├── tracing.py
    │   ├── metrics.py
    │   ├── correlation.py
    │   ├── middleware.py
    │   └── health.py
    │
    ├── platform/                               # NEW: cross-cutting PORTS ONLY (no adapters, no SDKs)
    │   ├── __init__.py
    │   ├── storage/
    │   │   ├── ports.py                        # BlobStorage protocol + value types
    │   │   └── __init__.py
    │   ├── cache/
    │   │   ├── ports.py                        # Cache protocol
    │   │   └── __init__.py
    │   ├── queue/
    │   │   ├── ports.py                        # TaskQueue protocol + Job descriptor
    │   │   └── __init__.py
    │   ├── rate_limit/
    │   │   ├── ports.py                        # RateLimiter protocol
    │   │   └── __init__.py
    │   └── idempotency/
    │       ├── ports.py                        # IdempotencyStore protocol
    │       └── __init__.py
    │
    ├── infrastructure/                         # CHANGED: adapters ONLY; never imported outside app.core
    │   ├── db/                                 # async engine, sessionmaker, base metadata, pgvector type
    │   ├── redis/                              # async Redis client + Cache adapter (impl of platform.cache)
    │   ├── http/                               # shared httpx client with retries, timeouts, OTel
    │   ├── storage/                            # local FS + S3 adapters (impl of platform.storage)
    │   ├── queue/                              # arq adapter (impl of platform.queue)
    │   ├── rate_limit/                         # NEW: Redis token-bucket adapter
    │   ├── idempotency/                        # NEW: Redis-backed IdempotencyStore adapter
    │   ├── llm_providers/                      # ChatModel adapters: openai, anthropic, gemini, openai_compatible
    │   ├── embedding_providers/                # EmbeddingModel adapters
    │   └── vector_stores/                      # VectorStore adapters: pgvector, qdrant (future)
    │
    ├── auth/                                   # minimal in Phase 2
    │   ├── __init__.py
    │   ├── domain.py
    │   ├── ports.py                            # IdentityProvider, TokenSigner, PasswordHasher
    │   ├── service.py
    │   ├── api.py                              # /api/v1/auth/*
    │   ├── persistence.py
    │   ├── policies.py
    │   ├── deps.py
    │   ├── adapters/                           # argon2 hasher, pyjwt signer
    │   └── tests/
    │
    ├── users/                                  # minimal in Phase 2
    │   ├── __init__.py
    │   ├── domain.py
    │   ├── service.py
    │   ├── api.py
    │   ├── persistence.py
    │   ├── deps.py
    │   └── tests/
    │
    ├── prompts/                                # versioned prompt registry
    │   ├── __init__.py
    │   ├── domain.py
    │   ├── ports.py                            # PromptRegistry
    │   ├── registry.py                         # default fs-loading registry
    │   ├── library/                            # prompt YAML + Pydantic input/output schemas
    │   │   └── rag_answer_v1.yaml              # golden-path prompt
    │   ├── api.py                              # read-only inspection
    │   └── tests/
    │
    ├── llm/                                    # ChatModel port + ModelRouter + observation
    │   ├── __init__.py
    │   ├── domain.py
    │   ├── ports.py                            # ChatModel, ModelRouter
    │   ├── router.py
    │   ├── observability.py                    # LLMCallObservation
    │   ├── service.py                          # call_chat / call_structured; consults ai_governance
    │   └── tests/
    │
    ├── embeddings/                             # EmbeddingModel port + batching helper
    │   ├── __init__.py
    │   ├── domain.py
    │   ├── ports.py
    │   ├── service.py
    │   └── tests/
    │
    ├── ai_governance/                          # NEW: budgets, quotas, allowlists, fallback policy
    │   ├── __init__.py
    │   ├── domain.py                           # BudgetPolicy, UsageLedger, ModelAllowlist
    │   ├── ports.py                            # UsageRepository, BudgetPolicyStore
    │   ├── service.py                          # check_call_allowed(); record_usage(); pick_fallback()
    │   ├── persistence.py                      # usage ledger tables
    │   ├── api.py                              # admin: budgets, current usage (Phase 2: read-only)
    │   ├── events.py                           # AIUsageAuditEvent
    │   └── tests/
    │
    ├── ai/                                     # PydanticAI behind a thin AgentRunner facade (Phase 3)
    │   ├── __init__.py
    │   ├── domain.py
    │   ├── ports.py                            # ConversationStore, ToolRegistry
    │   ├── agent_runner.py                     # NEW: thin facade over PydanticAI
    │   ├── agents/                             # Phase 3
    │   ├── tools/                              # Phase 3
    │   ├── memory/                             # Phase 3
    │   ├── streaming.py                        # Phase 3
    │   ├── service.py
    │   ├── api.py                              # Phase 3
    │   └── tests/
    │
    ├── documents/                              # ingestion: parse → chunk → embed → store
    │   ├── __init__.py
    │   ├── domain.py                           # Document, Chunk, ChunkStrategy
    │   ├── ports.py                            # DocumentParser, Chunker
    │   ├── parsers/                            # Phase 2: pdf, html, markdown, txt
    │   ├── chunkers/                           # Phase 2: recursive token-aware
    │   ├── ingestion.py                        # NEW: job entrypoint enqueued via platform.queue
    │   ├── service.py
    │   ├── persistence.py                      # documents + chunks tables
    │   ├── api.py                              # POST /api/v1/documents
    │   └── tests/
    │
    ├── rag/                                    # retrieval + answer with citations
    │   ├── __init__.py
    │   ├── domain.py                           # Query, Citation, RetrievedChunk, Answer
    │   ├── ports.py                            # VectorStore
    │   ├── pipeline.py
    │   ├── service.py
    │   ├── api.py                              # POST /api/v1/rag/ask
    │   └── tests/
    │
    └── api/                                    # cross-cutting HTTP only
        ├── v1.py                               # mounts per-module routers
        ├── errors.py                           # exception handlers → Problem Details
        ├── pagination.py
        ├── idempotency.py                      # depends on platform.idempotency
        ├── rate_limit.py                       # depends on platform.rate_limit
        └── security_headers.py
```

---

## Module-level rules (unchanged where not noted)

- Each module's `__init__.py` is the **only** public surface. Anything not re-exported is private.
- `domain.py` is **pure**: no FastAPI, no SQLAlchemy, no httpx, no SDKs, no `app.infrastructure.*`, no `app.platform.*` adapters.
- `ports.py` holds outbound Protocols owned by the module.
- `api.py` is the only place HTTP types live.
- `persistence.py` is the only place SQLAlchemy mapped classes live.
- `adapters/` inside a module is for adapters that are clearly module-specific (e.g. `auth/adapters/argon2_hasher.py`). Cross-cutting adapters live in `app/infrastructure/*`.
- `tests/` is co-located per module; cross-module e2e tests live in top-level `tests/`.

## Phase 2 materialization status per module

| Module           | Phase 2 status                                                |
| ---------------- | ------------------------------------------------------------- |
| `core`           | Full                                                          |
| `shared`         | Full                                                          |
| `observability`  | Full                                                          |
| `platform`       | Full (ports only)                                             |
| `infrastructure` | db, redis, http, storage(local+s3), queue(arq), rate_limit, idempotency, llm(openai), embedding(openai), vector_store(pgvector) |
| `api`            | Full                                                          |
| `auth`           | Minimal skeleton: login/refresh/logout, Argon2, JWT           |
| `users`          | Minimal skeleton: get_me, create on first signup              |
| `prompts`        | Registry + 1 prompt (`rag_answer_v1`)                         |
| `llm`            | Full port + OpenAI adapter + observability + governance hook  |
| `embeddings`     | Full port + OpenAI adapter                                    |
| `ai_governance`  | Minimal skeleton: budget check, usage ledger, audit events    |
| `ai`             | Skeleton only (`AgentRunner` facade not used in Phase 2)      |
| `documents`      | Full: POST endpoint + ingestion job + parsers + chunkers      |
| `rag`            | Full: POST /ask + pipeline + citations                        |
