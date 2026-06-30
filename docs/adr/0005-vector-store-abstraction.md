# ADR-0005: Vector store abstraction; pgvector as the default adapter

- **Status**: Accepted
- **Date**: 2026-06-29

## Context

Early AI products usually fit comfortably in pgvector (hundreds of thousands to a few million vectors). At larger scale or with strict hybrid-search needs, a dedicated engine (Qdrant, Pinecone, Weaviate, Vespa) becomes necessary. We don't want to choose between "easy now" and "scalable later".

## Decision

- Define a **`VectorStore`** Protocol in `app.rag.ports`:
  - `async def upsert(collection, items: list[VectorRecord]) -> None`
  - `async def search(collection, query: Vector, *, k: int, filter: Filter | None) -> list[Match]`
  - `async def delete(collection, ids: list[VectorId]) -> None`
  - `async def ensure_collection(collection, dimension: int, metric: Metric) -> None`
- Filters are expressed in a **store-agnostic AST** (`Eq`, `In`, `And`, `Or`, `Not`, etc.). Each adapter compiles the AST to its native query.
- **Default adapter**: pgvector. Uses HNSW indexes by default; tunables exposed via settings. Vector columns live in the consuming module's `persistence.py` so RAG-specific tables are owned by `app.rag` (the consumer of the port).
- **Future adapters**: Qdrant first (operationally close to pgvector, strong filter and hybrid support), then Pinecone if/when managed becomes a requirement. Adapters live in `app.infrastructure.vector_stores.*`.
- **Hybrid search** (vector + keyword) is implemented as a **stage in `app.rag.pipeline`**, not as a vector-store feature. This keeps the port small and portable.

## Consequences

**Positive**: one operational dependency in early life (Postgres); swap to Qdrant/Pinecone collection-by-collection without touching `rag/` logic; filters are portable.
**Negative**: the filter AST is a moving target; we will extend it as real query patterns emerge. We resist letting the AST become a full query DSL.
**Neutral**: per-tenant collections vs single collection + tenant filter is a deployment-time choice; the port supports both.

## Alternatives considered

- **Qdrant as the default**: better at scale; loses the "one DB" simplicity for early products.
- **No abstraction, pgvector everywhere**: cheap now, painful at scale; rejected.
- **Use SQLAlchemy directly from `rag/` without a port**: tightly couples retrieval logic to Postgres; rejected.
