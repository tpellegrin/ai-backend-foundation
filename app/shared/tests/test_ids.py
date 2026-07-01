# ruff: noqa: S101, PLR2004
import uuid

import pytest

from app.shared.ids import new_id, new_request_id


@pytest.mark.unit
def test_new_id_is_valid_uuid() -> None:
    id_str = new_id()
    val = uuid.UUID(id_str)
    assert str(val) == id_str
    # UUIDv7 preferred; fallback to v4 in Python < 3.14
    if hasattr(uuid, "uuid7"):
        assert val.version == 7
    else:
        assert val.version == 4


@pytest.mark.unit
def test_new_id_is_unique() -> None:
    ids = {new_id() for _ in range(100)}
    assert len(ids) == 100


@pytest.mark.unit
def test_new_request_id_is_valid_uuid() -> None:
    id_str = new_request_id()
    val = uuid.UUID(id_str)
    assert str(val) == id_str
    assert val.version == 4


@pytest.mark.unit
def test_new_request_id_is_unique() -> None:
    ids = {new_request_id() for _ in range(100)}
    assert len(ids) == 100
