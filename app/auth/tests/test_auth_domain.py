# ruff: noqa: S101, S105, S106
import inspect
from datetime import UTC, datetime
from uuid import uuid4

import pytest

import app.auth.domain
from app.auth.domain import RefreshTokenRecord, UserAuthRecord


def test_user_auth_record_is_immutable() -> None:
    record = UserAuthRecord(
        id=uuid4(),
        email="test@example.com",
        password_hash="hash",
        created_at=datetime.now(UTC),
        tenant_id=uuid4(),
        disabled=False,
    )
    with pytest.raises(AttributeError):
        # dataclass(frozen=True) should prevent assignment
        record.disabled = True  # type: ignore[misc]


def test_refresh_token_record_is_immutable() -> None:
    record = RefreshTokenRecord(
        id=uuid4(),
        user_id=uuid4(),
        family_id=uuid4(),
        hash="hash",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC),
        revoked_at=None,
        replaced_by=None,
    )
    with pytest.raises(AttributeError):
        # dataclass(frozen=True) should prevent assignment
        record.revoked_at = datetime.now(UTC)  # type: ignore[misc]


def test_user_auth_record_fields() -> None:
    user_id = uuid4()
    tenant_id = uuid4()
    now = datetime.now(UTC)
    record = UserAuthRecord(
        id=user_id,
        email="test@example.com",
        password_hash="hash",
        created_at=now,
        tenant_id=tenant_id,
        disabled=True,
    )
    assert record.id == user_id
    assert record.email == "test@example.com"
    assert record.password_hash == "hash"
    assert record.created_at == now
    assert record.tenant_id == tenant_id
    assert record.disabled is True


def test_refresh_token_record_fields() -> None:
    token_id = uuid4()
    user_id = uuid4()
    family_id = uuid4()
    now = datetime.now(UTC)
    record = RefreshTokenRecord(
        id=token_id,
        user_id=user_id,
        family_id=family_id,
        hash="hash",
        issued_at=now,
        expires_at=now,
        revoked_at=now,
        replaced_by=token_id,
    )
    assert record.id == token_id
    assert record.user_id == user_id
    assert record.family_id == family_id
    assert record.hash == "hash"
    assert record.issued_at == now
    assert record.expires_at == now
    assert record.revoked_at == now
    assert record.replaced_by == token_id


def test_auth_domain_boundary_imports() -> None:
    # T-905 §Tests required 1: Domain types do not import SQLAlchemy or infrastructure
    source = inspect.getsource(app.auth.domain)
    assert "sqlalchemy" not in source.lower()
    assert "app.infrastructure" not in source.lower()
