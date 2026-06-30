# Architecture Contradictions Found (Pre-Phase-2 Audit)

> Audit scope: `docs/architecture.md`, `docs/folder-structure.md`, `docs/dependency-graph.md`, ADRs 0001–0017.
> Goal: list every place where the stated architectural rules contradict each other or contradict the non-negotiable principles. Each contradiction has a concrete resolution that is implemented in the rest of this revision pack.

---

## C-1. Infrastructure ports are forbidden but required

- **Stated rule** (`dependency-graph.md` §3): *"`app.<any> → app.infrastructure.*` (except `app.core`)"* — forbidden edge.
- **Stated rule** (`folder-structure.md` *Forbidden patterns*): *"`from app.infrastructure.* import ...` anywhere outside `app/core/` or `app/infrastructure/`."*
- **Conflicting rule** (`dependency-graph.md` §4): the ports `BlobStorage`, `Cache`, `TaskQueue` are *defined in* `app.infrastructure.storage.ports`, `app.infrastructure.redis.ports`, `app.infrastructure.queue.ports`, and *consumed by* `app.documents`, `app.ai`, `app.rag`, and *"many"*.
- **Why this is a real contradiction, not a footnote**: a `Protocol` is not magically excluded from import-linter's reach. `from app.infrastructure.storage.ports import BlobStorage` *is* an import from `app.infrastructure.*`. The current rules cannot both be enforced.
- **Resolution**: introduce `app/platform/` as the home for cross-cutting **ports only** (`storage`, `cache`, `queue`, `rate_limit`, `idempotency`). Concrete adapters stay in `app/infrastructure/*`. Domain code imports `app.platform.*`; only `app.core` wires `app.infrastructure.*`. See ADR-0018.

## C-2. `app.observability` is a leaf, but the architecture also requires it to depend on infrastructure pieces

- **Stated** (`dependency-graph.md` §1, L0): `shared` and `observability` are leaves; `observability → shared` only.
- **Reality**: structlog/OTel are libraries, not internal infrastructure, so the leaf rule still holds at the *internal* boundary. The contradiction is smaller than C-1 but worth pinning: the **exporters / collector wiring** belongs to `app.core` (composition root), not to `app.observability`. `app.observability` exposes configuration objects and middleware factories; `app.core` constructs the exporters and registers providers.
- **Resolution**: clarified in the revised module tree (§02). No code change in concept, but the doc was ambiguous.

## C-3. `prompts/`, `embeddings/`, `llm/` listed both as siblings and as a layer

- **Stated** (`dependency-graph.md` §1): they are at L2 (capabilities), below domains (L3).
- **Stated** (`dependency-graph.md` §2): `app.users` may import from `app.auth` *(read-only domain types only)*. By the same logic, capabilities (`llm`, `embeddings`, `prompts`) might be tempted to import from each other.
- **Stated** (§2 asymmetries): *"`app.llm`, `app.embeddings`, `app.prompts` do not depend on each other. They are siblings."*
- This is consistent if and only if "siblings" implies "independent". The doc is correct; the contradiction is only that there is no enforcement contract spelled out for it. We add one.
- **Resolution**: in the revised dependency graph, the `Independence` contract is named and added to `importlinter.toml` in Phase 2.

## C-4. Pydantic models position is ambiguous

- **Stated**: Pydantic models at the API edge; domain uses dataclasses *or* Pydantic; ORM at persistence boundary.
- **Risk**: this is permissive enough to become an "ORM/API/domain hybrid", which is exactly what principle #11 forbids.
- **Resolution**: hard rule — *one type per role per module*: `api.py` request/response models are Pydantic v2; `domain.py` types are `@dataclass(slots=True, frozen=True)` by default, Pydantic only for validation-heavy value objects (e.g., `Email`, `Url`, `Vector`); `persistence.py` SQLAlchemy mapped classes never leave the module. Codified in AGENTS.md.

## C-5. `documents/` was a Phase-2-or-later concern but RAG citations require it

- **Stated** (principle #16): RAG must support citations from the beginning.
- **Stated** (`architecture.md` §5.5): citations attached at retrieval time.
- **Risk**: citations require provenance — `(document_id, chunk_id, span)` triples — which require `documents/` ingestion to be real. If `documents/` is a stub in Phase 2, RAG citations are theatre.
- **Resolution**: golden-path vertical slice (ADR-0020) makes `POST /api/v1/documents` → ingest → embed → store → `POST /api/v1/rag/ask` → answer-with-citations the **first** product slice of Phase 2. See revised Phase 2 scope (§04).

## C-6. Arq classified as Phase 3, but ingestion implies Phase 2 needs a queue

- **Stated** (ADR-0009, `architecture.md` §10): Arq is Phase 3.
- **Stated** (revised Phase 2 scope): ingestion (`parse → chunk → embed → store`) must run as a background job, not in the request path. Doing it inline contradicts principle #14 (latency budgets) and the "no sync I/O in async request paths" rule.
- **Resolution**: promote Arq to Phase 2. Supersede ADR-0009 with ADR-0022. The `TaskQueue` port lives in `app.platform.queue.ports`; the Arq adapter lives in `app.infrastructure.queue.arq`.

## C-7. No module owns LLM cost / budget enforcement

- **Stated** (principle #14): every LLM call records cost, tokens, etc.
- **Missing**: nothing in the current module tree owns the *enforcement* of token budgets, per-tenant caps, model allowlists, or provider fallback policies. `llm/observability.py` records, but no module decides whether the call is *allowed*.
- **Resolution**: add `app/ai_governance/` (ADR-0019). It owns budget policies, usage ledgers, allowlists/denylists, fallback policy, and emits audit events. `app.llm.service` consults it before every call.

## C-8. `import-linter` contracts not yet specified

- **Stated** (ADR-0011): enforce boundaries with import-linter.
- **Missing**: no concrete contract list. CI cannot enforce what isn't written.
- **Resolution**: revised dependency graph (§03) lists each contract; Phase 2 materializes `importlinter.toml` from that list.

## C-9. Repo name undersells the project

- **Stated**: `ai-backend-boilerplate`.
- **Reality**: this is not a boilerplate; it is a production substrate with governance, observability, and replaceable adapters baked in.
- **Resolution**: rename to `ai-backend-foundation` (ADR-0021). Logical rename in docs/config now; physical directory rename and remote rename happen at Phase 2 kickoff in one atomic commit.

## C-10. "Phase 1 ships only README and docs" is not a stated quality gate

- **Stated** (`folder-structure.md`): *"Phase 1 ships only `README.md`, `docs/`. Everything else is materialized in Phase 2."*
- **Risk**: Phase 2 is then everything, which makes it unbounded.
- **Resolution**: revised Phase 2 scope (§04) is explicitly bounded to (a) the foundation files and (b) the golden-path slice. Anything else is Phase 3.

---

## Summary

| #    | Contradiction                                       | Resolved by                |
| ---- | --------------------------------------------------- | -------------------------- |
| C-1  | Infrastructure ports forbidden but required         | `app/platform/` (ADR-0018) |
| C-2  | `observability` leaf vs. exporter wiring            | Doc clarification          |
| C-3  | Capability siblings independence not enforced       | New import-linter contract |
| C-4  | Pydantic role ambiguity                             | AGENTS.md hard rule        |
| C-5  | RAG citations require real `documents/`             | Golden-path slice (ADR-0020) |
| C-6  | Arq scheduled too late for Phase 2 ingestion        | Promote Arq (ADR-0022)     |
| C-7  | No owner for LLM cost / budget enforcement          | `app/ai_governance/` (ADR-0019) |
| C-8  | Import-linter contracts unspecified                 | Revised dep-graph §03      |
| C-9  | Repo name undersells the project                    | Rename (ADR-0021)          |
| C-10 | Phase 2 unbounded                                   | Revised Phase 2 scope (§04) |
