from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.trace import StatusCode

from app.observability import get_logger, request_id_var
from app.shared.errors import AppError
from app.shared.problem_details import MEDIA_TYPE, ProblemDetails, from_app_error

logger = get_logger(__name__)


def _resolve_request_id(request: Request) -> str:
    """Recover the correlation id for an error response.

    Preference order:

    1. ``request.state.request_id`` — set by
       :class:`app.observability.correlation.CorrelationMiddleware` and
       reachable even after the contextvar has been reset (e.g. when the
       fallback ``Exception`` handler runs inside
       ``ServerErrorMiddleware``, which wraps our middleware).
    2. ``request_id_var`` — set for handlers that still run inside the
       correlation middleware's contextvar scope (``AppError``,
       ``RequestValidationError``).
    3. A freshly generated UUIDv4 — defensive fallback so error responses
       *always* carry ``X-Request-ID``, even if the correlation middleware
       is not installed (e.g. in isolated unit tests).
    """
    state_id = getattr(request.state, "request_id", "") or ""
    if state_id:
        return state_id
    ctx_id = request_id_var.get()
    if ctx_id:
        return ctx_id
    return str(uuid4())


def register_exception_handlers(app: FastAPI) -> None:
    """Install the three T-501 exception handlers.

    Service and domain code must raise :class:`AppError` subclasses only.
    ``HTTPException`` raised from below ``api.py`` is intentionally *not*
    mapped here — it is caught by the fallback :class:`Exception` handler and
    reported as a generic 500, which surfaces the misuse instead of hiding it.

    All three handlers emit ``X-Request-ID`` on every response, including
    sanitized 500s produced by the fallback handler. The id is resolved via
    :func:`_resolve_request_id`, which reads from ``request.state`` first so
    that the fallback handler (invoked by Starlette's ``ServerErrorMiddleware``
    *outside* our correlation middleware's contextvar scope) still recovers
    the correct id.
    """

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        request_id = _resolve_request_id(request)
        problem = from_app_error(exc, request_id=request_id)

        span = trace.get_current_span()
        if span.is_recording():
            span.set_status(StatusCode.ERROR, str(exc))
            span.record_exception(exc)

        return JSONResponse(
            status_code=exc.status,
            content=problem.model_dump(exclude_none=True),
            headers={"X-Request-ID": request_id},
            media_type=MEDIA_TYPE,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = _resolve_request_id(request)

        problem = ProblemDetails(
            title="Validation error",
            status=422,
            detail="The request body or parameters are invalid.",
            code="validation-error",
            request_id=request_id,
            errors=exc.errors(),
        )

        span = trace.get_current_span()
        if span.is_recording():
            span.set_status(StatusCode.ERROR, "Validation failed")
            span.record_exception(exc)

        return JSONResponse(
            status_code=422,
            content=problem.model_dump(exclude_none=True),
            headers={"X-Request-ID": request_id},
            media_type=MEDIA_TYPE,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = _resolve_request_id(request)

        logger.error(
            "unhandled_exception",
            exc_info=exc,
            request_id=request_id,
            method=request.method,
            url=str(request.url),
        )

        span = trace.get_current_span()
        if span.is_recording():
            span.set_status(StatusCode.ERROR, "Unhandled exception")
            span.record_exception(exc)

        problem = ProblemDetails(
            title="Internal server error",
            status=500,
            detail="An unexpected error occurred.",
            code="internal-error",
            request_id=request_id,
        )

        return JSONResponse(
            status_code=500,
            content=problem.model_dump(exclude_none=True),
            headers={"X-Request-ID": request_id},
            media_type=MEDIA_TYPE,
        )
