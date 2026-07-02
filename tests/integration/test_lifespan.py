from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Response, status
from httpx import ASGITransport, AsyncClient

from app.core.di import get_container, get_probe_registry, get_settings
from app.core.lifespan import lifespan
from app.observability.health import ProbeRegistry, build_health_router


@pytest.fixture
def valid_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    vars_dict = {
        "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
        "REDIS_URL": "redis://localhost:6379/0",
        "ARQ_REDIS_URL": "redis://localhost:6379/1",
        "JWT_PRIVATE_KEY": "fake-private-key",
        "JWT_PUBLIC_KEY": "fake-public-key",
        "JWT_ISSUER": "ai-backend-foundation",
        "JWT_AUDIENCE": "ai-backend-foundation",
        "OPENAI_API_KEY": "sk-placeholder",
        "OPENAI_CHAT_MODEL": "gpt-4o",
        "OPENAI_EMBEDDING_MODEL": "text-embedding-3-small",
        "BLOB_STORAGE_BACKEND": "local",
        "BLOB_LOCAL_DIR": "./.storage",
        "LLM_MONTHLY_BUDGET_USD": "100.0",
        "LLM_MODEL_ALLOWLIST": "gpt-4o,gpt-4o-mini",
    }
    for k, v in vars_dict.items():
        monkeypatch.setenv(k, v)


@pytest.mark.integration
async def test_lifespan_lifecycle(valid_env_vars: None) -> None:
    """Test that the lifespan correctly manages the container and readiness flag.

    Verifies:
    - Container is populated on startup.
    - Probe registry is initially empty.
    - app.state.ready flips from False to True and back to False.
    - /readyz returns 503 before startup and 200 after.
    """
    app = FastAPI(lifespan=lifespan)

    # Use a proxy for the registry since it's created during lifespan
    class RegistryProxy:
        async def run_all(self) -> list:
            if not hasattr(app.state, "container"):
                return []
            return list(await app.state.container.probe_registry.run_all())

    # Wire health router against app state
    router = build_health_router(
        registry=RegistryProxy(),  # type: ignore[arg-type] # RegistryProxy implements subset of ProbeRegistry required for test
        is_ready=lambda: getattr(app.state, "ready", False),
    )
    app.include_router(router)

    # 1. Before startup: /readyz returns 503
    # We test the handler directly because AsyncClient would trigger startup.
    readyz_route = next(r for r in router.routes if r.path == "/readyz")
    handler = readyz_route.endpoint
    response = Response()
    res = await handler(response)
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert res == {"status": "starting"}

    # 2. During/After startup
    async with lifespan(app):
        # After startup completed
        assert app.state.ready is True
        assert hasattr(app.state, "container")
        assert app.state.container.settings is not None
        assert isinstance(app.state.container.probe_registry, ProbeRegistry)
        assert len(app.state.container.probe_registry.probes) == 0

        # Verify dependency providers in di.py
        mock_request = MagicMock()
        mock_request.app = app
        container = get_container(mock_request)
        assert container == app.state.container
        assert get_settings(container) == container.settings
        assert get_probe_registry(container) == container.probe_registry

        # Now we can use AsyncClient to test endpoints
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Verify /readyz is 200
            response_api = await client.get("/readyz")
            assert response_api.status_code == status.HTTP_200_OK
            assert response_api.json() == {"status": "ok"}

            # Verify /healthz is 200
            response_api = await client.get("/healthz")
            assert response_api.status_code == status.HTTP_200_OK
            assert response_api.json() == {"status": "ok"}

    # 3. After shutdown
    assert app.state.ready is False
