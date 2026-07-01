from contextvars import ContextVar
from uuid import UUID, uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class CorrelationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that handles request correlation using an X-Request-ID header.
    It reads the inbound header, validates it, sets the request_id_var ContextVar,
    and ensures the response carries the same header.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        inbound_id = request.headers.get("X-Request-ID")

        request_id: str
        if inbound_id:
            try:
                # Basic validation: must be a valid UUID
                UUID(inbound_id)
                request_id = inbound_id
            except ValueError:
                request_id = str(uuid4())
        else:
            request_id = str(uuid4())

        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(token)
