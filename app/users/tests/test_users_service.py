# ruff: noqa: S101
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.shared.clock import Clock
from app.users.domain import UserProfile
from app.users.service import UserService


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_clock() -> MagicMock:
    clock = MagicMock(spec=Clock)
    clock.now.return_value = datetime(2024, 7, 7, 12, 0, 0, tzinfo=UTC)
    return clock


@pytest.mark.unit
async def test_get_or_create_profile_existing(
    mock_session: AsyncMock, mock_clock: MagicMock
) -> None:
    user_id = uuid.uuid4()
    email = "test@example.com"

    profile = UserProfile(
        id=user_id,
        email=email,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with patch("app.users.persistence.get_user_profile", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = profile

        service = UserService(mock_session, mock_clock)
        result = await service.get_or_create_profile(user_id, email)

        assert result == profile
        mock_get.assert_called_once_with(
            mock_session,
            user_id=user_id,
        )


@pytest.mark.unit
async def test_get_or_create_profile_new(mock_session: AsyncMock, mock_clock: MagicMock) -> None:
    user_id = uuid.uuid4()
    email = "test@example.com"
    now = mock_clock.now()

    profile = UserProfile(
        id=user_id,
        email=email,
        created_at=now,
        updated_at=now,
    )

    with patch("app.users.persistence.get_user_profile", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None
        with patch(
            "app.users.persistence.create_user_profile", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = profile

            service = UserService(mock_session, mock_clock)
            result = await service.get_or_create_profile(user_id, email)

            assert result == profile
            mock_get.assert_called_once_with(
                mock_session,
                user_id=user_id,
            )
            mock_create.assert_called_once_with(
                mock_session,
                user_id=user_id,
                email=email,
                created_at=now,
                updated_at=now,
            )
