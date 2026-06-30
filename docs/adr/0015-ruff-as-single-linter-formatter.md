# ADR-0015: Ruff as the single linter and formatter

- **Status**: Accepted
- **Date**: 2026-06-29

## Context

Python projects historically combine Black (formatter), isort (imports), Flake8 (linter), pyupgrade (modernization), pydocstyle (docs), and sometimes Bandit (security). Each has its own config, its own CI step, and its own contributor friction. Ruff replaces all of them, fast.

## Decision

- **Ruff** is the only linter and the only formatter. Configured in `pyproject.toml` under `[tool.ruff]`.
- Enabled rule families (initial set; tightened as needed):
  - `E`, `W`, `F` (pycodestyle, pyflakes)
  - `I` (isort)
  - `B` (bugbear)
  - `UP` (pyupgrade — Python 3.13 idioms)
  - `S` (bandit; security)
  - `N` (pep8-naming)
  - `SIM` (simplify)
  - `TID` (tidy-imports; used to forbid `from app.main` and similar)
  - `ASYNC` (async-correct patterns)
  - `RUF` (ruff-specific)
  - `PL` (pylint subset, conservative)
  - `D` (pydocstyle — minimal, `D100`/`D104` disabled to avoid module-docstring noise)
- `ruff format` replaces Black. We do not configure Black.
- **Per-file ignores** are allowed only with a written justification in a comment.
- Ruff runs in **pre-commit** and in CI; the two must agree (same version).

## Consequences

**Positive**: one config, one tool, instant feedback; CI lint step measured in seconds; less cognitive load for contributors.
**Negative**: Ruff occasionally lags on a Flake8 plugin rule we like; acceptable.
**Neutral**: doc strings are not enforced project-wide; we encourage them on public surfaces and rely on review for the rest.

## Alternatives considered

- **Black + isort + Flake8 (+ plugins)**: three tools, three configs, slower; rejected.
- **Pylint as the gate**: powerful but slow and noisy; we use selected PL rules in Ruff instead.
