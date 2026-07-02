# ruff: noqa: S101, PLR2004
import pytest
from starlette.middleware.cors import CORSMiddleware
from starlette.testclient import TestClient

from app.api.security_headers import SecurityHeadersMiddleware
from app.core.config.settings import get_settings
from app.core.container import Container
from app.main.app_factory import create_app
from app.observability.correlation import CorrelationMiddleware
from app.observability.health import ProbeResult
from app.observability.middleware import AccessLogMiddleware


@pytest.fixture(autouse=True)
def mock_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure valid settings for app booting in tests."""
    vars_dict = {
        "APP_ENV": "test",
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

    get_settings.cache_clear()


@pytest.mark.unit
def test_app_boots_and_routes_registered() -> None:
    app = create_app()
    with TestClient(app) as client:
        # Health routes
        assert client.get("/livez").status_code == 200
        assert client.get("/readyz").status_code == 200

        # /api/v1 route
        assert client.get("/api/v1").status_code == 404  # Empty router returns 404


@pytest.mark.unit
def test_container_ownership() -> None:
    app = create_app()
    assert isinstance(app.state.container, Container)
    container_id = id(app.state.container)

    # Ensure it's populated BEFORE lifespan
    assert app.state.container is not None

    with TestClient(app):
        # Identity unchanged during startup
        assert id(app.state.container) == container_id
        assert app.state.ready is True

    # Identity unchanged after shutdown
    assert id(app.state.container) == container_id
    assert app.state.ready is False


@pytest.mark.unit
def test_shared_probe_registry() -> None:
    app = create_app()
    registry = app.state.container.probe_registry

    class FakeProbe:
        name = "fake"

        async def check(self) -> ProbeResult:
            return ProbeResult(name="fake", status="error")

    # Appending a probe via the real API
    registry.add_probe(FakeProbe())

    with TestClient(app) as client:
        response = client.get("/readyz")
        assert response.status_code == 503
        assert response.json()["probes"]["fake"] == "error"


@pytest.mark.unit
def test_middleware_registered_once() -> None:
    app = create_app()
    middleware_list = list(app.user_middleware)
    classes = [m.cls for m in middleware_list]

    # No duplicate middleware classes
    assert len(classes) == len(set(classes))

    # Check order (outermost first in user_middleware list)
    # 1. CorrelationMiddleware
    # 2. AccessLogMiddleware
    # 3. SecurityHeadersMiddleware
    # 4. CORSMiddleware
    assert classes[0] is CorrelationMiddleware  # type: ignore[comparison-overlap] # Starlette Middleware.cls is generic
    assert classes[1] is AccessLogMiddleware  # type: ignore[comparison-overlap] # Starlette Middleware.cls is generic
    assert classes[2] is SecurityHeadersMiddleware  # type: ignore[comparison-overlap] # Starlette Middleware.cls is generic
    assert classes[3] is CORSMiddleware  # type: ignore[comparison-overlap] # Starlette Middleware.cls is generic


@pytest.mark.unit
def test_cors_deny_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_CORS_ALLOWED_ORIGINS", "")
    get_settings.cache_clear()
    app = create_app()
    client = TestClient(app)

    response = client.options(
        "/livez",
        headers={
            "Origin": "https://malicious.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "Access-Control-Allow-Origin" not in response.headers


@pytest.mark.unit
def test_cors_whitelist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_CORS_ALLOWED_ORIGINS", "https://ok.example")
    get_settings.cache_clear()
    app = create_app()
    client = TestClient(app)

    # Whitelisted
    response = client.options(
        "/livez",
        headers={
            "Origin": "https://ok.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers["Access-Control-Allow-Origin"] == "https://ok.example"

    # Denied
    response = client.options(
        "/livez",
        headers={
            "Origin": "https://bad.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "Access-Control-Allow-Origin" not in response.headers


@pytest.mark.unit
def test_security_headers_present() -> None:
    app = create_app()
    client = TestClient(app)
    response = client.get("/livez")

    assert response.headers["Strict-Transport-Security"] == "max-age=63072000; includeSubDomains"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Content-Security-Policy"] == "default-src 'none'"


@pytest.mark.unit
def test_readiness_semantics() -> None:
    app = create_app()
    client = TestClient(app)

    # Before lifespan startup, app.state.ready is False (initialized by factory).
    # Returns 503.
    assert client.get("/readyz").status_code == 503

    # livez works even without state.ready
    assert client.get("/livez").status_code == 200

    # With lifespan context
    with TestClient(app) as booted_client:
        # After startup completes, it's 200
        assert booted_client.get("/readyz").status_code == 200
        assert booted_client.get("/livez").status_code == 200

    # After shutdown, it's 503 (state.ready is False)
    assert client.get("/readyz").status_code == 503
    assert client.get("/livez").status_code == 200
