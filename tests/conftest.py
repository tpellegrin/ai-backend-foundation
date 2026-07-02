"""Repository-wide pytest bootstrap.

This is the ONLY shared ``conftest.py`` in the repository. It exists for
exactly one reason and MUST NOT grow beyond that reason:

    Guarantee that ``pytest`` can *collect* the test tree even when it
    triggers side effects that construct ``app.core.config.settings.AppSettings``
    at import time.

Background
----------

Per ADR-0023 the composition root lives at ``app.main``. Per T-506 the ASGI
binding ``app = create_app()`` runs at ``import app.main`` time. That means
any test file that imports anything from ``app.main.*`` (directly or
transitively) will construct ``AppSettings`` **during pytest collection**,
which happens *before* any test-scoped ``monkeypatch`` fixture is able to
set environment variables. Without a minimal env in place at collection
time, ``AppSettings`` raises ``pydantic.ValidationError`` (missing
``DATABASE_URL`` etc.), collection aborts, and the whole run turns red.

Ordinary test-local fixtures (``monkeypatch.setenv`` inside an autouse
fixture) cannot solve this: they run at test-execution time, not at
collection/import time. The only correct fix is to seed a minimal
environment *before* any ``app.*`` module is imported for collection —
which is what a repository-wide ``conftest.py`` at ``tests/`` (the rootdir
``conftest``) does automatically.

Scope rules (binding)
---------------------

1. This file is a permanent part of the repository structure. Tasks may
   assume it exists and do the right thing.
2. This file does exactly one thing: it calls ``os.environ.setdefault``
   for each variable the ``AppSettings`` schema declares as required.
   Values are obvious, non-production placeholders. ``setdefault`` means a
   real value already present in the environment (CI secrets, developer
   ``.env``) always wins.
3. This file is the ONLY sanctioned use of ``os.environ`` outside
   ``app/core/config/``. See ``docs/implementation/rules.md`` §3 rule 8
   and §4 for the carve-out.
4. This file is NOT a place for shared fixtures, factories, mocks, fakes,
   or helpers. Those still live inside the test file that consumes them
   (see ``docs/implementation/patterns.md`` P-10 / AP-6). If a second
   consumer appears, promote to a scoped ``conftest.py`` inside the
   module's ``tests/`` directory — never here.
5. This file changes only when the ``AppSettings`` schema gains a new
   *required* field. The task that introduces that field must list
   ``tests/conftest.py`` in its ``Allowed files`` and add the
   corresponding ``setdefault`` line here in the same commit.
6. Values here MUST NOT be secrets or resemble production credentials.
   Every value must be recognizable as a test placeholder.
"""

from __future__ import annotations

import os

# Minimum env required to import `app.main` (which eagerly calls
# `create_app()` per T-506) without tripping `AppSettings` validation.
# Keep this list aligned with the required (non-defaulted) fields of
# `app.core.config.settings.AppSettings`. Optional fields (those with a
# `default=`) are intentionally omitted.
_MINIMAL_TEST_ENV: dict[str, str] = {
    # Database
    "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
    # Redis / Arq
    "REDIS_URL": "redis://localhost:6379/0",
    "ARQ_REDIS_URL": "redis://localhost:6379/1",
    # JWT (obvious placeholders; NOT valid keys)
    "JWT_PRIVATE_KEY": "test-placeholder-private-key",
    "JWT_PUBLIC_KEY": "test-placeholder-public-key",
    "JWT_ISSUER": "ai-backend-foundation-test",
    "JWT_AUDIENCE": "ai-backend-foundation-test",
    # OpenAI (placeholder; providers are stubbed in tests)
    "OPENAI_API_KEY": "sk-test-placeholder",
    "OPENAI_CHAT_MODEL": "gpt-4o",
    "OPENAI_EMBEDDING_MODEL": "text-embedding-3-small",
    # Blob storage (local backend, ephemeral dir under project)
    "BLOB_LOCAL_DIR": "./.storage-test",
    # LLM governance
    "LLM_MONTHLY_BUDGET_USD": "100.0",
    "LLM_MODEL_ALLOWLIST": "gpt-4o,gpt-4o-mini",
}

for _key, _value in _MINIMAL_TEST_ENV.items():
    os.environ.setdefault(_key, _value)
