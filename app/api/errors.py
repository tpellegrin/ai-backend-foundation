from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.trace import StatusCode
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.observability import get_logger, request_id_var
from app.shared.errors import AppError
from app.shared.problem_details import MEDIA_TYPE, ProblemDetails, from_app_error

logger = get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        request_id = request_id_var.get()
        problem = from_app_error(exc, request_id=request_id)

        span = trace.get_current_span()
        if span.is_recording():
            span.set_status(StatusCode.ERROR, str(exc))
            span.record_exception(exc)

        return JSONResponse(
            status_code=exc.status,
            content=problem.model_dump(exclude_none=True),
            headers={"X-Request-ID": request_id} if request_id else {},
            media_type=MEDIA_TYPE,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = request_id_var.get()

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
            headers={"X-Request-ID": request_id} if request_id else {},
            media_type=MEDIA_TYPE,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = request_id_var.get()

        try:
            title = HTTPStatus(exc.status_code).phrase
        except ValueError:
            title = "HTTP error"

        problem = ProblemDetails(
            title=title,
            status=exc.status_code,
            detail=str(exc.detail),
            code=f"http-{exc.status_code}",
            request_id=request_id,
        )

        return JSONResponse(
            status_code=exc.status_code,
            content=problem.model_dump(exclude_none=True),
            headers={"X-Request-ID": request_id} if request_id else {},
            media_type=MEDIA_TYPE,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = request_id_var.get()

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
            headers={"X-Request-ID": request_id} if request_id else {},
            media_type=MEDIA_TYPE,
        )
