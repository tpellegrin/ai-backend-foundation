from opentelemetry import metrics
from opentelemetry.metrics import Meter


def get_meter(name: str) -> Meter:
    """Get a meter for the given name."""
    return metrics.get_meter(name)
