from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

__all__ = ["SecurityHeadersMiddleware"]


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that sets security headers on every outbound response.

    Headers set:
    - Strict-Transport-Security: max-age=63072000; includeSubDomains
    - X-Content-Type-Options: nosniff
    - Referrer-Policy: no-referrer
    - X-Frame-Options: DENY
    - Content-Security-Policy: default-src 'none'

    Gated by `security_headers_enabled` boolean passed at construction.
    """

    def __init__(self, app: ASGIApp, security_headers_enabled: bool = True) -> None:
        super().__init__(app)
        self.security_headers_enabled = security_headers_enabled

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if self.security_headers_enabled:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Content-Security-Policy"] = "default-src 'none'"
        return response
