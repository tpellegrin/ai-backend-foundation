# ruff: noqa: S101, PLR2004
from typing import TypeAliasType

import pytest

from app.shared.result import Err, Ok, Result


@pytest.mark.unit
def test_ok_behavior() -> None:
    res: Ok[int] = Ok(42)
    assert res.is_ok() is True
    assert res.is_err() is False
    assert res.unwrap() == 42


@pytest.mark.unit
def test_err_behavior() -> None:
    exc = ValueError("bad thing")
    res: Err[ValueError] = Err(exc)
    assert res.is_ok() is False
    assert res.is_err() is True
    with pytest.raises(ValueError, match="bad thing"):
        res.unwrap()


@pytest.mark.unit
def test_result_type_alias() -> None:
    # PEP 695 type aliases are TypeAliasType objects in 3.12+
    assert isinstance(Result, TypeAliasType)
    assert Result.__name__ == "Result"
