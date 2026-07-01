from pydantic import BaseModel, ConfigDict

from app.shared.errors import AppError

MEDIA_TYPE = "application/problem+json"


class ProblemDetails(BaseModel):
    """
    RFC 9457 Problem Details for HTTP APIs.
    """

    model_config = ConfigDict(extra="allow")

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    code: str
    request_id: str | None = None


def from_app_error(err: AppError, *, request_id: str | None = None) -> ProblemDetails:
    """
    Factory to create ProblemDetails from an AppError.
    """
    return ProblemDetails(
        title=err.title,
        status=err.status,
        detail=err.detail,
        code=err.code,
        request_id=request_id,
        **err.extras,
    )
