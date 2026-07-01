from pydantic import BaseModel, ConfigDict

from app.shared.errors import AppError

MEDIA_TYPE = "application/problem+json"

# Field names owned by ProblemDetails that must never be overridden by
# arbitrary AppError.extras keys. Extras attempting to set any of these keys
# are silently dropped so that the canonical fields cannot be spoofed.
_RESERVED_FIELDS: frozenset[str] = frozenset(
    {"type", "title", "status", "detail", "instance", "code", "request_id"}
)


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

    ``AppError.extras`` keys that collide with reserved ProblemDetails fields
    are dropped; the canonical fields (``type``, ``title``, ``status``, ``detail``,
    ``instance``, ``code``, ``request_id``) cannot be overridden.
    """
    safe_extras = {k: v for k, v in err.extras.items() if k not in _RESERVED_FIELDS}
    return ProblemDetails(
        title=err.title,
        status=err.status,
        detail=err.detail,
        code=err.code,
        request_id=request_id,
        **safe_extras,
    )
