from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import Tracer


def build_resource(service_name: str, env: str) -> Resource:
    """Build an OTel resource with service name and environment."""
    return Resource.create(
        {
            "service.name": service_name,
            "deployment.environment": env,
        }
    )


def get_tracer(name: str) -> Tracer:
    """Get a tracer for the given name."""
    return trace.get_tracer(name)
