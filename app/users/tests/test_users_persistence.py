# ruff: noqa: S101
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.users.persistence import UserProfileRow, create_user_profile, get_user_profile


@pytest.mark.unit
def test_user_row_to_domain() -> None:
    user_id = uuid.uuid4()
    now = datetime.now(UTC)
    row = UserProfileRow(
        id=user_id,
        email="test@example.com",
        created_at=now,
        updated_at=now,
    )
    domain = row.to_domain()
    assert domain.id == user_id
    assert domain.email == "test@example.com"
    assert domain.created_at == now
    assert domain.updated_at == now


@pytest.mark.unit
async def test_get_user_profile(mock_session: AsyncMock) -> None:
    user_id = uuid.uuid4()
    now = datetime.now(UTC)
    row = UserProfileRow(
        id=user_id,
        email="test@example.com",
        created_at=now,
        updated_at=now,
    )

    # Mocking the execution of the statement
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = row
    mock_session.execute.return_value = mock_result

    result = await get_user_profile(mock_session, user_id)
    assert result is not None
    assert result.id == user_id
    assert result.email == "test@example.com"


@pytest.mark.unit
async def test_create_user_profile(mock_session: AsyncMock) -> None:
    user_id = uuid.uuid4()
    email = "test@example.com"
    now = datetime.now(UTC)

    result = await create_user_profile(
        mock_session,
        user_id=user_id,
        email=email,
        created_at=now,
        updated_at=now,
    )

    assert result.id == user_id
    assert result.email == email
    mock_session.add.assert_called_once()
    mock_session.flush.assert_called_once()


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    return session
