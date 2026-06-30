# ADR-0021: Rename repository from `ai-backend-boilerplate` to `ai-backend-foundation`

- **Status**: Accepted
- **Date**: 2026-06-30
- **Deciders**: Architecture review

## Context

The repository is named `ai-backend-boilerplate`. The name implies a starter template, copy-paste scaffold, or tutorial — categories where mediocre code is acceptable. The repository is none of those. It is a production substrate: it carries explicit ports, enforced module boundaries, observability discipline, AI governance, prompt versioning, and a real golden-path slice. The current name actively misrepresents the project to anyone (including reviewers and contributors) opening it for the first time.

## Decision

Rename the repository to `ai-backend-foundation`. "Foundation" describes the project honestly: a stable base intended to outlive any particular product built on top of it.

The rename is performed in **one atomic commit** at the Phase 2 kickoff and includes:

- Git remote rename (handled at the hosting provider).
- Local clone directory rename.
- All occurrences of `ai-backend-boilerplate` in `README.md`, `docs/*`, `pyproject.toml` (`[project] name`), `Dockerfile`, `docker-compose.yml`, CI workflows, and any other configuration.
- The Python package name remains `app` (unchanged).

Documentation references in the revision pack already use the new name.

## Consequences

**Positive**

- The repository self-describes accurately on first contact.
- Search and discovery (internal and external) reflect intent.
- Aligns with the quality bar stated in the non-negotiables.

**Negative**

- One-time link/bookmark churn for early viewers. Mitigated by hosting-provider redirect on the remote.

**Neutral**

- Phase 1 ADRs and history still reference the old name. They are kept as-is (immutable). Forward references use the new name.

## Alternatives considered

- **Keep the name and document the intent in README.** Rejected: names drive expectations more than READMEs. The cheap fix is the right fix.
- **`ai-platform-backend`.** Rejected: collides with the `app/platform/` package name introduced in ADR-0018 and may imply a multi-tenant SaaS *product*, which this is not.
- **`ai-substrate`.** Rejected: too abstract; "foundation" is widely understood.
