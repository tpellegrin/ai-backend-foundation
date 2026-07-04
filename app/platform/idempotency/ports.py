from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable


@dataclass(frozen=True)
class IdempotencyRecord:
    """
    Result of an idempotency check.
    """

    status: Literal["new", "in_flight", "done"]
    response_hash: str | None = None


@runtime_checkable
class IdempotencyStore(Protocol):
    """
    Port for idempotency storage.

    Used by the API layer to ensure exactly-once processing of requests
    identified by an idempotency key.
    """

    async def begin(self, key: str, ttl_s: int) -> IdempotencyRecord:
        """
        Attempt to start a new idempotent operation.

        If the key does not exist, it is created with 'in_flight' status
        and 'new' status is returned in the record.
        If the key exists, the current record is returned.
        """
        ...

    async def complete(self, key: str, response_hash: str) -> None:
        """
        Mark an operation as completed with a response hash.
        """
        ...

    async def get(self, key: str) -> IdempotencyRecord | None:
        """
        Retrieve the current status of an operation by key.
        """
        ...
