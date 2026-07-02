# ADR-0023: Composition-root ownership — `create_app()` in `app.main`, lifespan mutates in place

- **Status**: Accepted
- **Date**: 2026-07-02
- **Deciders**: Architecture review (T-505 FAIL review remediation)

## Context

Task T-505 as originally written placed `create_app()` in `app/core/app_factory.py`. The factory is required to mount routers from `app.api.v1` (T-503) and register exception handlers from `app.api.errors` (T-501). Both live in `app.api`, which sits at layer L5 (edge) — strictly **above** `app.core` (L4, composition) in the layer contract fixed by `AGENTS.md` §3 and enforced by `importlinter.toml` (ADR-0011).

No correct implementation of T-505-as-written can satisfy the Layers contract: `app.core → app.api` inverts the layer order. The implementer's workaround — adding `ignore_imports` to `.importlinter` — silences the contract instead of respecting it, and is rejected.

A second, independent contradiction exists between T-504 and T-505: T-504's lifespan constructs the `Container` and `ProbeRegistry` at startup and assigns them to `app.state.container`, while T-505's factory closes the health router over `container.probe_registry` **at construction time**. The health router therefore captures an empty registry that is discarded when the lifespan installs its own `Container`. Every probe appended by later wiring tasks (T-701, T-702/T-708, T-1402, T-1503) lands on the lifespan's registry and is invisible to `/readyz`. This is a silent observability defect masquerading as a working health endpoint.

## Decision

1. **Composition root lives in `app.main`, not `app.core`.**
   `create_app()` moves from `app/core/app_factory.py` to `app/main/app_factory.py`. `app.main` is the edge layer (L5) and is already allowed to import `app.core` and `app.api`. No new layer edge is introduced; no `.importlinter` weakening is required. `app.main:app = create_app()` remains the ASGI entrypoint.

2. **`create_app()` owns initial `Container` and `ProbeRegistry` construction.**
   The factory constructs a `Container` populated with `settings` (from `get_settings()`) and an **empty** `ProbeRegistry`, and assigns the container to `app.state.container` **before** the lifespan is attached. The health router closes over `app.state.container.probe_registry` at construction time. This is the same registry instance that every later wiring task mutates.

3. **`lifespan` mutates the existing `Container` in place.**
   `app.core.lifespan` reads `app.state.container` (installed by the factory), runs `await on_startup(container)` hooks, and manages `app.state.ready`. It **must not** construct a new `Container` or `ProbeRegistry`, and **must not** reassign `app.state.container`. Later wiring tasks (T-701, T-702/T-708, T-1212, T-1402, T-1503) append their fields to the same `Container` instance and their probes to the same `ProbeRegistry` instance.

4. **No `app.core → app.api` import exceptions.**
   The Layers contract in `importlinter.toml` remains untouched. Any future contradiction between a task spec and the layer contract must be reconciled at the spec level, not by weakening the contract.

## Consequences

**Positive**

- The layer contract is preserved; `.importlinter` needs no `ignore_imports` shims.
- The `ProbeRegistry` observed by the health router is the same object every wiring task mutates; `/readyz` reports the true readiness of all wired dependencies.
- Ownership of the composition root is unambiguous: `app.main` builds and holds it; `app.core` supplies the building blocks (`Container`, `lifespan`, `di`, `wiring`); `app.core` never imports upward.
- Later wiring tasks retain their "append one field + one probe" contract without change to the incremental-`Container` model documented in `IMPLEMENTATION_PLAN.md`.

**Negative**

- `app/main/` becomes a small package (not a single `main.py` file) housing `__init__.py`, `app_factory.py`, the ASGI `app` binding, and `tests/`. `docs/folder-structure.md` is updated accordingly.
- T-504 and T-505 task specs must be amended; T-504's lifespan is now smaller (no construction responsibility) and T-505's `Allowed files` list changes path.

## Alternatives considered

- **Keep `create_app()` in `app.core` and add an `ignore_imports` line to `.importlinter`.** Rejected. The Layers contract is not advisory. Silencing it hides the real problem (composition root misplaced) and normalises weakening contracts to unblock tasks.
- **Introduce a layer-neutral re-export shim (e.g., `app.core.app_factory` re-exports from a hidden module that dynamically imports `app.api`).** Rejected. Creates a second composition site, multiplies indirection, and does not shrink cost of change. Fails the AGENTS.md §14 "avoid overengineering" gate.
- **Leave lifespan owning `Container` construction; have the factory read it back after startup.** Rejected. The health router must be wired at app-construction time (before the first request); routers cannot be re-mounted after startup. The registry the router closes over must exist before the lifespan runs.

## Relationship to prior ADRs

- Refines ADR-0016 (vertical-slice modules) and ADR-0017 (dependency-injection strategy) by naming `app.main` as the unique composition root and `app.core` as the composition **library** (Container/lifespan/di/wiring), not the composition **site**.
- Reaffirms ADR-0011 (enforce module boundaries with import-linter): no exceptions to the Layers contract are introduced.

## Follow-ups

- Amend T-504 (`docs/implementation/tasks/T-504.md`): remove `Container`/`ProbeRegistry` construction from `lifespan.py`.
- Amend T-505 (`docs/implementation/tasks/T-505.md`): relocate allowed files to `app/main/app_factory.py` and `app/main/tests/test_app_factory.py`; state factory-owned `Container` construction explicitly.
- Update `docs/folder-structure.md` and `docs/dependency-graph.md` to reflect `app/main/` as a package and the composition-root split.
- Update `IMPLEMENTATION_PLAN.md` T-505 row to point at the new path.
