# ruff: noqa: S101
import pytest
from pydantic import Field, ValidationError

from app.shared.pydantic import BaseSchema


class SampleSchema(BaseSchema):
    name: str
    age: int


@pytest.mark.unit
def test_baseschema_frozen() -> None:
    obj = SampleSchema(name="Alice", age=30)
    with pytest.raises(ValidationError):
        # frozen=True forbids mutation
        obj.name = "Bob"  # type: ignore[misc]


@pytest.mark.unit
def test_baseschema_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        # extra="forbid" prevents unknown fields
        SampleSchema(name="Alice", age=30, extra_field="forbidden")  # type: ignore[call-arg]


@pytest.mark.unit
def test_baseschema_populate_by_name() -> None:
    class AliasedSchema(BaseSchema):
        first_name: str = Field(alias="firstName")

    # Should work with alias
    obj1 = AliasedSchema(firstName="Alice")  # type: ignore[call-arg]
    assert obj1.first_name == "Alice"

    # Should also work with field name because of populate_by_name=True
    obj2 = AliasedSchema(first_name="Alice")
    assert obj2.first_name == "Alice"
