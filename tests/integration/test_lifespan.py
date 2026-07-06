from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Response, status
from httpx import ASGITransport, AsyncClient

from app.core.config.settings import get_settings as bootstrap_settings
from app.core.container import Container
from app.core.di import get_container, get_probe_registry, get_settings
from app.core.lifespan import lifespan
from app.core.wiring import cache, db
from app.observability.health import (
    Probe,
    ProbeRegistry,
    ProbeResult,
    build_health_router,
)


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


@pytest.fixture(autouse=True)
def mock_db_wiring(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock DB wiring to avoid needing a real database in integration tests."""
    # Mock setup_db to return a mock engine and session factory
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    mock_session_factory = MagicMock()

    monkeypatch.setattr(db, "setup_db", lambda _: (mock_engine, mock_session_factory))

    # Mock DBProbe.check to always return OK
    monkeypatch.setattr(
        db.DBProbe, "check", AsyncMock(return_value=ProbeResult(name="db", status="ok"))
    )


@pytest.fixture(autouse=True)
def mock_cache_wiring(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock Redis/Cache wiring to avoid needing a real Redis in integration tests."""
    mock_client = MagicMock()
    mock_client.aclose = AsyncMock()
    mock_cache_adapter = MagicMock()

    monkeypatch.setattr(cache, "setup_redis_client", lambda _: mock_client)
    monkeypatch.setattr(cache, "setup_cache", lambda _: mock_cache_adapter)

    # Mock RedisProbe.check to always return OK
    monkeypatch.setattr(
        cache.RedisProbe, "check", AsyncMock(return_value=ProbeResult(name="redis", status="ok"))
    )


@pytest.mark.integration
async def test_lifespan_lifecycle(valid_env_vars: None) -> None:
    """Test that the lifespan correctly manages the container and readiness flag.

    Verifies:
    - Container identity is preserved (pre-constructed).
    - Readiness transitions from False -> True -> False.
    - Health router correctly uses the container's probe registry.
    - Probes added before startup are visible after startup.
    """
    # 1. Setup pre-constructed container (mirroring app factory)
    settings = bootstrap_settings()
    registry = ProbeRegistry([])
    container = Container(settings=settings, probe_registry=registry)

    app = FastAPI(lifespan=lifespan)
    app.state.container = container
    app.state.ready = False

    # 2. Wire health router using Container's ProbeRegistry
    router = build_health_router(
        registry=container.probe_registry,
        is_ready=lambda: getattr(app.state, "ready", False),
    )
    app.include_router(router)

    # 3. Add a probe before startup
    mock_probe = MagicMock(spec=Probe)
    mock_probe.name = "test_probe"
    mock_probe.check = AsyncMock(return_value=ProbeResult(name="test_probe", status="ok"))
    # Append to the registry instance (must not replace registry instance)
    container.probe_registry._probes += (mock_probe,)  # type: ignore[attr-defined]

    # 4. Verify identity and initial state
    assert app.state.container is container
    assert app.state.ready is False

    # Check /readyz before startup (503)
    readyz_route = next(r for r in router.routes if r.path == "/readyz")
    handler = readyz_route.endpoint
    response = Response()
    res = await handler(response)
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert res == {"status": "starting"}

    # 5. Execute lifespan
    async with lifespan(app):
        # Verify identity preserved during startup
        assert app.state.container is container
        assert app.state.ready is True

        # Verify probe is visible and /readyz is 200
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/readyz")
            assert resp.status_code == status.HTTP_200_OK
            assert resp.json() == {"status": "ok"}
            mock_probe.check.assert_called()

            # Verify /healthz is also 200
            resp_health = await client.get("/healthz")
            assert resp_health.status_code == status.HTTP_200_OK

        # Verify dependency providers in di.py
        mock_request = MagicMock()
        mock_request.app = app
        injected_container = get_container(mock_request)
        assert injected_container is container
        assert get_settings(injected_container) is container.settings
        assert get_probe_registry(injected_container) is container.probe_registry

    # 6. After shutdown
    assert app.state.container is container
    assert app.state.ready is False

    # Verify /readyz is 503 again
    response = Response()
    res = await handler(response)
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
