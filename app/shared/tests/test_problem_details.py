# ruff: noqa: S101, PLR2004
import json

import pytest

from app.shared.errors import AppError, NotFoundError
from app.shared.problem_details import MEDIA_TYPE, ProblemDetails, from_app_error


@pytest.mark.unit
def test_problem_details_serialization() -> None:
    """
    Test that ProblemDetails serializes to the expected JSON shape.
    """
    problem = ProblemDetails(
        title="Not Found",
        status=404,
        detail="The requested resource was not found.",
        code="not-found",
        request_id="req-123",
        extra_info="some extra data",
    )

    serialized = problem.model_dump()
    assert serialized["type"] == "about:blank"
    assert serialized["title"] == "Not Found"
    assert serialized["status"] == 404
    assert serialized["detail"] == "The requested resource was not found."
    assert serialized["code"] == "not-found"
    assert serialized["request_id"] == "req-123"
    assert serialized["extra_info"] == "some extra data"

    # Test JSON serialization
    json_data = problem.model_dump_json()
    data = json.loads(json_data)
    assert data["type"] == "about:blank"
    assert data["extra_info"] == "some extra data"


@pytest.mark.unit
def test_from_app_error_mapping() -> None:
    """
    Test that from_app_error correctly maps AppError fields.
    """
    err = NotFoundError(detail="User 123 not found", extras={"user_id": 123})
    problem = from_app_error(err, request_id="req-456")

    assert problem.title == "Resource not found"
    assert problem.status == 404
    assert problem.detail == "User 123 not found"
    assert problem.code == "not-found"
    assert problem.request_id == "req-456"
    assert problem.model_extra is not None
    assert problem.model_extra["user_id"] == 123


@pytest.mark.unit
def test_media_type_constant() -> None:
    """
    Test that MEDIA_TYPE is correct.
    """
    assert MEDIA_TYPE == "application/problem+json"


@pytest.mark.unit
def test_no_leaks_for_unknown_errors() -> None:
    """
    Test that a generic AppError only maps explicitly allowed fields.
    """
    # Create a generic AppError
    err = AppError(
        code="internal-error",
        title="Internal Server Error",
        status=500,
        detail="Something went wrong",
    )

    problem = from_app_error(err, request_id="req-789")

    # Dump to dict and check that no internal Exception fields or Python-specific fields leaked
    data = problem.model_dump()

    expected_keys = {"type", "title", "status", "detail", "instance", "code", "request_id"}
    assert set(data.keys()) == expected_keys

    assert data["code"] == "internal-error"
    assert data["title"] == "Internal Server Error"
    assert data["status"] == 500
    assert data["detail"] == "Something went wrong"
    assert data["request_id"] == "req-789"
