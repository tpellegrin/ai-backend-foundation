# ADR-0002: Authentication — JWT (asymmetric) + Argon2id

- **Status**: Accepted
- **Date**: 2026-06-29

## Context

We need an auth foundation that:
- works for a single deployable today,
- is safe to extend to multiple services later (signature verification across processes),
- supports refresh-token rotation,
- is replaceable by OIDC/SSO without touching domain modules,
- uses current best-practice password hashing.

## Decision

- **Access tokens**: short-lived JWTs (≤ 15 min) signed with **EdDSA (Ed25519)**; **RS256** is permitted where Ed25519 is unsupported. **HS256 is forbidden** in any deployment where verifiers and signers are not the same process.
- **Refresh tokens**: opaque high-entropy tokens (≥ 256 bits), stored **hashed** in Postgres with rotation and reuse detection (re-using an old refresh token revokes the family).
- **Password hashing**: **Argon2id** via `argon2-cffi`, with parameters tuned for ≥ 250 ms on production hardware. Hashes are stored with a versioned prefix so parameters can be increased over time and re-hashed on next login.
- **Ports** (in `app.auth.ports`): `IdentityProvider`, `TokenSigner`, `PasswordHasher`. The auth module never imports concrete adapters.
- **Default adapters** (in `app.auth.adapters`): `Argon2PasswordHasher`, `JwtTokenSigner`, `LocalIdentityProvider`. An OIDC adapter (e.g., Auth0/Keycloak/Cognito) plugs in later without changing domain code.
- **Authorization** is separate from authentication. Policies live in `app.auth.policies` (RBAC now, ABAC-ready). Resource-level checks happen in services, not in routes.

## Consequences

**Positive**: future SSO is additive; signature verification works across services; password hashing meets 2025 best practice; refresh-token reuse detection mitigates token theft.
**Negative**: asymmetric keys require a small key-management story (JWKS endpoint, rotation). We document it; it's a one-page runbook.
**Neutral**: short-lived access tokens mean clients must implement refresh — this is desirable, not an accident.

## Alternatives considered

- **Opaque session tokens with a sessions table**: simpler, but worse for multi-service futures and harder for stateless edge verification.
- **HS256**: acceptable in single-process apps; rejected because the foundation must scale to multiple verifiers.
- **bcrypt**: acceptable; Argon2id is strictly better in 2025 and is what OWASP recommends as the default.
