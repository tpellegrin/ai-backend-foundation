from contextvars import ContextVar
from uuid import UUID, uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class CorrelationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that handles request correlation using an X-Request-ID header.

    It reads the inbound header, validates it as a UUID, and either echoes it
    or generates a fresh UUIDv4. The resolved id is stored in two places:

    * the ``request_id_var`` :class:`~contextvars.ContextVar`, for use in
      service/domain code and structured logging;
    * ``request.state.request_id`` (which lives on the ASGI ``scope["state"]``
      dict), so that Starlette's ``ServerErrorMiddleware`` — which wraps this
      middleware and runs the ``Exception`` handler *outside* our
      contextvar's scope — can still recover the id when emitting sanitized
      500 Problem Details responses.

    The header is echoed on every response we return from this middleware.
    Because the ``Exception`` handler is invoked by ``ServerErrorMiddleware``
    (outermost), it is responsible for setting the header itself; see
    :mod:`app.api.errors`.
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

        # Persist on scope-backed state so exception handlers running outside
        # this middleware (i.e. inside ServerErrorMiddleware) can still read
        # the id after our contextvar has been reset.
        request.state.request_id = request_id

        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(token)
