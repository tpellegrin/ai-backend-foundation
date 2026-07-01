from collections.abc import Mapping
from typing import Any


class AppError(Exception):
    """
    Base class for all application errors.

    Provides the only base for raisable domain/service errors so the API edge
    can translate them uniformly to Problem Details.
    """

    def __init__(
        self,
        code: str,
        title: str,
        status: int = 400,
        detail: str | None = None,
        extras: Mapping[str, Any] | None = None,
    ) -> None:
        self._code = code
        self._title = title
        self._status = status
        self._detail = detail
        self._extras = dict(extras) if extras else {}
        super().__init__(self.title)

    @property
    def code(self) -> str:
        return self._code

    @property
    def title(self) -> str:
        return self._title

    @property
    def status(self) -> int:
        return self._status

    @property
    def detail(self) -> str | None:
        return self._detail

    @property
    def extras(self) -> Mapping[str, Any]:
        return self._extras

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(code={self.code}, status={self.status}, title={self.title})"
        )


class NotFoundError(AppError):
    def __init__(self, detail: str | None = None, extras: Mapping[str, Any] | None = None) -> None:
        super().__init__(
            code="not-found",
            title="Resource not found",
            status=404,
            detail=detail,
            extras=extras,
        )


class ConflictError(AppError):
    def __init__(self, detail: str | None = None, extras: Mapping[str, Any] | None = None) -> None:
        super().__init__(
            code="conflict",
            title="Conflict",
            status=409,
            detail=detail,
            extras=extras,
        )


class ValidationError(AppError):
    def __init__(self, detail: str | None = None, extras: Mapping[str, Any] | None = None) -> None:
        super().__init__(
            code="validation-error",
            title="Validation error",
            status=422,
            detail=detail,
            extras=extras,
        )


class AuthenticationError(AppError):
    def __init__(self, detail: str | None = None, extras: Mapping[str, Any] | None = None) -> None:
        super().__init__(
            code="authentication-error",
            title="Authentication failed",
            status=401,
            detail=detail,
            extras=extras,
        )


class AuthorizationError(AppError):
    def __init__(self, detail: str | None = None, extras: Mapping[str, Any] | None = None) -> None:
        super().__init__(
            code="authorization-error",
            title="Authorization failed",
            status=403,
            detail=detail,
            extras=extras,
        )


class BudgetExceededError(AppError):
    def __init__(self, detail: str | None = None, extras: Mapping[str, Any] | None = None) -> None:
        super().__init__(
            code="budget-exceeded",
            title="Budget exceeded",
            status=409,
            detail=detail,
            extras=extras,
        )


class UpstreamProviderError(AppError):
    def __init__(self, detail: str | None = None, extras: Mapping[str, Any] | None = None) -> None:
        super().__init__(
            code="upstream-provider-error",
            title="Upstream provider error",
            status=502,
            detail=detail,
            extras=extras,
        )


class RateLimitedError(AppError):
    def __init__(self, detail: str | None = None, extras: Mapping[str, Any] | None = None) -> None:
        super().__init__(
            code="rate-limited",
            title="Rate limit exceeded",
            status=429,
            detail=detail,
            extras=extras,
        )
