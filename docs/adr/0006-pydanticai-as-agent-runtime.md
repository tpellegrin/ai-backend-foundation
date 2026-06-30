# ADR-0006: PydanticAI as the agent runtime

- **Status**: Accepted
- **Date**: 2026-06-29

## Context

We need a typed agent runtime: structured outputs, typed tools, streaming, provider-agnostic. LangChain/LangGraph are powerful but have a churn rate and abstraction cost that does not match this foundation's "must be defensible in five years" bar.

## Decision

- Use **PydanticAI** as the agent runtime inside `app.ai.agents`. Each agent declares:
  - a system prompt (sourced from `app.prompts`, with version),
  - a typed `result_type` (Pydantic model) where structured output is desired,
  - a set of typed tools (Python callables with Pydantic input/output) registered via our `ToolRegistry`.
- PydanticAI's model backends are **wrapped** behind our `ChatModel` port (see [ADR-0004](0004-llm-provider-abstraction.md)). The agent receives a `ChatModel` via DI, not a PydanticAI-specific model object. This means we are never bound to PydanticAI's provider list.
- Streaming is the default surface; agent runs emit a stream of `AgentEvent`s (token deltas, tool calls, tool results, final result). The HTTP edge maps these to SSE.
- Conversation memory is **outside** PydanticAI's runtime, behind our `ConversationStore` port. Agents are stateless functions of `(history, input)`.
- Tools never see HTTP, ORM, or provider SDKs directly. They depend on ports from `app.shared`, `app.infrastructure.*` (via DI), or other modules' public services.

## Consequences

**Positive**: typed agents end-to-end; structured outputs without regex-on-JSON; provider-agnostic via our port; observability hooks land naturally on the agent loop and on individual tool calls.
**Negative**: PydanticAI is younger than LangChain; API may shift. We mitigate by wrapping it (our `Agent` class re-exports a minimal surface) and pinning versions.
**Neutral**: more complex workflows (graphs, deterministic state machines) may eventually want LangGraph or a custom orchestrator; we leave room for an additional "workflow" module without changing the `ai/` contract.

## Alternatives considered

- **LangChain/LangGraph**: power vs. cost not justified for the foundation; leaky abstractions; high churn.
- **Instructor only**: solves structured outputs, not agent loops or tools; PydanticAI subsumes it.
- **Roll our own agent loop on top of `ChatModel`**: feasible but reinvents tool-format normalization and streaming plumbing for every provider.
