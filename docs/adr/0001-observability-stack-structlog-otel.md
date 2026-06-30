# ADR-0001: Observability stack — structlog + OpenTelemetry

- **Status**: Accepted
- **Date**: 2026-06-29

## Context

An AI backend's failure modes are subtle: a prompt regressed, a provider got slower, retrieval recall dropped, tokens-per-request quietly tripled. Generic application logs do not catch this. We need structured, correlated signals from day one: traces around external calls, metrics for tokens/cost/latency, and structured logs that join all three.

## Decision

- Use **`structlog`** as the only logging entrypoint. JSON renderer in non-dev environments; console renderer in dev. All logs carry `request_id`, `tenant_id` (when present), `user_id` (when present), `span_id`, and `trace_id`.
- Use **OpenTelemetry** for traces and metrics. Auto-instrument FastAPI, SQLAlchemy, httpx, Redis. Add manual spans around LLM calls and RAG stages with explicit attributes (`gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `app.prompt.id`, `app.prompt.version`, `app.cost.usd`, semantic conventions where available).
- Export via OTLP to an **OpenTelemetry Collector** sidecar (local in Compose, vendor of choice in prod).
- Correlation ID middleware: read `X-Request-ID` or generate ULID; set in a contextvar; emit on every log and propagate downstream HTTP.
- Health probes split into `/livez` (process), `/readyz` (deps reachable), `/healthz` (alias of livez for k8s default).
- A first-class `LLMCallObservation` record (provider, model, prompt_id@version, tokens, cost_usd, latency_ms, status) is emitted as a structured log **and** as OTel metric/span attributes. This is the substrate for evals, billing, and budget guards.

## Consequences

**Positive**: vendor-neutral observability; one consistent way to log; LLM-specific signals available from day one; future SLOs and budget guards are trivial to build on top.
**Negative**: OTel collector is one more local service; learning curve for structlog processors.
**Neutral**: Sentry remains a complementary error tracker if a product wants it; it plugs in via OTel SDK or its own SDK.

## Alternatives considered

- **stdlib logging only**: works, verbose to configure, no structured ergonomics.
- **loguru**: nice DX, weaker OTel correlation story, opinionated globals.
- **Vendor APM agent (Datadog/New Relic)**: lock-in; we keep the option by switching collector exporters.
