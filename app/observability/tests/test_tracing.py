# ruff: noqa: S101
import pytest
from opentelemetry.trace import Tracer

from app.observability.tracing import build_resource, get_tracer


@pytest.mark.unit
def test_build_resource() -> None:
    service_name = "test-service"
    env = "test-env"
    resource = build_resource(service_name, env)

    assert resource.attributes["service.name"] == service_name
    assert resource.attributes["deployment.environment"] == env


@pytest.mark.unit
def test_get_tracer() -> None:
    tracer = get_tracer("test-tracer")
    assert isinstance(tracer, Tracer)
