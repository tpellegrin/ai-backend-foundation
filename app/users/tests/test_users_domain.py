# ruff: noqa: S101
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.users.domain import UserProfile


@pytest.mark.unit
def test_user_profile_creation() -> None:
    """Test UserProfile dataclass creation and immutability."""
    user_id = uuid4()
    now = datetime.now(UTC)
    email = "test@example.com"

    profile = UserProfile(
        id=user_id,
        email=email,
        created_at=now,
        updated_at=now,
    )

    assert profile.id == user_id
    assert profile.email == email
    assert profile.created_at == now
    assert profile.updated_at == now


@pytest.mark.unit
def test_user_profile_immutability() -> None:
    """Test UserProfile is frozen."""
    profile = UserProfile(
        id=uuid4(),
        email="test@example.com",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with pytest.raises(AttributeError):
        profile.email = "new@example.com"  # type: ignore[misc]


@pytest.mark.unit
def test_user_profile_equality() -> None:
    """Test UserProfile equality."""
    user_id = uuid4()
    now = datetime.now(UTC)
    email = "test@example.com"

    profile1 = UserProfile(
        id=user_id,
        email=email,
        created_at=now,
        updated_at=now,
    )
    profile2 = UserProfile(
        id=user_id,
        email=email,
        created_at=now,
        updated_at=now,
    )

    assert profile1 == profile2
