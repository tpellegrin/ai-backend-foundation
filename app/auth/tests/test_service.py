# ruff: noqa: S101, S105, S106, SIM117
from datetime import UTC, datetime, timedelta
from unittest.mock import ANY, AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.auth.domain import (
    Credentials,
    InvalidCredentialsError,
    RefreshReuseDetectedError,
    RefreshTokenRecord,
    UserAuthRecord,
)
from app.auth.service import AuthService
from app.shared.errors import AuthenticationError, ConflictError
from app.shared.types import TenantId, UserId


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_hasher() -> MagicMock:
    hasher = MagicMock()
    hasher.hash.side_effect = lambda p: f"hashed-{p}"
    hasher.verify.side_effect = lambda p, h: h == f"hashed-{p}"
    return hasher


@pytest.fixture
def mock_signer() -> MagicMock:
    signer = MagicMock()
    signer.sign.return_value = "signed-token"
    signer.verify.return_value = {"sub": "user-id", "jti": str(uuid4()), "typ": "refresh"}
    return signer


@pytest.fixture
def service(mock_session: AsyncMock, mock_hasher: MagicMock, mock_signer: MagicMock) -> AuthService:
    return AuthService(mock_session, mock_hasher, mock_signer)


@pytest.mark.unit
async def test_register_happy_path(
    service: AuthService, mock_session: AsyncMock, mock_hasher: MagicMock
) -> None:
    email = "test@example.com"
    password = "password123"

    with (
        patch("app.auth.persistence.get_user_by_email", return_value=None),
        patch("app.auth.persistence.insert_user") as mock_insert,
    ):
        mock_insert.return_value = UserAuthRecord(
            id=uuid4(),
            email=email,
            password_hash=mock_hasher.hash(password),
            created_at=datetime.now(UTC),
            tenant_id=None,
            disabled=False,
        )

        user = await service.register(email, password)

        assert user.user_id == UserId(str(mock_insert.return_value.id))
        assert user.tenant_id == TenantId("")
        assert user.scopes == frozenset(["user"])
        mock_insert.assert_called_once()


@pytest.mark.unit
async def test_register_conflict(service: AuthService) -> None:
    email = "test@example.com"
    password = "password123"

    with patch("app.auth.persistence.get_user_by_email") as mock_get:
        mock_get.return_value = UserAuthRecord(
            id=uuid4(),
            email=email,
            password_hash="hash",
            created_at=datetime.now(UTC),
            tenant_id=None,
            disabled=False,
        )

        with pytest.raises(ConflictError):
            await service.register(email, password)


@pytest.mark.unit
async def test_login_happy_path(
    service: AuthService, mock_hasher: MagicMock, mock_signer: MagicMock
) -> None:
    email = "test@example.com"
    password = "password123"
    user_id = uuid4()

    user_record = UserAuthRecord(
        id=user_id,
        email=email,
        password_hash=mock_hasher.hash(password),
        created_at=datetime.now(UTC),
        tenant_id=None,
        disabled=False,
    )

    with (
        patch("app.auth.persistence.get_user_by_email", return_value=user_record),
        patch("app.auth.persistence.insert_refresh_token") as mock_insert,
    ):
        at, rt = await service.login(Credentials(username=email, password=password))

        assert at.token == "signed-token"
        assert rt.token == "signed-token"
        mock_insert.assert_called_once()


@pytest.mark.unit
async def test_login_invalid_credentials(service: AuthService) -> None:
    email = "test@example.com"

    with patch("app.auth.persistence.get_user_by_email", return_value=None):
        with pytest.raises(InvalidCredentialsError):
            await service.login(Credentials(username=email, password="wrong"))


@pytest.mark.unit
async def test_login_disabled_user(service: AuthService, mock_hasher: MagicMock) -> None:
    email = "test@example.com"
    user_record = UserAuthRecord(
        id=uuid4(),
        email=email,
        password_hash=mock_hasher.hash("password"),
        created_at=datetime.now(UTC),
        tenant_id=None,
        disabled=True,
    )

    with patch("app.auth.persistence.get_user_by_email", return_value=user_record):
        with pytest.raises(InvalidCredentialsError):
            await service.login(Credentials(username=email, password="password"))


@pytest.mark.unit
async def test_refresh_rotation_happy_path(
    service: AuthService, mock_signer: MagicMock, mock_hasher: MagicMock
) -> None:
    token_id = uuid4()
    user_id = uuid4()
    family_id = uuid4()

    mock_signer.verify.return_value = {"jti": str(token_id), "typ": "refresh"}

    token_record = RefreshTokenRecord(
        id=token_id,
        user_id=user_id,
        family_id=family_id,
        hash="hashed-old-token",
        issued_at=datetime.now(UTC) - timedelta(hours=1),
        expires_at=datetime.now(UTC) + timedelta(days=1),
        revoked_at=None,
        replaced_by=None,
    )

    user_record = UserAuthRecord(
        id=user_id,
        email="test@example.com",
        password_hash="hash",
        created_at=datetime.now(UTC),
        tenant_id=None,
        disabled=False,
    )

    with (
        patch("app.auth.persistence.get_refresh_token_by_id", return_value=token_record),
        patch("app.auth.persistence.get_user_by_id", return_value=user_record),
        patch("app.auth.persistence.mark_refresh_token_replaced") as mock_replace,
        patch("app.auth.persistence.insert_refresh_token") as mock_insert,
    ):
        # Initial verify for RT matches the mock_hasher logic
        mock_hasher.verify.return_value = True

        at, rt = await service.refresh("old-token")

        assert at.token == "signed-token"
        assert rt.token == "signed-token"
        mock_replace.assert_called_once()
        mock_insert.assert_called_once()


@pytest.mark.unit
async def test_refresh_reuse_detection(
    service: AuthService, mock_signer: MagicMock, mock_hasher: MagicMock
) -> None:
    token_id = uuid4()
    family_id = uuid4()

    mock_signer.verify.return_value = {"jti": str(token_id), "typ": "refresh"}

    token_record = RefreshTokenRecord(
        id=token_id,
        user_id=uuid4(),
        family_id=family_id,
        hash="hashed-reused-token",
        issued_at=datetime.now(UTC) - timedelta(hours=2),
        expires_at=datetime.now(UTC) + timedelta(days=1),
        revoked_at=datetime.now(UTC) - timedelta(hours=1),
        replaced_by=uuid4(),
    )

    with (
        patch("app.auth.persistence.get_refresh_token_by_id", return_value=token_record),
        patch("app.auth.persistence.revoke_refresh_token_family") as mock_revoke_family,
    ):
        mock_hasher.verify.return_value = True

        with patch("app.auth.service.logger") as mock_logger:
            with pytest.raises(RefreshReuseDetectedError):
                await service.refresh("reused-token")

            mock_logger.error.assert_called_once_with(
                "refresh_token_reuse_detected",
                user_id=token_record.user_id,
                family_id=token_record.family_id,
                token_id=token_record.id,
            )

        mock_revoke_family.assert_called_once_with(
            service._session,
            family_id=family_id,
            revoked_at=ANY,
        )


@pytest.mark.unit
async def test_login_wrong_password(service: AuthService, mock_hasher: MagicMock) -> None:
    email = "test@example.com"
    user_record = UserAuthRecord(
        id=uuid4(),
        email=email,
        password_hash=mock_hasher.hash("correct-password"),
        created_at=datetime.now(UTC),
        tenant_id=None,
        disabled=False,
    )

    with patch("app.auth.persistence.get_user_by_email", return_value=user_record):
        with pytest.raises(InvalidCredentialsError):
            await service.login(Credentials(username=email, password="wrong-password"))


@pytest.mark.unit
async def test_refresh_invalid_token_format(service: AuthService, mock_signer: MagicMock) -> None:
    mock_signer.verify.side_effect = AuthenticationError("invalid")
    with pytest.raises(InvalidCredentialsError) as excinfo:
        await service.refresh("garbage")
    assert excinfo.value.detail == "Invalid refresh token"


@pytest.mark.unit
async def test_refresh_wrong_token_type(service: AuthService, mock_signer: MagicMock) -> None:
    mock_signer.verify.return_value = {"jti": str(uuid4()), "typ": "access"}
    with pytest.raises(InvalidCredentialsError) as excinfo:
        await service.refresh("access-token-to-refresh")
    assert excinfo.value.detail == "Invalid token type"


@pytest.mark.unit
async def test_refresh_token_hash_mismatch(
    service: AuthService, mock_signer: MagicMock, mock_hasher: MagicMock
) -> None:
    token_id = uuid4()
    mock_signer.verify.return_value = {"jti": str(token_id), "typ": "refresh"}
    mock_hasher.verify.return_value = False

    token_record = RefreshTokenRecord(
        id=token_id,
        user_id=uuid4(),
        family_id=uuid4(),
        hash="mismatched-hash",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=1),
        revoked_at=None,
        replaced_by=None,
    )

    with patch("app.auth.persistence.get_refresh_token_by_id", return_value=token_record):
        with pytest.raises(InvalidCredentialsError) as excinfo:
            await service.refresh("token-with-bad-hash")
        assert excinfo.value.detail == "Invalid refresh token hash"


@pytest.mark.unit
async def test_refresh_token_not_found(service: AuthService, mock_signer: MagicMock) -> None:
    mock_signer.verify.return_value = {"jti": str(uuid4()), "typ": "refresh"}
    with patch("app.auth.persistence.get_refresh_token_by_id", return_value=None):
        with pytest.raises(InvalidCredentialsError) as excinfo:
            await service.refresh("valid-but-unknown")
        assert excinfo.value.detail == "Refresh token not found"


@pytest.mark.unit
async def test_refresh_revoked_but_not_reused(
    service: AuthService, mock_signer: MagicMock, mock_hasher: MagicMock
) -> None:
    token_id = uuid4()
    mock_signer.verify.return_value = {"jti": str(token_id), "typ": "refresh"}

    token_record = RefreshTokenRecord(
        id=token_id,
        user_id=uuid4(),
        family_id=uuid4(),
        hash="hashed-revoked-token",
        issued_at=datetime.now(UTC) - timedelta(hours=2),
        expires_at=datetime.now(UTC) + timedelta(days=1),
        revoked_at=datetime.now(UTC) - timedelta(hours=1),
        replaced_by=None,  # Not replaced, just revoked (e.g. logout)
    )

    with patch("app.auth.persistence.get_refresh_token_by_id", return_value=token_record):
        with pytest.raises(InvalidCredentialsError) as excinfo:
            await service.refresh("revoked-token")
        assert excinfo.value.detail == "Refresh token revoked"


@pytest.mark.unit
async def test_refresh_user_disabled(
    service: AuthService, mock_signer: MagicMock, mock_hasher: MagicMock
) -> None:
    token_id = uuid4()
    user_id = uuid4()
    mock_signer.verify.return_value = {"jti": str(token_id), "typ": "refresh"}

    token_record = RefreshTokenRecord(
        id=token_id,
        user_id=user_id,
        family_id=uuid4(),
        hash="hashed-token-for-disabled-user",
        issued_at=datetime.now(UTC) - timedelta(hours=1),
        expires_at=datetime.now(UTC) + timedelta(days=1),
        revoked_at=None,
        replaced_by=None,
    )

    user_record = UserAuthRecord(
        id=user_id,
        email="test@example.com",
        password_hash="hash",
        created_at=datetime.now(UTC),
        tenant_id=None,
        disabled=True,
    )

    with (
        patch("app.auth.persistence.get_refresh_token_by_id", return_value=token_record),
        patch("app.auth.persistence.get_user_by_id", return_value=user_record),
    ):
        with pytest.raises(InvalidCredentialsError):
            await service.refresh("token-for-disabled-user")


@pytest.mark.unit
async def test_logout_invalid_token(service: AuthService, mock_signer: MagicMock) -> None:
    mock_signer.verify.side_effect = AuthenticationError("invalid")
    # Should not raise
    await service.logout("garbage")


@pytest.mark.unit
async def test_logout_missing_jti(service: AuthService, mock_signer: MagicMock) -> None:
    mock_signer.verify.return_value = {"sub": "user-id", "typ": "refresh"}
    # Should not raise
    await service.logout("token-no-jti")


@pytest.mark.unit
async def test_logout_wrong_token_type(service: AuthService, mock_signer: MagicMock) -> None:
    mock_signer.verify.return_value = {"jti": str(uuid4()), "typ": "access"}
    # Should not raise, just return
    await service.logout("access-token-to-logout")


@pytest.mark.unit
async def test_logout_unexpected_error(service: AuthService, mock_signer: MagicMock) -> None:
    mock_signer.verify.side_effect = Exception("boom")
    with pytest.raises(Exception, match="boom"):
        await service.logout("valid-token")


@pytest.mark.unit
async def test_refresh_unexpected_error(service: AuthService, mock_signer: MagicMock) -> None:
    mock_signer.verify.side_effect = Exception("boom")
    with pytest.raises(Exception, match="boom"):
        await service.refresh("valid-token")


@pytest.mark.unit
async def test_logout_happy_path(service: AuthService, mock_signer: MagicMock) -> None:
    token_id = uuid4()
    mock_signer.verify.return_value = {"jti": str(token_id), "typ": "refresh"}

    with patch("app.auth.persistence.revoke_refresh_token") as mock_revoke:
        await service.logout("valid-token")
        mock_revoke.assert_called_once()
