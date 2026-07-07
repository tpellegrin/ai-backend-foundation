from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import select

from app.platform.db.base import Base
from app.users.domain import UserProfile


class UserProfileRow(Base):
    """SQLAlchemy model for user profiles, stored in a separate table."""

    __tablename__ = "user_profiles"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def to_domain(self) -> UserProfile:
        """Convert row to domain object."""
        return UserProfile(
            id=self.id,
            email=self.email,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


async def get_user_profile(
    session: AsyncSession,
    user_id: UUID,
) -> UserProfile | None:
    """Fetch a user profile by ID."""
    stmt = select(UserProfileRow).where(UserProfileRow.id == user_id)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return row.to_domain() if row else None


async def create_user_profile(
    session: AsyncSession,
    *,
    user_id: UUID,
    email: str,
    created_at: datetime,
    updated_at: datetime,
) -> UserProfile:
    """Create a user profile record."""
    row = UserProfileRow(
        id=user_id,
        email=email,
        created_at=created_at,
        updated_at=updated_at,
    )
    session.add(row)
    await session.flush()
    return row.to_domain()
