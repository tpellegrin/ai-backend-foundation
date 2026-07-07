from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.clock import Clock
from app.users import persistence
from app.users.domain import UserProfile


class UserService:
    """Service for managing user profiles."""

    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self._session = session
        self._clock = clock

    async def get_or_create_profile(self, user_id: UUID, email: str) -> UserProfile:
        """
        Get the user profile, or create it if it doesn't exist.

        This lazy-read path ensures that the Users module can always provide
        a profile even if the registration flow didn't explicitly initialize
        it (e.g. creating the user_profiles row).
        """
        profile = await persistence.get_user_profile(
            self._session,
            user_id=user_id,
        )
        if profile:
            return profile

        # In the split-table architecture, the 'users' row was created
        # during registration by the Auth service. This lazy-read path ensures
        # that the Users module can always provide a profile record in
        # user_profiles even if it wasn't explicitly initialized.
        now = self._clock.now()
        profile = await persistence.create_user_profile(
            self._session,
            user_id=user_id,
            email=email,
            created_at=now,
            updated_at=now,
        )
        return profile
