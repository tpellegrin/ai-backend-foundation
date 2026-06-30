# ADR-0008: Prompt management and versioning

- **Status**: Accepted
- **Date**: 2026-06-29

## Context

Prompts are the most volatile, most consequential artifacts in an AI product. They get tweaked daily, regressions are silent, and "what prompt was in production when this happened?" is the single hardest question to answer in incident response. Inline f-strings make all of this impossible.

## Decision

- Prompts are **first-class artifacts**, owned by `app.prompts`. They are not strings sprinkled in code.
- Each prompt has:
  - a stable `id` (e.g., `rag.answer`),
  - a **semantic version** (`MAJOR.MINOR.PATCH`),
  - a Pydantic **input schema** (variables the template accepts),
  - an optional Pydantic **output schema** (when used with structured outputs),
  - a **template** (Jinja2 with strict undefined),
  - declared **target model capabilities** (e.g. supports tool calls, json mode),
  - optional **eval references** (path to golden datasets).
- Storage:
  - **Source of truth**: files in `app/prompts/library/<prompt_id>/<version>.yaml` (frontmatter + template). Reviewed in PRs.
  - **Optional DB-backed overrides** (Phase 3+) for live editing in admin UIs. Overrides carry the same schema and are versioned. Production never silently picks an override without a feature flag and an audit log entry.
- API:
  - `PromptRegistry.get(id, *, version="latest") -> PromptVersion`
  - `PromptVersion.render(inputs) -> RenderedPrompt` (validates inputs via the Pydantic schema, returns a typed object).
- Every LLM call records `prompt_id@version` in the `LLMCallObservation` (see [ADR-0001](0001-observability-stack-structlog-otel.md)). This is the join key for evals, incident analysis, and cost attribution.
- **Versioning rules**:
  - MAJOR: input/output schema breaking change.
  - MINOR: meaningful behavioral change (new instruction, new examples, restructured output).
  - PATCH: typo, formatting, no semantic change expected.
- **Eval gate** (Phase 3): MINOR/MAJOR bumps run the prompt's tagged eval set in CI. Threshold drops fail the PR.

## Consequences

**Positive**: every production output is reproducible to a specific prompt version; A/B tests are a routing concern, not a prompt-management concern; evals are wired in by design.
**Negative**: a tiny upfront cost (yaml + schema) that pays back the first time a prompt regresses.
**Neutral**: non-trivial prompts may want partials/macros — Jinja2 supports it; we will conventionalize a `partials/` directory if needed.

## Alternatives considered

- **Inline f-strings**: rejected — see context.
- **External prompt SaaS (Langfuse, PromptLayer, Humanloop)**: complementary, not a substitute; can integrate via an additional `PromptRegistry` adapter without changing consumers.
