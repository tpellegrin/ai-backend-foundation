from dataclasses import dataclass
from typing import NoReturn


@dataclass(frozen=True)
class Ok[T]:
    """Successful result containing a value."""

    value: T

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self.value


@dataclass(frozen=True)
class Err[E: Exception]:
    """Failed result containing an exception."""

    error: E

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    def unwrap(self) -> NoReturn:
        raise self.error


type Result[T, E: Exception] = Ok[T] | Err[E]
