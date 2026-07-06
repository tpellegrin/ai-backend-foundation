from httpx import AsyncClient

from app.core.config.settings import AppSettings
from app.infrastructure.http import build_http_client


def setup_http_client(settings: AppSettings) -> AsyncClient:
    """Initialize the shared HTTP client."""
    return build_http_client(settings.http)
