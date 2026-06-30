# ADR-0016: Vertical-slice modules over file-type layout

- **Status**: Accepted
- **Date**: 2026-06-29

## Context

A common Python backend layout groups files by **technical role**: `models/`, `schemas/`, `routers/`, `services/`, `repositories/`. It looks clean at the start. By month six, every feature touches five sibling directories and "find all the code that does X" is a project-wide grep.

We design for **locality of change**: a feature should live in one place.

## Decision

- Top-level folders inside `app/` represent **domains and capabilities**: `auth`, `users`, `ai`, `rag`, `documents`, `llm`, `embeddings`, `prompts`, plus the leaves `shared`, `observability`, `infrastructure`, `core`, `api`.
- Inside a module, files describe **what the code is for**, not what type it is:
  - `domain.py` — pure types and rules,
  - `ports.py` — outbound Protocols,
  - `service.py` — use cases,
  - `api.py` — FastAPI router + request/response models,
  - `persistence.py` — SQLAlchemy mapped classes + queries,
  - `adapters/` — module-local adapter implementations,
  - `deps.py` — FastAPI dependency providers,
  - `tests/` — co-located.
- Subpackages appear when a module is non-trivial (e.g. `ai/agents/`, `ai/tools/`, `ai/memory/`, `rag/pipeline.py` may grow into `rag/pipeline/`). **Structure follows complexity, not aspiration.**
- **Forbidden top-level folders inside `app/`**: `models/`, `schemas/`, `routers/`, `services/`, `repositories/`, `utils/`, `common/`, `helpers/`. These names hide intent.
- A module's `__init__.py` declares its **public surface**. Imports across modules go through the public surface, never deep into siblings.

## Consequences

**Positive**: features change in one place; deletions are tractable; new contributors can read one module top-to-bottom without crossing folders; module boundaries can be enforced mechanically (see [ADR-0011](0011-enforce-module-boundaries-with-import-linter.md)).
**Negative**: contributors used to layered Django/DRF-style layouts need an orientation. One paragraph in the developer guide handles it.
**Neutral**: shared code still exists — in `shared/`, `observability/`, `infrastructure/` — but only when it is genuinely shared, not when it is "could be shared someday."

## Alternatives considered

- **File-type layout**: rejected — see context.
- **One package per module with separate `pyproject.toml`** (true monorepo): heavy ceremony for one deployable; revisit if/when modules genuinely deploy independently.
