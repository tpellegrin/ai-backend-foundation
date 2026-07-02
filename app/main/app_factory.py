from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.api.errors import register_exception_handlers
from app.api.security_headers import SecurityHeadersMiddleware
from app.api.v1 import build_v1_router
from app.core.config.settings import AppSettings, get_settings
from app.core.container import Container
from app.core.lifespan import lifespan
from app.observability.correlation import CorrelationMiddleware
from app.observability.health import ProbeRegistry, build_health_router
from app.observability.logging import configure_logging
from app.observability.middleware import AccessLogMiddleware


def create_app(settings: AppSettings | None = None) -> FastAPI:
    """Produce a fully configured FastAPI app for serving and for tests.
    This function is the composition root of the application. It constructs
    the initial Container and ProbeRegistry, installs middleware, mounts
    routers, and registers exception handlers.
    """
    # 1. Resolve settings and configure logging
    settings = settings if settings is not None else get_settings()
    configure_logging(level=settings.logging.level, json=settings.app.env != "dev")

    # 2. Construct the initial Container
    # This is the sole construction site for both objects for the process lifetime.
    container = Container(settings=settings, probe_registry=ProbeRegistry())

    # 3. Create FastAPI instance
    app = FastAPI(
        title=settings.app.service_name,
    )
    app.state.ready = False

    # 4. Assign container to app state BEFORE attaching the lifespan
    # ADR-0023 requirement: ensures health router and downstream code see the container.
    app.state.container = container

    # 5. Install middleware in exact order (outermost first)
    # Since add_middleware prepends, we add them in reverse order of the desired stack.
    # Desired stack: Correlation -> AccessLog -> SecurityHeaders -> CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_allowed_origins,
        allow_credentials=settings.api.cors_allow_credentials,
        allow_methods=settings.api.cors_allowed_methods,
        allow_headers=settings.api.cors_allowed_headers,
    )

    app.add_middleware(
        SecurityHeadersMiddleware,
        security_headers_enabled=settings.api.security_headers_enabled,
    )

    app.add_middleware(AccessLogMiddleware)

    app.add_middleware(CorrelationMiddleware)

    # 6. Mount routers
    # Health router closes over the same ProbeRegistry instance that wiring tasks will mutate.
    app.include_router(
        build_health_router(
            registry=container.probe_registry,
            is_ready=lambda: app.state.ready,
        )
    )
    # API v1 router
    app.include_router(build_v1_router())

    # 7. Register exception handlers
    register_exception_handlers(app)

    # 8. Set the lifespan from app.core.lifespan (T-504)
    # ADR-0023 requirement: must be assigned after app.state.container.
    app.router.lifespan_context = lifespan

    return app
