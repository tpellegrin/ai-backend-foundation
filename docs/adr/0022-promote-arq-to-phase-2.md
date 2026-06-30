# ADR-0022: Promote Arq (background jobs) to Phase 2

- **Status**: Accepted; supersedes ADR-0009
- **Date**: 2026-06-30
- **Deciders**: Architecture review

## Context

ADR-0009 chose Arq over Celery and scheduled the background-jobs capability for Phase 3. The Phase 2 scope, however, now includes the golden-path vertical slice (ADR-0020): `POST /api/v1/documents` triggers `parse → chunk → embed → store`. That work cannot run inline in the HTTP request path without:

1. Violating the latency budget for the endpoint (PDF parsing + embedding round-trips are seconds, not milliseconds).
2. Violating the rule against blocking I/O in async request handlers under load.
3. Forfeiting retries, observability, and isolation for a path that is inherently flaky (embedding rate limits, parser failures).

If ingestion is in Phase 2, a queue is in Phase 2. There is no defensible middle ground.

## Decision

Promote Arq from Phase 3 to Phase 2. The `TaskQueue` Protocol lives in `app.platform.queue.ports` (per ADR-0018). The Arq adapter lives in `app.infrastructure.queue.arq` and is wired exclusively by `app.core.wiring.queue`. The worker is a separate container in `docker-compose.yml`, runs the same DI container as the API, and inherits the same observability (`job_id`, `job_name`, `attempt`, `request_id`, `tenant_id`).

Phase 2 worker scope:

- One worker pool, default concurrency.
- Retries with exponential backoff and a bounded maximum.
- Dead-letter on terminal failure (table `failed_jobs` in Phase 2; richer DLQ semantics in Phase 3).
- Healthcheck endpoint suitable for compose / k8s readiness.
- Integration test that enqueues a real ingestion job and observes the full lifecycle through pgvector.

The choice of Arq itself (vs. Celery, Dramatiq, RQ) is unchanged from ADR-0009.

## Consequences

**Positive**

- The golden-path slice is honest about what it does: ingestion is asynchronous, observable, and retryable.
- The `TaskQueue` port is exercised in Phase 2, surfacing API problems early.
- Phase 3 inherits a working worker baseline.

**Negative**

- One additional container in compose and one additional CI integration test pathway.
- Slightly larger Phase 2 footprint than the original plan.

## Alternatives considered

- **Run ingestion inline in the API process.** Rejected: explicit violation of latency and async-purity rules; would also bypass observation requirements for background work.
- **Use FastAPI `BackgroundTasks` for Phase 2.** Rejected: not durable, not retryable, dies with the process, no separate worker scaling.
- **Defer ingestion entirely and stub it.** Rejected: that breaks the golden-path acceptance criterion in ADR-0020. RAG citations require real ingestion.

## Relationship to ADR-0009

ADR-0009 is **superseded** by this ADR. The provider choice (Arq) carries forward; the **phase** changes from 3 to 2.
