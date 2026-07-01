# ruff: noqa: S101
import pytest
from opentelemetry.metrics import Meter

from app.observability.metrics import get_meter


@pytest.mark.unit
def test_get_meter() -> None:
    meter = get_meter("test-meter")
    assert isinstance(meter, Meter)
