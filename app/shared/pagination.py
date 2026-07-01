from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Page[T]:
    items: Sequence[T]
    total: int
    cursor: str | None = None


@dataclass(frozen=True)
class CursorParams:
    cursor: str | None = None
    limit: int = 20
