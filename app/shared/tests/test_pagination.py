# ruff: noqa: S101, PLR2004
import pytest

from app.shared.pagination import CursorParams, Page


@pytest.mark.unit
def test_page_initialization() -> None:
    page = Page(items=[1, 2, 3], total=10, cursor="next-123")
    assert page.items == [1, 2, 3]
    assert page.total == 10
    assert page.cursor == "next-123"


@pytest.mark.unit
def test_page_defaults() -> None:
    page: Page[int] = Page(items=[], total=0)
    assert page.items == []
    assert page.total == 0
    assert page.cursor is None


@pytest.mark.unit
def test_cursor_params_defaults() -> None:
    params = CursorParams()
    assert params.cursor is None
    assert params.limit == 20
