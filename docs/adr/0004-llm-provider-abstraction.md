# ADR-0004: LLM provider abstraction (`ChatModel` port)

- **Status**: Accepted
- **Date**: 2026-06-29

## Context

Provider markets (OpenAI, Anthropic, Google, Azure, Bedrock, Groq, Together, vLLM, Fireworks, …) shift rapidly. SOTA models, prices, latencies, and tool-calling formats all change on month-scale. An AI product that calls one SDK directly becomes a rewrite the moment a better/cheaper model appears.

## Decision

- Define a **`ChatModel`** Protocol in `app.llm.ports`:
  - `async def complete(messages, *, tools=None, response_model=None, **opts) -> ChatResult`
  - `def stream(messages, *, tools=None, response_model=None, **opts) -> AsyncIterator[ChatChunk]`
  - Inputs and outputs are **our** typed domain objects (`Message`, `ToolCall`, `ChatResult`, `ChatChunk`, `Usage`, `Cost`), not provider SDK types.
- Define a **`ModelRouter`** Protocol that selects a `ChatModel` by capability/cost/latency hints. Default implementation is config-driven (round-robin, or by tag). Routing is optional; small apps use a single configured model.
- Provider **adapters** live in `app.infrastructure.llm_providers.{openai,anthropic,gemini,openai_compatible}`. Each adapter:
  - implements `ChatModel`,
  - normalizes tool-calling and structured-output formats,
  - records an `LLMCallObservation` (tokens, cost, latency, status, prompt_id@version) on every call (see [ADR-0001](0001-observability-stack-structlog-otel.md)),
  - retries with backoff on transient errors via a shared `infrastructure/http` resilience layer (httpx + tenacity).
- **PydanticAI** (see [ADR-0006](0006-pydanticai-as-agent-runtime.md)) is the agent runtime sitting **on top** of `ChatModel` for higher-level use cases. Direct `ChatModel.complete()` remains available for stateless calls.
- **OpenAI-compatible endpoints** (Groq, Together, Fireworks, Azure OpenAI, vLLM, LM Studio, Ollama) share a single adapter parameterized by base URL, API key, and model id.

## Consequences

**Positive**: swap providers via config; consistent observability across providers; product code never imports a provider SDK; multi-provider routing/fallback is a small additive feature.
**Negative**: we own a translation layer for tool-calling and structured-output quirks. The cost is bounded because PydanticAI handles much of it.
**Neutral**: we expose only the subset of provider parameters we support. Rare provider-specific features are reachable via an `opts` escape hatch with an explicit warning that it is provider-specific.

## Alternatives considered

- **LiteLLM as the single multiplexer**: borrows the same idea but takes a runtime dependency we can't reshape; we prefer to own the abstraction.
- **No abstraction, single SDK**: rejected — provider lock-in is the most expensive form of debt in AI products today.
