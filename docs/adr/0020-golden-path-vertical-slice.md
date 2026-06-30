# ADR-0020: First product slice — the document RAG golden path

- **Status**: Accepted
- **Date**: 2026-06-30
- **Deciders**: Architecture review

## Context

Architectural scaffolding without an end-to-end product slice is not testable architecture. A foundation that ships only modules, ports, and CI checks proves nothing about whether the design actually composes. We need a single, explicit vertical slice that exercises every boundary in the system. The slice must also be the proof that RAG citations work — a non-negotiable requirement from the start, not a Phase 3 addition.

## Decision

Phase 2 ships **one** end-to-end vertical slice — the "golden path":

```
POST /api/v1/documents
   → store document metadata + blob (BlobStorage port)
   → enqueue ingestion job (TaskQueue port → Arq worker)
   → parse document (DocumentParser, in worker)
   → chunk document (Chunker, in worker)
   → generate embeddings (EmbeddingModel port)
   → store vectors (VectorStore port → pgvector)
   → transition document status: pending → processing → ready

POST /api/v1/rag/ask
   → embed query (EmbeddingModel port)
   → retrieve top-k chunks (VectorStore port)
   → attach citations at retrieval time
   → generate answer (ChatModel port, prompt = rag_answer_v1)
   → consult ai_governance.check_call_allowed (deny if over budget)
   → record LLMCallObservation (all 11 required fields)
   → return { answer, citations[] } with X-Request-ID
```

The slice is the **acceptance test for the architecture**. Every Port in Phase 2 is exercised. Every layer is traversed. The OTel trace is continuous from edge to provider. The slice is documented in `README.md` as a one-command demo against `make up`.

Specifically, the slice validates:

- The `platform` ports layer (storage, queue, cache).
- The capability layer (`llm`, `embeddings`, `prompts`).
- The domain layer (`documents`, `rag`, `ai_governance`).
- The composition root (`app.core.wiring.*`).
- The HTTP edge (`app.api` — Problem Details, idempotency, rate-limit, correlation).
- Background work (`infrastructure.queue.arq` + worker).
- Observability (structured logs + OTel + `LLMCallObservation`).
- Security (JWT, Argon2, refresh rotation).

## Consequences

**Positive**

- The architecture is provable, not aspirational.
- New contributors have a concrete example of every pattern in one slice.
- Any architectural regression breaks the slice's integration test in CI.

**Negative**

- More upfront work than a "scaffold only" Phase 2. We deliberately accept this cost.

## Alternatives considered

- **Ship scaffolding only, with stubs.** Rejected: stubs do not exercise boundaries; they hide them.
- **Ship a simpler `/echo` slice.** Rejected: an echo endpoint does not exercise embeddings, the queue, the vector store, governance, or citations.
- **Ship the slice without ingestion (pre-loaded corpus).** Rejected: citations without provenance are theater; provenance requires real ingestion.
