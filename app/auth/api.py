from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.auth.deps import get_auth_service
from app.auth.domain import Credentials
from app.auth.service import AuthService
from app.shared.problem_details import ProblemDetails

router = APIRouter()


class RegisterRequest(BaseModel):
    """Request model for user registration."""

    email: str = Field(..., examples=["user@example.com"])
    password: str = Field(..., min_length=8)


class RegisterResponse(BaseModel):
    """Response model for user registration."""

    user_id: str
    tenant_id: str


class LoginRequest(BaseModel):
    """Request model for user login."""

    username: str = Field(..., examples=["user@example.com"])
    password: str = Field(...)


class TokenResponse(BaseModel):
    """Response model for authentication tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"  # noqa: S105
    expires_in: int


class RefreshRequest(BaseModel):
    """Request model for rotating a refresh token."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Request model for logging out."""

    refresh_token: str


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterResponse,
    responses={
        409: {"model": ProblemDetails, "description": "User already exists"},
        422: {"model": ProblemDetails, "description": "Validation error"},
    },
)
async def register(
    request: RegisterRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> RegisterResponse:
    """Register a new user."""
    user = await auth_service.register(email=request.email, password=request.password)
    return RegisterResponse(
        user_id=str(user.user_id),
        tenant_id=str(user.tenant_id),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={
        401: {"model": ProblemDetails, "description": "Invalid credentials"},
        422: {"model": ProblemDetails, "description": "Validation error"},
    },
)
async def login(
    request: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """Authenticate a user and issue tokens."""
    creds = Credentials(username=request.username, password=request.password)
    access_token, refresh_token = await auth_service.login(creds)

    # TODO: [T-908] Use app/shared/clock.py for expires_in calculation
    now = datetime.now(UTC)
    expires_in = int((access_token.expires_at - now).total_seconds())

    return TokenResponse(
        access_token=access_token.token,
        refresh_token=refresh_token.token,
        expires_in=max(0, expires_in),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={
        401: {"model": ProblemDetails, "description": "Invalid refresh token"},
        422: {"model": ProblemDetails, "description": "Validation error"},
    },
)
async def refresh(
    request: RefreshRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """Rotate a refresh token."""
    access_token, refresh_token = await auth_service.refresh(request.refresh_token)

    # TODO: [T-908] Use app/shared/clock.py for expires_in calculation
    now = datetime.now(UTC)
    expires_in = int((access_token.expires_at - now).total_seconds())

    return TokenResponse(
        access_token=access_token.token,
        refresh_token=refresh_token.token,
        expires_in=max(0, expires_in),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        422: {"model": ProblemDetails, "description": "Validation error"},
    },
)
async def logout(
    request: LogoutRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    """Revoke a refresh token."""
    await auth_service.logout(request.refresh_token)
