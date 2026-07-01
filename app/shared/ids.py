import uuid


def new_id() -> str:
    """Generate a new unique ID (UUIDv7 preferred, fallback to UUIDv4)."""
    # uuid7 is available in Python 3.14+; fallback to uuid4 in 3.13
    if hasattr(uuid, "uuid7"):
        return str(uuid.uuid7())
    return str(uuid.uuid4())


def new_request_id() -> str:
    """Generate a new unique request ID (UUIDv4)."""
    return str(uuid.uuid4())
