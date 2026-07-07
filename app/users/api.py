from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.deps import get_current_user
from app.auth.domain import AuthenticatedUser
from app.users.deps import get_user_service
from app.users.domain import UserProfile
from app.users.service import UserService

router = APIRouter()


class UserProfileResponse(BaseModel):
    """API response model for user profile."""

    id: UUID
    email: str


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserProfile:
    """Get the current user's profile, creating it if necessary."""
    return await user_service.get_or_create_profile(
        user_id=UUID(current_user.user_id),
        email=current_user.email,
    )
