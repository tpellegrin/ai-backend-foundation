# ruff: noqa: S101
from unittest.mock import MagicMock

import pytest
from fastapi import Request

from app.users import api, deps
from app.users.deps import _get_db_session, get_user_service


@pytest.fixture
def mock_container() -> MagicMock:
    container = MagicMock()
    container.clock = MagicMock()
    return container


@pytest.fixture
def mock_request(mock_container: MagicMock) -> MagicMock:
    request = MagicMock(spec=Request)
    request.app.state.container = mock_container
    return request


@pytest.mark.unit
async def test_get_db_session(mock_request: MagicMock, mock_container: MagicMock) -> None:
    session = MagicMock()
    mock_container.session_factory.return_value.__aenter__.return_value = session

    async for s in _get_db_session(mock_request):
        assert s == session

    mock_container.session_factory.return_value.__aenter__.assert_called_once()


@pytest.mark.unit
async def test_get_db_session_no_factory(
    mock_request: MagicMock, mock_container: MagicMock
) -> None:
    mock_container.session_factory = None
    with pytest.raises(RuntimeError) as excinfo:
        async for _ in _get_db_session(mock_request):
            pass
    assert "session_factory not initialized" in str(excinfo.value)


@pytest.mark.unit
async def test_get_user_service(mock_request: MagicMock, mock_container: MagicMock) -> None:
    session = MagicMock()
    service = await get_user_service(mock_request, session)
    assert service._session == session
    assert service._clock == mock_container.clock


@pytest.mark.unit
async def test_get_user_service_no_clock(
    mock_request: MagicMock, mock_container: MagicMock
) -> None:
    mock_container.clock = None
    session = MagicMock()
    with pytest.raises(RuntimeError) as excinfo:
        await get_user_service(mock_request, session)
    assert "Clock not wired" in str(excinfo.value)


@pytest.mark.unit
def test_dependency_behavior_no_auth_internals() -> None:
    """
    Explicitly verify that the users layer does not pull in auth internals.
    This satisfies the T-910 requirement for dependency behavior testing.
    """
    # Only public auth modules are allowed at the API/deps edge
    allowed_auth = {"app.auth.deps", "app.auth.domain"}
    forbidden_substrings = {"persistence", "adapters", "tokens", "password"}

    for module in [api, deps]:
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            module_name = getattr(attr, "__module__", "") or ""

            if "app.auth" in module_name:
                # Must be one of the allowed public modules
                is_allowed = any(allowed in module_name for allowed in allowed_auth)
                assert is_allowed, (
                    f"Forbidden auth import in {module.__name__}: {module_name}.{attr_name}"
                )

                # Even if allowed, ensure no internals leaked through (e.g. by re-export)
                has_forbidden = any(forbidden in module_name for forbidden in forbidden_substrings)
                assert not has_forbidden, (
                    f"Auth internal leaked in {module.__name__}: {module_name}.{attr_name}"
                )
