from __future__ import annotations

from argon2 import PasswordHasher as Argon2Hasher
from argon2 import Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


class Argon2PasswordHasher:
    """Argon2id implementation of the PasswordHasher port.

    This adapter uses the high-level argon2-cffi PasswordHasher with
    explicit Argon2id type and configurable tuning parameters.
    It structurally satisfies the PasswordHasher Protocol.
    """

    def __init__(
        self,
        time_cost: int,
        memory_cost: int,
        parallelism: int,
        hash_len: int,
        salt_len: int,
    ) -> None:
        """Initialize the hasher with tuning parameters.

        Args:
            time_cost: Number of passes.
            memory_cost: Memory usage in KiB.
            parallelism: Number of parallel threads.
            hash_len: Length of the hash in bytes.
            salt_len: Length of the salt in bytes.
        """
        self._hasher = Argon2Hasher(
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
            hash_len=hash_len,
            salt_len=salt_len,
            type=Type.ID,
        )

    def hash(self, password: str) -> str:
        """Hash a plaintext password using Argon2id."""
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        """Verify a password against an Argon2id hash.

        Returns False on mismatch or if the hash is malformed.
        Does not leak provider-specific exceptions.
        """
        try:
            # argon2-cffi: verify(hash, password)
            return self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, password_hash: str) -> bool:
        """Check if the hash was created with different parameters."""
        try:
            return self._hasher.check_needs_rehash(password_hash)
        except InvalidHashError:
            # If it's not a valid Argon2 hash, it definitely needs to be replaced
            # when the user next provides their password.
            return True
