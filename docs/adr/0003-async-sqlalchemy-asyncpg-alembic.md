# ADR-0003: Async SQLAlchemy 2.x + asyncpg + Alembic

- **Status**: Accepted
- **Date**: 2026-06-29

## Context

Our HTTP path is async (FastAPI). Mixing a sync ORM with async handlers causes thread-pool exhaustion under load. We also need first-class migrations, vector column support (pgvector), and idiomatic typing.

## Decision

- **SQLAlchemy 2.x async** with the typed declarative API (`DeclarativeBase`, `Mapped[T]`, `mapped_column`).
- **`asyncpg`** as the database driver (`postgresql+asyncpg://…`). It is the fastest, most correct PG driver in Python.
- **One `AsyncSession` per request**, created by a FastAPI dependency and closed by the dependency's teardown. Commits happen in the application service or the route handler, never implicitly.
- **One global `MetaData`** in `app.platform.db.base.Base.metadata`. Each module declares its mapped classes in its own `persistence.py`, all sharing the global metadata so Alembic sees them.
- **Alembic** for migrations, one linear history. Auto-generation is a *draft*, not the source of truth — every migration is reviewed and committed by hand. Naming convention for constraints (`ix_`, `uq_`, `ck_`, `fk_`, `pk_`) is configured to produce stable DDL diffs.
- **pgvector**: install via Alembic (`CREATE EXTENSION IF NOT EXISTS vector`). Use the official `pgvector.sqlalchemy.Vector` type wrapped in a small project-local column helper so dimension is explicit at the column site.
- **PgBouncer compatibility**: when running behind PgBouncer in transaction-pooling mode, disable server-side prepared statement caching (`prepared_statement_cache_size=0`, `statement_cache_size=0`). Made explicit in `DatabaseSettings`.
- **No generic `Repository[T]`** (see [ADR-0007](0007-no-generic-repository-pattern.md)).

## Consequences

**Positive**: full async stack with no thread-pool surprises; typed queries; stable migrations; pgvector available with the same operational footprint as the rest of Postgres.
**Negative**: SQLAlchemy 2.x async has a learning curve (`session.scalars(select(...))` ergonomics); we document patterns in the developer guide.
**Neutral**: SQLite cannot fully emulate Postgres (pgvector, JSONB ops) — tests use real Postgres via testcontainers.

## Alternatives considered

- **SQLModel**: blends Pydantic and SQLAlchemy; we keep them separate by design.
- **Tortoise ORM**: async-native but smaller ecosystem and weaker migration story.
- **Raw `asyncpg` + hand-rolled migrations**: pure but expensive; rejected.
