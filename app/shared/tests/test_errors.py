# ruff: noqa: S101
import pytest

from app.shared.errors import (
    AppError,
    AuthenticationError,
    AuthorizationError,
    BudgetExceededError,
    ConflictError,
    NotFoundError,
    RateLimitedError,
    UpstreamProviderError,
    ValidationError,
)


@pytest.mark.unit
def test_app_error_properties() -> None:
    status_code = 400
    err = AppError(
        code="some-error",
        title="Some Title",
        status=status_code,
        detail="Some detail",
        extras={"key": "value"},
    )
    assert err.code == "some-error"
    assert err.title == "Some Title"
    assert err.status == status_code
    assert err.detail == "Some detail"
    assert err.extras == {"key": "value"}
    assert str(err) == "Some Title"
    assert repr(err) == f"AppError(code=some-error, status={status_code}, title=Some Title)"


@pytest.mark.unit
def test_app_error_frozen() -> None:
    err = AppError(code="test", title="test")
    with pytest.raises(AttributeError):
        err.code = "new"  # type: ignore[misc]  # property has no setter (frozen)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("error_class", "expected_code", "expected_status", "expected_title"),
    [
        (NotFoundError, "not-found", 404, "Resource not found"),
        (ConflictError, "conflict", 409, "Conflict"),
        (ValidationError, "validation-error", 422, "Validation error"),
        (AuthenticationError, "authentication-error", 401, "Authentication failed"),
        (AuthorizationError, "authorization-error", 403, "Authorization failed"),
        (BudgetExceededError, "budget-exceeded", 409, "Budget exceeded"),
        (UpstreamProviderError, "upstream-provider-error", 502, "Upstream provider error"),
        (RateLimitedError, "rate-limited", 429, "Rate limit exceeded"),
    ],
)
def test_subclasses(
    error_class: type[AppError], expected_code: str, expected_status: int, expected_title: str
) -> None:
    detail = "Specific detail"
    extras = {"foo": "bar"}
    err = error_class(detail=detail, extras=extras)  # type: ignore[call-arg]  # subclasses take only detail/extras, not code/title/status

    assert isinstance(err, AppError)
    assert err.code == expected_code
    assert err.status == expected_status
    assert err.title == expected_title
    assert err.detail == detail
    assert err.extras == extras
