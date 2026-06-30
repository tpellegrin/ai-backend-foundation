# ADR-0011: Enforce module boundaries with import-linter

- **Status**: Accepted
- **Date**: 2026-06-29

## Context

Documents like `docs/dependency-graph.md` are necessary but not sufficient. Without mechanical enforcement, boundaries erode silently: someone imports `app.users.persistence` from `app.auth.service`, the test suite still passes, and a year later the modules are tangled.

## Decision

- Add **`import-linter`** as a dev dependency and a CI gate, configured in `importlinter.toml`.
- Encode the dependency graph (see [dependency-graph.md](../dependency-graph.md)) as contracts:
  - **Layers** contract for `shared` < `observability` < `infrastructure` < `{llm, embeddings, prompts}` < `{auth, users, ai, rag, documents}` < `core` < `api` < `main`.
  - **Independence** contract for `llm`, `embeddings`, `prompts` (no cross-imports).
  - **Independence** contract for `ai`, `rag`.
  - **Forbidden** contract: nothing outside `app.core` may import from `app.infrastructure.*`.
  - **Forbidden** contract: nothing outside a module may import that module's `persistence` or `adapters` submodules.
- A new edge requires updating both `docs/dependency-graph.md` and `importlinter.toml` in the same PR.
- Complementary, in `ruff` (`flake8-tidy-imports`): forbid `from app.main import …` from anywhere.

## Consequences

**Positive**: architecture is mechanically defended, not just documented; refactors become safe; new contributors learn boundaries from CI failures, not from tribal knowledge.
**Negative**: occasional friction when a contract is too tight; the resolution is an ADR + contract change, not a quiet bypass.
**Neutral**: import-linter runs in seconds even on large codebases.

## Alternatives considered

- **Convention only**: rejected — does not survive scale.
- **Custom AST checks in pre-commit**: reinvents import-linter.
- **Move modules to separate packages**: heavy ceremony for what is still one deployable.
