# Revised Phase 3 Scope

> Phase 3 builds on the foundation. It is **not** a list of everything left to do. It is the next coherent slice of capability that the foundation makes cheap.

---

## 1. Theme

Move from "one product slice works end-to-end" to "the substrate can host multiple AI products in parallel with safety, evals, and operational maturity."

## 2. Capability expansion

### Multi-provider LLM & embedding adapters
- `infrastructure/llm_providers/`: `anthropic.py`, `gemini.py`, `openai_compatible.py` (vLLM, Groq, Together, Azure OpenAI).
- `infrastructure/embedding_providers/`: `voyage.py`, `cohere.py`, optional `local.py` (sentence-transformers via sidecar).
- `ModelRouter` upgraded: cost/latency/capability routing, with fallbacks consulted via `ai_governance.service.pick_fallback`.

### Agents (`app/ai/`)
- `AgentRunner` facade implemented over PydanticAI.
- First agent: tool-using research assistant with explicit typed tools.
- Tools: web fetch, internal search (RAG), structured calculator.
- `ConversationStore` adapters: Postgres (durable) + Redis (short-term cache).
- Streaming via SSE at HTTP edge (`/api/v1/ai/chat:stream`).
- MCP-compatible tool descriptor emission (per ADR-0012).

### Retrieval improvements (`app/rag/`)
- Hybrid retrieval (BM25 via Postgres + vector).
- Reranking stage (cross-encoder via provider or local).
- Query rewriting stage.
- Optional Qdrant `VectorStore` adapter.

### Vector store alternative
- `infrastructure/vector_stores/qdrant.py` with full contract-test parity to pgvector.

### Document ingestion at scale
- Larger parsers: `.docx`, `.pptx`, `.epub`, OCR for image-bearing PDFs.
- Per-tenant ingestion quotas in `ai_governance`.

### Evaluations
- `app/evaluations/` module (new).
- Golden datasets per prompt; deterministic + LLM-judge metrics.
- Eval failures break CI on tagged prompts (per ADR-0008).
- Linked to `LLMCallObservation` for offline replay.

### Governance maturity
- Per-user (not just per-tenant) budgets.
- Soft-degradation: when budget at 90%, force cheaper model from allowlist.
- Audit-event sink for SIEM (structured log + optional webhook).

## 3. Operational maturity

- `infrastructure/queue/arq.py`: priority queues, scheduled jobs, retry with jitter, dead-letter queue.
- Tracing: tail-based sampling at OTel collector for high-traffic endpoints.
- Metrics dashboards (Grafana JSON) shipped in `deploy/grafana/`.
- Runbooks in `docs/runbooks/` for: budget exhaustion, provider outage, embedding-dim mismatch, pgvector index bloat.
- Backpressure: token-bucket adapter wired into `RateLimiter` per route group.
- Postgres logical replication notes for read replicas.

## 4. Auth & multi-tenancy

- OIDC `IdentityProvider` adapter.
- Organizations + memberships; `Principal` carries `tenant_id` end-to-end.
- Row-level filtering helper in `infrastructure/db/` (tenant-scoped queries).
- Scopes/permissions catalog frozen.

## 5. Developer experience

- `make seed` — repeatable seed data, including a small RAG corpus.
- `make eval` — runs eval suite, gates on regressions.
- `scripts/replay_llm_call.py` — replays an `LLMCallObservation` against the current code path.
- `scripts/cost_report.py` — daily/weekly cost rollup by tenant/prompt/model from `usage_entries`.

## 6. Explicitly NOT in Phase 3

- GraphQL.
- WebSockets for agents (SSE only).
- DDD aggregates / event sourcing.
- Microservice split.
- Custom DI container.
- Building our own agent framework on top of PydanticAI.
- Real-time multi-modal (audio/video) pipelines.

These are reachable from the foundation but require their own scope discussion when justified by a product.

## 7. Phase 3 acceptance criteria (preview)

1. Two LLM providers usable in production with one config flag (no code change).
2. One end-to-end agent example with streaming and tool calls.
3. One eval suite gating one prompt in CI.
4. Hybrid retrieval beats pure-vector retrieval on a tagged eval set by a measurable margin.
5. Per-tenant budget enforcement demonstrably stops a runaway loop in <1s.
6. SIEM-shaped audit log entry for every privileged action.
7. Dashboards show, per tenant: requests, p95 latency, tokens, cost, error rate.
