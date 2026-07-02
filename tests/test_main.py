import fastapi
import pytest

import app.main


@pytest.mark.unit
def test_app_instance_is_fastapi() -> None:
    """
    Assert that the eager app binding in the entrypoint is a FastAPI instance.

    This test relies on the repository-wide `tests/conftest.py` to seed
    the environment for AppSettings at collection time.
    """
    assert isinstance(app.main.app, fastapi.FastAPI)
