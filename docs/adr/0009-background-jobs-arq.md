# ADR-0009: Background jobs — Arq over Celery

- **Status**: Superseded by [ADR-0022](0022-promote-arq-to-phase-2.md) (Arq promoted from Phase 3 to Phase 2). Provider choice unchanged.
- **Date**: 2026-06-29

## Context

We need a background worker for: document parsing, embedding batches, long-running agent runs, evals, and scheduled tasks. The HTTP path must enqueue and forget; failures must be observable; the API must be the same in tests and production.

## Decision

- Introduce a **`TaskQueue`** Protocol in `app.platform.queue.ports` *(originally `app.infrastructure.queue.ports`; moved to `app.platform` by ADR-0018)*:
  - `async def enqueue(job_name, payload, *, key=None, defer=None) -> JobId`
  - `async def schedule(job_name, payload, *, cron) -> JobId`
- **Default adapter**: **Arq** (Redis-backed). *(Originally scheduled for Phase 3; promoted to Phase 2 by ADR-0022.)* Async-native, small, well-suited to our async stack. Workers share the same DI container as the API process so jobs reuse the same `ChatModel`, `EmbeddingModel`, `BlobStorage`, etc.
- **Test adapter**: an in-memory queue that runs jobs synchronously (or via `asyncio.create_task`) for unit tests; the same `TaskQueue` Protocol.
- **Jobs are functions**, not classes. Job functions live in their owning module (e.g. `app.documents.jobs.parse_document`). Registration is centralized in `app.infrastructure.queue.registry` to keep the worker entrypoint discoverable.
- **Idempotency keys** are first-class: `enqueue(..., key=...)` is dedup-safe within a configurable window.
- **Observability**: each job execution gets its own OTel span and structured log scope, with `job_name`, `job_id`, `attempt`, `tenant_id`, `correlation_id` (propagated from the enqueuer).
- **Heavy/long workflows** (multi-step, durable state, sagas) are explicitly out of scope for Arq. When they appear, we add a **Temporal** adapter behind the same `TaskQueue` (or a sibling `Workflow` port) without changing callers in HTTP modules.

## Consequences

**Positive**: small operational footprint (Redis we already run); async-native, no thread-pool gymnastics; same DI container as the API; future migration to Temporal is additive.
**Negative**: Arq is less feature-rich than Celery (no priorities-as-queues, weaker scheduler). For features we genuinely need but Arq lacks, we evaluate whether to extend the adapter or move that workload to a different backend (Temporal/Cloud Tasks) behind the same port.
**Neutral**: durability is bounded by Redis configuration; production deployments use AOF + replication.

## Alternatives considered

- **Celery**: most popular, but sync-first; bridging to our async stack is awkward; operational weight.
- **Dramatiq**: async support is bolted on, not native.
- **Taskiq**: promising, async-native; younger ecosystem; revisit at the next decision point.
- **Temporal**: excellent for durable workflows; overkill for the foundation; will be added as an additional adapter when products need it.
