# ADR-0031: Platform-owned SQLAlchemy mapping foundation

## Status
Accepted

## Context

The project architecture requires each feature module to own its persistence tables and define SQLAlchemy mapped classes in its local `persistence.py` file. However, all mapped classes must share a single `MetaData` instance and inherit from a common `DeclarativeBase` for table discovery and unified Alembic migrations.

Previously, this shared `Base` lived in `app.infrastructure.db.base`. Under the strict layering rules defined in ADR-0025 and ADR-0026, domain modules and their persistence components are forbidden from importing from `app.infrastructure`. This created a contradiction: feature modules needed the shared `Base` to define mapped classes, but importing it from infrastructure would violate architectural boundaries.

## Decision

The shared SQLAlchemy `DeclarativeBase`, shared `MetaData`/naming convention, and explicitly approved SQLAlchemy mapping types used directly by module-owned mapped classes belong to `app.platform.db`.

1. **Platform ownership**: `app.platform.db` may contain explicitly approved SQLAlchemy mapping primitives required for module-local persistence boundaries.
2. **Infrastructure ownership**: `app.infrastructure.db` continues to own engines, sessions, sessionmakers, probes, migration runtime integration, and database resource lifecycle.
3. **Module persistence**: Feature modules define SQLAlchemy mapped classes in local `persistence.py` files using primitives imported from `app.platform.db`.
4. **Strict boundaries**: Feature modules must not import from `app.infrastructure`.

## Consequences

- **Boundary preservation**: ADR-0026, ADR-0029, and ADR-0030 are preserved because runtime database infrastructure remains in the outer adapter ring while shared schema/mapping primitives move to a reachable platform layer.
- **Dependency flow**: The dependency graph now supports `app.<module>.persistence -> app.platform.db` and `app.infrastructure.db -> app.platform.db`.
- **Consistency**: Feature modules now have a legal path to participate in the shared database schema and Alembic metadata stream.
- **Narrow platform scope**: `app.platform.db` is not a general home for database runtime code. Only approved mapping primitives required at persistence-definition time belong there.

## Rejected Alternatives

- **Adding import-linter exceptions**: Rejected to avoid weakening the infrastructure boundary and accumulating architectural debt.
- **Moving `Base` to `app.shared`**: Rejected to keep `shared` as a leaf layer for pure shared types and utilities without framework dependencies like SQLAlchemy.
- **Moving `Base` to `app.core`**: Rejected because feature modules must not depend on core composition/runtime modules.
- **Moving engine/session/sessionmaker/probe code to platform**: Rejected to keep runtime infrastructure and lifecycle management clearly separated from schema/mapping definitions.
