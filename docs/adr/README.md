# Architecture Decision Records

This directory captures **consequential** decisions: choices that are hard to reverse, or whose rationale must survive turnover.

We use a compact [MADR](https://adr.github.io/madr/)-inspired format. An ADR is required when:

1. The decision changes a public interface or a module boundary.
2. The decision introduces or removes a dependency.
3. The decision constrains future contributors (e.g., "we always do X").

ADRs are immutable once **Accepted**. Superseded ADRs are kept and linked from their replacement.

## Index

| #    | Title                                                                | Status   |
| ---- | -------------------------------------------------------------------- | -------- |
| 0001 | [Observability stack: structlog + OpenTelemetry](0001-observability-stack-structlog-otel.md) | Accepted |
| 0002 | [Authentication: JWT (asymmetric) + Argon2id](0002-authentication-jwt-argon2.md) | Accepted |
| 0003 | [Async SQLAlchemy 2.x + asyncpg + Alembic](0003-async-sqlalchemy-asyncpg-alembic.md) | Accepted |
| 0004 | [LLM provider abstraction (`ChatModel` port)](0004-llm-provider-abstraction.md) | Accepted |
| 0005 | [Vector store abstraction; pgvector as default](0005-vector-store-abstraction.md) | Accepted |
| 0006 | [PydanticAI as the agent runtime](0006-pydanticai-as-agent-runtime.md) | Accepted |
| 0007 | [No generic repository pattern](0007-no-generic-repository-pattern.md) | Accepted |
| 0008 | [Prompt management and versioning](0008-prompt-management-and-versioning.md) | Accepted |
| 0009 | [Background jobs: Arq over Celery](0009-background-jobs-arq.md) | Superseded by 0022 |
| 0010 | [RFC 9457 Problem Details for errors](0010-rfc9457-problem-details-errors.md) | Accepted |
| 0011 | [Enforce module boundaries with import-linter](0011-enforce-module-boundaries-with-import-linter.md) | Accepted |
| 0012 | [Forward-compatible MCP support](0012-future-mcp-compatibility.md) | Accepted |
| 0013 | [Config strategy: Pydantic Settings, composed](0013-config-strategy-pydantic-settings.md) | Accepted |
| 0014 | [uv as the package and environment manager](0014-uv-as-package-manager.md) | Accepted |
| 0015 | [Ruff as the single linter and formatter](0015-ruff-as-single-linter-formatter.md) | Accepted |
| 0016 | [Vertical-slice modules over file-type layout](0016-vertical-slice-modules.md) | Accepted |
| 0017 | [Dependency injection strategy](0017-dependency-injection-strategy.md) | Accepted |
| 0018 | [Platform ports layer (`app/platform/`)](0018-platform-ports-layer.md) | Accepted |
| 0019 | [`ai_governance` module: cost, quota, allowlists](0019-ai-governance-module.md) | Accepted |
| 0020 | [Golden-path vertical slice (documents → RAG)](0020-golden-path-vertical-slice.md) | Accepted |
| 0021 | [Repository rename: `ai-backend-foundation`](0021-repository-rename-to-foundation.md) | Accepted |
| 0022 | [Promote Arq to Phase 2 (supersedes 0009)](0022-promote-arq-to-phase-2.md) | Accepted |

## Template

```markdown
# ADR-NNNN: <Title>

- **Status**: Proposed | Accepted | Superseded by ADR-XXXX
- **Date**: YYYY-MM-DD
- **Deciders**: <names or roles>

## Context
What problem are we solving? What forces are at play?

## Decision
The decision, in one paragraph.

## Consequences
Positive, negative, neutral. Be honest about the negatives.

## Alternatives considered
Each alternative, briefly, and why we rejected it.
```
