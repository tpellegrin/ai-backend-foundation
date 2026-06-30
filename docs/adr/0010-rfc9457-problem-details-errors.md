# ADR-0010: RFC 9457 Problem Details for HTTP errors

- **Status**: Accepted
- **Date**: 2026-06-29

## Context

A consistent error contract is a feature: clients can branch on `code`, humans can read `title`/`detail`, operators can find requests by `instance` and `request_id`. Most FastAPI apps ship inconsistent shapes (`{"detail": "..."}`, `{"error": {...}}`, validation errors yet again different). We fix it once.

## Decision

- All non-2xx responses return a **`application/problem+json`** body conforming to **RFC 9457** (the successor to RFC 7807):
  ```json
  {
    "type": "https://errors.example.com/validation",
    "title": "Validation failed",
    "status": 422,
    "detail": "The 'email' field must be a valid address.",
    "instance": "/api/v1/users",
    "code": "VALIDATION_FAILED",
    "request_id": "01J…",
    "errors": [
      { "path": "body.email", "code": "value_error.email", "message": "invalid" }
    ]
  }
  ```
- We add two project-specific extension fields:
  - `code`: a **stable machine-readable identifier** (e.g. `AUTH_INVALID_CREDENTIALS`, `RAG_NO_RESULTS`). Documented in `docs/error-codes.md` (Phase 2).
  - `request_id`: the correlation id (also in the `X-Request-ID` response header).
- One **central exception hierarchy** in `app.shared.errors` (`AppError` with `code`, `http_status`, `title`, optional `detail`, optional `errors`).
- One **central exception handler** in `app.api.errors` maps:
  - `AppError` → its declared status + Problem Details body,
  - Pydantic `ValidationError` → 422 + Problem Details with `errors`,
  - unhandled `Exception` → 500 + opaque Problem Details + structured log + OTel span error,
  - FastAPI `HTTPException` → Problem Details (we wrap Starlette's default).
- **Never** leak internals (stack traces, SQL, provider error bodies) into the `detail` field.

## Consequences

**Positive**: one shape, one place to change it; OpenAPI documents the error model precisely; clients implement one error handler.
**Negative**: a small amount of upfront error catalog work. Worth it.
**Neutral**: `type` URIs do not need to resolve initially; they become real doc pages over time.

## Alternatives considered

- **Ad-hoc `{"detail": "..."}` (FastAPI default)**: rejected — inconsistent across endpoints.
- **GraphQL-style errors array**: not applicable; we are REST-first.
