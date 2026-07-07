from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import select

from app.auth.domain import RefreshTokenRecord, UserAuthRecord
from app.platform.db.base import Base


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    tenant_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=False)

    def to_domain(self) -> UserAuthRecord:
        return UserAuthRecord(
            id=self.id,
            email=self.email,
            password_hash=self.password_hash,
            created_at=self.created_at,
            tenant_id=self.tenant_id,
            disabled=self.disabled,
        )


class RefreshTokenRow(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    family_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("refresh_tokens.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        Index(
            "ix_refresh_tokens_family_active",
            family_id,
            unique=True,
            # We use == None (with noqa) because SQLAlchemy's postgresql_where
            # requires it to produce 'IS NULL' in the index predicate.
            postgresql_where=(replaced_by == None),  # noqa: E711
        ),
    )

    def to_domain(self) -> RefreshTokenRecord:
        return RefreshTokenRecord(
            id=self.id,
            user_id=self.user_id,
            family_id=self.family_id,
            hash=self.hash,
            issued_at=self.issued_at,
            expires_at=self.expires_at,
            revoked_at=self.revoked_at,
            replaced_by=self.replaced_by,
        )


async def insert_user(  # noqa: PLR0913
    session: AsyncSession,
    *,
    id: UUID,
    email: str,
    password_hash: str,
    created_at: datetime,
    tenant_id: UUID | None,
    disabled: bool,
) -> UserAuthRecord:
    row = UserRow(
        id=id,
        email=email,
        password_hash=password_hash,
        created_at=created_at,
        tenant_id=tenant_id,
        disabled=disabled,
    )
    session.add(row)
    await session.flush()
    return row.to_domain()


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> UserAuthRecord | None:
    stmt = select(UserRow).where(UserRow.id == user_id)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return row.to_domain() if row else None


async def get_user_by_email(session: AsyncSession, email: str) -> UserAuthRecord | None:
    stmt = select(UserRow).where(UserRow.email == email)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return row.to_domain() if row else None


async def insert_refresh_token(  # noqa: PLR0913
    session: AsyncSession,
    *,
    id: UUID,
    user_id: UUID,
    family_id: UUID,
    hash: str,
    issued_at: datetime,
    expires_at: datetime,
    revoked_at: datetime | None,
    replaced_by: UUID | None,
) -> RefreshTokenRecord:
    row = RefreshTokenRow(
        id=id,
        user_id=user_id,
        family_id=family_id,
        hash=hash,
        issued_at=issued_at,
        expires_at=expires_at,
        revoked_at=revoked_at,
        replaced_by=replaced_by,
    )
    session.add(row)
    await session.flush()
    return row.to_domain()


async def get_refresh_token_by_hash(
    session: AsyncSession, token_hash: str
) -> RefreshTokenRecord | None:
    stmt = select(RefreshTokenRow).where(RefreshTokenRow.hash == token_hash)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return row.to_domain() if row else None


async def get_refresh_token_by_id(
    session: AsyncSession, token_id: UUID
) -> RefreshTokenRecord | None:
    stmt = select(RefreshTokenRow).where(RefreshTokenRow.id == token_id)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return row.to_domain() if row else None


async def get_active_refresh_token_by_family(
    session: AsyncSession, family_id: UUID
) -> RefreshTokenRecord | None:
    stmt = select(RefreshTokenRow).where(
        RefreshTokenRow.family_id == family_id,
        RefreshTokenRow.replaced_by == None,  # noqa: E711
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return row.to_domain() if row else None
