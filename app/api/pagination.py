from typing import Annotated, Final

from fastapi import Query

from app.shared.errors import ValidationError
from app.shared.pagination import CursorParams

LIMIT_MIN: Final = 1
LIMIT_MAX: Final = 100
DEFAULT_LIMIT: Final = 20

__all__ = ["CursorParams", "get_cursor_params"]


async def get_cursor_params(
    cursor: Annotated[str | None, Query(description="Opaque pagination cursor")] = None,
    limit: Annotated[int, Query(description="Number of items to return")] = DEFAULT_LIMIT,
) -> CursorParams:
    """
    FastAPI dependency that extracts and validates cursor pagination parameters.

    - limit: default 20, max 100, min 1.
    - cursor: opaque string.

    Raises:
        ValidationError: If limit is out of bounds or cursor is invalid.
    """
    if limit < LIMIT_MIN:
        raise ValidationError(f"Limit must be at least {LIMIT_MIN}")  # noqa: TRY003
    if limit > LIMIT_MAX:
        raise ValidationError(f"Limit cannot exceed {LIMIT_MAX}")  # noqa: TRY003

    if cursor == "":
        raise ValidationError("Cursor cannot be empty")  # noqa: TRY003

    return CursorParams(cursor=cursor, limit=limit)
