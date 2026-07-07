# ruff: noqa: S101, S105, PLR2004
import pytest

from app.auth.adapters.argon2_hasher import Argon2PasswordHasher
from app.auth.ports import PasswordHasher


@pytest.fixture
def cheap_hasher() -> Argon2PasswordHasher:
    # Use cheap settings for tests to keep them fast
    return Argon2PasswordHasher(
        time_cost=1,
        memory_cost=512,
        parallelism=1,
        hash_len=16,
        salt_len=8,
    )


@pytest.mark.unit
def test_argon2_hasher_conforms_to_port(cheap_hasher: Argon2PasswordHasher) -> None:
    """Ensure Argon2PasswordHasher structurally satisfies the PasswordHasher Protocol."""
    assert isinstance(cheap_hasher, PasswordHasher)


@pytest.mark.unit
def test_argon2_hasher_hash_verify_round_trip(cheap_hasher: Argon2PasswordHasher) -> None:
    """Test that a hashed password can be verified."""
    password = "secret-password"
    password_hash = cheap_hasher.hash(password)

    assert password_hash != password
    assert "$argon2id$" in password_hash

    assert cheap_hasher.verify(password, password_hash) is True
    assert cheap_hasher.verify("wrong-password", password_hash) is False


@pytest.mark.unit
def test_argon2_hasher_verify_invalid_hash(cheap_hasher: Argon2PasswordHasher) -> None:
    """Test that verify returns False for malformed hashes without leaking exceptions."""
    assert cheap_hasher.verify("password", "not-a-hash") is False
    assert cheap_hasher.verify("password", "$argon2id$v=19$m=512,t=1,p=1$garbage") is False


@pytest.mark.unit
def test_argon2_hasher_needs_rehash(cheap_hasher: Argon2PasswordHasher) -> None:
    """Test that needs_rehash correctly identifies when parameters have changed."""
    password = "password"
    password_hash = cheap_hasher.hash(password)

    # Current settings should not need rehash
    assert cheap_hasher.needs_rehash(password_hash) is False

    # A hasher with different parameters should indicate a rehash is needed
    different_hasher = Argon2PasswordHasher(
        time_cost=2,  # different from cheap_hasher (1)
        memory_cost=512,
        parallelism=1,
        hash_len=16,
        salt_len=8,
    )

    assert different_hasher.needs_rehash(password_hash) is True


@pytest.mark.unit
def test_argon2_hasher_needs_rehash_invalid_hash(cheap_hasher: Argon2PasswordHasher) -> None:
    """Test that needs_rehash handles invalid hashes gracefully."""
    assert cheap_hasher.needs_rehash("not-a-hash") is True


@pytest.mark.unit
def test_argon2_hasher_construction_from_primitive_values() -> None:
    """Verify the adapter can be constructed from primitive values (Configuration Boundary)."""
    hasher = Argon2PasswordHasher(
        time_cost=1,
        memory_cost=512,
        parallelism=1,
        hash_len=16,
        salt_len=8,
    )
    assert hasher._hasher.time_cost == 1
    assert hasher._hasher.memory_cost == 512
