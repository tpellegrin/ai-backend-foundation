from unittest.mock import MagicMock, patch

import pytest

from app.core.wiring.observability import apply_httpx_instrumentation


@pytest.mark.unit
def test_apply_httpx_instrumentation_calls_instrument_if_enabled() -> None:
    settings = MagicMock()
    settings.otel.endpoint = "http://localhost:4317"

    with patch("app.core.wiring.observability.HTTPXClientInstrumentor") as mock_instrumentor:
        apply_httpx_instrumentation(settings)
        mock_instrumentor.return_value.instrument.assert_called_once()


@pytest.mark.unit
def test_apply_httpx_instrumentation_does_not_call_instrument_if_disabled() -> None:
    settings = MagicMock()
    settings.otel.endpoint = None

    with patch("app.core.wiring.observability.HTTPXClientInstrumentor") as mock_instrumentor:
        apply_httpx_instrumentation(settings)
        mock_instrumentor.return_value.instrument.assert_not_called()
