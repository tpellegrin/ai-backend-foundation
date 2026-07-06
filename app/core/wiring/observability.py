from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from app.core.config.settings import AppSettings


def apply_httpx_instrumentation(settings: AppSettings) -> None:
    """
    Apply OpenTelemetry instrumentation to HTTPX.
    Only enabled if an OTel endpoint is configured.
    """
    if settings.otel.endpoint:
        HTTPXClientInstrumentor().instrument()
