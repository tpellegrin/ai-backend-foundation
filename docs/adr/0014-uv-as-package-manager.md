# ADR-0014: `uv` as the package and environment manager

- **Status**: Accepted
- **Date**: 2026-06-29

## Context

Python dependency management has historically been a patchwork (pip + venv + pip-tools + Poetry + pipx). The result is slow installs, ambiguous lockfiles, and onboarding friction. `uv` (by Astral) consolidates the stack into a single fast tool with a deterministic lockfile.

## Decision

- Use **`uv`** for: project dependencies (`pyproject.toml` + `uv.lock`), virtual environments, script running (`uv run`), tool installation (`uv tool`), and Python version pinning (`.python-version`).
- The **lockfile (`uv.lock`) is committed** and is authoritative in CI (`uv sync --frozen`).
- Dependency groups: `default`, `dev`, `test`, `docs`. Optional extras are reserved for provider adapters that ship as opt-in (e.g. `[anthropic]`, `[gemini]`, `[qdrant]`) so deployments install only what they use.
- `uv` version is **pinned** in CI and in the Dockerfile build stage.
- Developers run **only**:
  - `uv sync` — install everything.
  - `uv run <cmd>` — run inside the environment.
  - `uv add <pkg>` / `uv remove <pkg>` — modify dependencies.
- No `pip install` in docs. No `requirements.txt`. No `pyproject.toml + poetry.lock`.

## Consequences

**Positive**: minutes-faster CI; deterministic builds; one tool to learn; Docker images build dramatically faster; opt-in extras keep production images lean.
**Negative**: `uv` is younger than Poetry; we pin and follow its release notes.
**Neutral**: editors/CI that don't natively understand `uv` still work via `uv run <tool>`.

## Alternatives considered

- **Poetry**: mature; slower resolver, plugin ecosystem churn, weaker workspace story.
- **pip-tools + venv**: works, but every contributor reinvents their workflow.
- **pdm**: smaller ecosystem; `uv` has more momentum and is faster.
