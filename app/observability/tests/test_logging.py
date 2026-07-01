# ruff: noqa: S101
import json
from uuid import uuid4

import pytest
from _pytest.capture import CaptureFixture

from app.observability.correlation import request_id_var
from app.observability.logging import configure_logging, get_logger


@pytest.mark.unit
def test_get_logger() -> None:
    logger = get_logger("test")
    assert logger is not None
    assert hasattr(logger, "info")
    assert hasattr(logger, "error")


@pytest.mark.unit
def test_json_logging_format(capsys: CaptureFixture[str]) -> None:
    # Configure logging for JSON output
    configure_logging(level="INFO", json=True)

    logger = get_logger("test")

    request_id = str(uuid4())
    token = request_id_var.set(request_id)

    try:
        logger.info("test message", extra_field="extra_value")
    finally:
        request_id_var.reset(token)

    captured = capsys.readouterr()
    log_line = captured.out.strip()

    # Verify it's parseable JSON
    data = json.loads(log_line)

    assert data["event"] == "test message"
    assert "timestamp" in data
    assert data["level"] == "info"
    assert data["request_id"] == request_id
    assert data["extra_field"] == "extra_value"


@pytest.mark.unit
def test_logging_without_request_id(capsys: CaptureFixture[str]) -> None:
    configure_logging(level="INFO", json=True)

    logger = get_logger("test")

    # Ensure request_id_var is empty
    token = request_id_var.set("")
    try:
        logger.info("no request id")
    finally:
        request_id_var.reset(token)

    captured = capsys.readouterr()
    log_line = captured.out.strip()
    data = json.loads(log_line)

    assert data["event"] == "no request id"
    assert "request_id" not in data


@pytest.mark.unit
def test_event_renamer(capsys: CaptureFixture[str]) -> None:
    configure_logging(level="INFO", json=True)
    logger = get_logger("test")

    # Passing None as event and providing msg as kwarg
    logger.info(None, msg="renamed message")

    captured = capsys.readouterr()
    log_line = captured.out.strip()
    data = json.loads(log_line)

    assert data["event"] == "renamed message"
    assert "msg" not in data
