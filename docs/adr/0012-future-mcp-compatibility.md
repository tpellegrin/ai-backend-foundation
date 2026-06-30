# ADR-0012: Forward-compatible MCP (Model Context Protocol) support

- **Status**: Accepted
- **Date**: 2026-06-29

## Context

The Model Context Protocol (MCP) is becoming the de-facto interop layer between LLM clients and external tools/resources. We do not need to ship an MCP server in Phase 2, but we must not paint ourselves into a corner that makes adding one expensive later.

## Decision

- **Tool model alignment**. Tools in `app.ai.tools` are typed callables with:
  - a stable name,
  - a Pydantic input schema,
  - a Pydantic output schema,
  - a human-readable description,
  - an optional capability/scope tag.

  This is a near-superset of what an MCP tool descriptor needs. The `ToolRegistry` will be able to project its tools to MCP tool descriptors with no behavior change.

- **Resource model alignment**. Documents and retrieved chunks in `app.documents` and `app.rag` carry stable identifiers and URIs. These map naturally to MCP resources.

- **Future modules** (not in Phase 2 scope):
  - `app.ai.mcp.server` — exposes a curated subset of our tools and resources as an MCP server endpoint.
  - `app.ai.mcp.client` — consumes external MCP servers and registers their tools/resources into our `ToolRegistry` at startup, **as adapters**. External MCP servers are external dependencies; they go through the same observability and policy gates as any other tool.

- **Security**: MCP-exposed tools must declare an explicit allowlist (per-tenant or global). Implicit exposure is forbidden.

## Consequences

**Positive**: zero retrofit cost when MCP becomes a product requirement; cleanly separates our internal tool model from the wire protocol.
**Negative**: a small ongoing discipline of keeping tool schemas declarative and capability-tagged.
**Neutral**: we do not depend on any MCP SDK in Phase 2.

## Alternatives considered

- **Ignore MCP for now**: viable but risks coupling our tool model to PydanticAI specifics, then retrofitting later. Avoided cheaply by alignment now.
- **Adopt MCP as the internal tool model**: premature; the protocol is still evolving and our internal needs (typed Python tools, DI) are richer than wire-level MCP.
