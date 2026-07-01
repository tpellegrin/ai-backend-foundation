import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.observability.logging import get_logger

logger = get_logger(__name__)


class AccessLogMiddleware(BaseHTTPMiddleware):
    """
    Middleware that emits a single structured access log per request.
    Logs method, path, status, duration_ms, and request_id (via logging processor).

    ``user_id`` is intentionally ``None`` at this phase: no auth subsystem
    exists yet, and guessing its shape would prematurely lock a contract
    that T-701+ has not defined.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.perf_counter()

        response = await call_next(request)

        duration_ms = int((time.perf_counter() - start_time) * 1000)

        logger.info(
            "access_log",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            user_id=None,
        )

        return response
