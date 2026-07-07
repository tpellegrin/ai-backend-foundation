from app.auth.domain import AuthenticatedUser
from app.shared.errors import AuthenticationError


def require_authenticated(user: AuthenticatedUser | None) -> AuthenticatedUser:
    """Ensure a user is authenticated."""
    if user is None:
        raise AuthenticationError("Not authenticated")  # noqa: TRY003
    return user


def require_active_user(user: AuthenticatedUser, active: bool | None) -> AuthenticatedUser:
    """Ensure an authenticated user is active."""
    if not active:
        raise AuthenticationError("User is disabled")  # noqa: TRY003
    return user
