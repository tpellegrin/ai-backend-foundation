from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class UserProfile:
    """User profile domain model."""

    id: UUID
    email: str
    created_at: datetime
    updated_at: datetime
