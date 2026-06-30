# ADR-0007: No generic repository pattern

- **Status**: Accepted
- **Date**: 2026-06-29

## Context

A common pattern in "clean" Python backends is `Repository[Entity]` with `add`/`get`/`list`/`delete`. In practice it tends to:
- duplicate what SQLAlchemy already provides,
- push complex queries into ad-hoc methods (`find_users_with_active_subscriptions_by_org_and_created_after`),
- create a fake abstraction (we are not actually swapping the database),
- make joins, projections, and pagination awkward.

We already abstract the things we actually swap (LLM providers, embedders, vector stores, blob storage, queue). The relational database is not in that list.

## Decision

- **No generic repository base class. No `Repository[T]` per entity by default.**
- Queries are written as **small async functions** in each module's `persistence.py`:
  ```python
  async def get_user_by_email(session: AsyncSession, email: Email) -> User | None: ...
  async def list_active_users(session: AsyncSession, *, page: Cursor) -> Page[User]: ...
  ```
  They take an `AsyncSession`, return domain types or DTOs, and are trivially testable against a real Postgres via testcontainers.
- A module may introduce a **named, narrow repository class** if and only if:
  1. The module legitimately needs to swap persistence (true for `ConversationStore`, `BlobStorage`, etc. — these are ports, not repositories), **or**
  2. The module's query surface is large enough that grouping under a class with a descriptive name improves clarity (e.g., `DocumentSearchQueries`).
- The **Unit of Work** is the HTTP request: one `AsyncSession` per request via FastAPI dependency; commit/rollback at the service boundary.
- ORM mapped classes are **module-private**. They never leak past the module's `persistence.py`. Services return domain types (dataclasses or Pydantic models) or DTOs, not ORM instances.

## Consequences

**Positive**: less code, less indirection, less ceremony; complex queries stay readable; SQLAlchemy's full power is available where needed.
**Negative**: tests for query functions require a real database — which we already do via testcontainers; pure-unit tests for queries are not a goal.
**Neutral**: contributors used to layered architectures may initially miss a repository. The developer guide will explain the rule once.

## Alternatives considered

- **`Repository[T]` per entity**: rejected — overhead without benefit since we do not swap Postgres.
- **CQRS (separate read/write models)**: useful where reads and writes diverge sharply; introduce on a case-by-case basis, not as a default.
