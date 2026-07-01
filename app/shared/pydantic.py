from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base Pydantic model with strict configuration for the project."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
    )
