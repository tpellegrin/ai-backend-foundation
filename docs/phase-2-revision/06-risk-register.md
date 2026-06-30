# Top 10 Architecture Risks

> Read this as: "things that could make the architecture wrong, not just the code." Each entry has a likelihood, an impact, a leading indicator, and a planned mitigation already encoded in the design.

| # | Risk | Likelihood | Impact | Leading indicator | Mitigation already in the design |
| - | ---- | ---------- | ------ | ----------------- | -------------------------------- |
| R-1 | **Uncontrolled LLM spend** — a runaway loop or misconfigured prompt drives 100× normal cost overnight. | High | Severe (financial + reputational) | Daily cost per tenant trending non-linear; `usage_entries` count spiking | `ai_governance` checks every LLM call **before** invocation; hard-deny on budget; `LLMCallObservation` per call; alerting on cost slope; circuit breaker via `pick_fallback`. |
| R-2 | **Provider lock-in via leaked SDK types** — `openai.ChatCompletionMessage` leaks into `app.rag` and the port becomes ceremonial. | Medium | High (forces rewrite at provider swap) | Any import of an SDK type outside `infrastructure/llm_providers/*` | `ChatModel` Protocol defines its own `Message`/`ToolCall`/`ChatResult`; import-linter forbids SDK imports outside adapter folder; contract tests run on every adapter. |
| R-3 | **PydanticAI churn** — breaking API change in PydanticAI forces touching every agent. | Medium | Medium | Frequent CHANGELOG breaks in PydanticAI; agent code importing PydanticAI symbols directly | `app.ai.agent_runner` is the **only** importer of PydanticAI; everything else uses the `AgentRunner` facade. Pinned version. |
| R-4 | **pgvector recall/latency wall** at >10M vectors or hybrid-search demand. | Medium | High | p95 retrieval latency rising; recall@k dropping on eval set | `VectorStore` port already abstracts; Qdrant adapter ships in Phase 3 with contract-test parity; hybrid retrieval stage is a pipeline stage, not a rewrite. |
| R-5 | **Background-job invisibility** — Arq job fails silently, document stays in `processing` forever. | Medium | High (user-visible breakage) | Documents stuck in `processing`; no `ready/failed` transitions; worker logs absent | Arq adapter emits OTel spans + structured logs with `job_id/attempt/request_id`; `documents` row updated on each transition; readiness probe on worker; integration test asserts the full lifecycle. |
| R-6 | **Prompt drift** — a "small wording tweak" silently regresses RAG quality. | High | High | Eval scores diverge from production traces; same `prompt_id` with different content live | Prompts are versioned artifacts (`prompt_id@version`); every `LLMCallObservation` records the version; evals (Phase 3) gate on regressions; admin endpoint exposes live prompt content. |
| R-7 | **Secrets leakage through error responses or logs** — provider raw response bubbles into Problem Details. | Medium | Severe (compliance + security) | Stack traces in 5xx; raw JSON from providers in logs | Single error middleware maps to RFC 9457 with a whitelist of fields; `SecretStr` everywhere; `detect-secrets` pre-commit; tests assert no secret-shaped strings in error payloads. |
| R-8 | **Boundary erosion** — a module imports another module's `persistence.py` "just this once" and the graph rots. | High | High (slow but irreversible) | import-linter violations being ignored; PRs touching multiple modules' persistence | import-linter contracts in CI (§03), each contract named; ADR required for new edge; `__init__.py` is the only public surface. |
| R-9 | **Embedding-dim or model-version mismatch** — corpus embedded with model A, queries embedded with model B. | Medium | High (silent quality collapse) | Recall drops post-deploy; cosine distances clustered abnormally | `embeddings` model identifier persisted in `chunks` row; query path asserts equality; migration documented; runbook in Phase 3. |
| R-10 | **Async-path sync I/O contamination** — a blocking call slips into a request handler (e.g., `requests`, `time.sleep`, sync DB driver). | Medium | High (latency cliff under load) | Event-loop lag in OTel; p99 latency spikes uncorrelated with downstream | Ruff rules ban `requests`, sync `psycopg2`, `time.sleep` in `app/`; httpx everywhere; integration test under concurrency asserts steady p99. |

---

## Risks consciously deferred

- **Microservice extraction**: not a risk at Phase 2 scale; revisit at >50 engineers or hard team-boundary problems.
- **Custom DI container**: deliberately not adopted; FastAPI `Depends` + `Container` dataclass is enough until proven otherwise (ADR-0017).
- **Real-time multi-modal**: out of scope; would require a different transport story (WebRTC) and a different backpressure model.

## Risk review cadence

This register is reviewed at every phase boundary and whenever an incident touches one of its entries. New risks go in by PR. Removed risks are kept in `docs/phase-2-revision/history/`.
