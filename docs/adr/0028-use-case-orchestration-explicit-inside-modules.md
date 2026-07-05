# ADR-0028: Make use-case orchestration explicit inside bounded modules

- Status: Proposed
- Date: 2026-07-05
- Supersedes: none
- Superseded by: none
- Related: ADR-0027 (pragmatic ports-and-adapters over strict Clean Architecture rings)

## Context

ADR-0027 keeps the repository organized around bounded modules rather than strict Clean Architecture ring folders.

That decision preserves locality, but it introduces an important responsibility: each module must keep its internal orchestration understandable. If a module only has generic files such as `service.py`, there is a risk that those files become broad, unstructured coordination points.

Strict Clean Architecture makes use cases explicit by placing them in a use-case ring. This project does not adopt that global folder structure, but it should still preserve the useful idea: product workflows should be named and reviewable.

Examples of important workflows include:

- uploading a document;
- ingesting a document;
- extracting text;
- chunking content;
- generating embeddings;
- storing vectors;
- answering a RAG question;
- checking model governance;
- auditing model usage.

These are not merely technical helpers. They are application use cases or orchestration flows.

The project needs a convention for making these flows explicit without forcing every module into a heavy Clean Architecture folder layout.

## Decision

Use-case orchestration should be explicit inside bounded modules when a workflow becomes non-trivial.

A bounded module may use one of these shapes:

1. A clear module-level service when the flow is simple.

   Example:

    - `app.rag.service`
    - `app.documents.service`

2. A module-local `use_cases/` package when the module has multiple distinct workflows.

   Example:

    - `app.documents.use_cases.upload_document`
    - `app.documents.use_cases.ingest_document`
    - `app.rag.use_cases.answer_question`
    - `app.ai_governance.use_cases.check_budget`

The project will not introduce a global top-level `app.use_cases` package by default.

Use cases remain owned by their bounded module.

## Rules

1. API handlers should not orchestrate business workflows directly.

   API handlers should:

    - validate and parse request input;
    - call a module service or use case;
    - translate the result into an API response.

2. Use cases may depend on ports, module services, and domain/capability types.

3. Use cases must not depend directly on concrete infrastructure adapters.

4. Use cases must not depend on FastAPI request/response objects.

5. Use cases should expose business-oriented inputs and outputs, not framework objects.

6. A module should introduce `use_cases/` only when it improves clarity.

7. Do not create use-case files for trivial one-line delegation.

## Consequences

### Positive

- Preserves the main Clean Architecture benefit of explicit use-case orchestration.
- Avoids global ring folders that scatter feature concepts.
- Keeps task scopes local to the module being implemented.
- Makes complex AI workflows easier to review.
- Prevents API handlers from becoming business orchestration code.
- Prevents module `service.py` files from growing without structure.

### Neutral

- Some modules may use `service.py`, while more complex modules may use `use_cases/`.
- The repository will not have one uniform use-case folder for all workflows.
- Reviewers must judge whether a workflow is complex enough to justify a use-case file.

### Negative

- There is some subjectivity in deciding when to introduce `use_cases/`.
- Too many tiny use-case files could create ceremony.
- Too few use-case files could lead to large services.

## Alternatives considered

### 1. Require `use_cases/` in every module

Rejected.

This is too much ceremony for simple modules and early foundation work. Some modules only need ports, settings, small services, or simple primitives.

### 2. Use a global `app.use_cases` package

Rejected.

This weakens module ownership and scatters bounded concepts away from the modules that own them.

### 3. Keep only generic `service.py` files

Rejected as a universal rule.

This is simple at first, but complex workflows can accumulate in large service files and become harder to review.

### 4. Introduce module-local use cases only when needed

Accepted.

This balances clarity and locality.

## Implementation notes

A good use-case module name should describe a workflow, not a technical operation.

Prefer:

- `answer_question`
- `ingest_document`
- `generate_embeddings`
- `check_model_budget`

Avoid vague names:

- `manager`
- `handler`
- `processor`
- `helper`
- `utils`

A use-case class or function should make dependencies explicit.

Example shape:

    class AnswerQuestion:
        def __init__(
            self,
            *,
            chat_model: ChatModel,
            vector_store: VectorStore,
            prompt_registry: PromptRegistry,
            governance_gate: GovernanceGate,
        ) -> None:
            ...

The exact style may vary by module, but concrete infrastructure dependencies must not appear in the use-case constructor.

## Review guidance

A reviewer should ask:

- Is orchestration happening in the API layer?
- Is the module service becoming too broad?
- Would a named use case make the workflow easier to test?
- Does the use case depend on ports rather than concrete adapters?
- Are FastAPI, SQLAlchemy, Redis, OpenAI SDK, or provider-specific types leaking into the use case?
- Is the proposed `use_cases/` package justified by real workflow complexity?

## Summary

The project keeps bounded module ownership while adopting Clean Architecture’s useful emphasis on explicit use cases.

Use cases live inside the module that owns the workflow. They are introduced when they improve clarity, not as mandatory ceremony.
