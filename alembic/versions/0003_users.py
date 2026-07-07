"""users

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-07 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create user_profiles table separate from auth users table
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["id"], ["users.id"], ondelete="CASCADE", name="fk_user_profiles_id_users"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_profiles_email"), "user_profiles", ["email"], unique=True)


def downgrade() -> None:
    # Drop user_profiles table
    op.drop_index(op.f("ix_user_profiles_email"), table_name="user_profiles")
    op.drop_table("user_profiles")
