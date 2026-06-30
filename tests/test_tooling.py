import tomllib
from pathlib import Path

import pytest


@pytest.mark.unit
def test_ruff_config_present():
    expected_line_length = 100
    expected_target_version = "py313"
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)
    assert "ruff" in config["tool"]
    assert config["tool"]["ruff"]["line-length"] == expected_line_length
    assert config["tool"]["ruff"]["target-version"] == expected_target_version


@pytest.mark.unit
def test_mypy_strict_on_app():
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)
    assert config["tool"]["mypy"]["strict"] is True
    assert "app" in config["tool"]["mypy"]["files"]
    assert config["tool"]["mypy"]["python_version"] == "3.13"


@pytest.mark.unit
def test_makefile_targets():
    makefile_path = Path(__file__).parent.parent / "Makefile"
    assert makefile_path.exists()

    with open(makefile_path) as f:
        content = f.read()

    required_targets = [
        "fmt",
        "lint",
        "typecheck",
        "test",
        "test-int",
        "migrate",
        "revision",
        "worker",
        "up",
        "down",
        "logs",
        "check",
    ]

    for target in required_targets:
        # Check that target is defined
        assert f"{target}:" in content, f"Target {target} not found in Makefile"

    # Check that all are .PHONY
    phony_line = next(line for line in content.splitlines() if line.startswith(".PHONY:"))
    for target in required_targets:
        assert target in phony_line, f"Target {target} not declared .PHONY"


@pytest.mark.unit
def test_env_example_keys():
    """Asserts that .env.example contains all keys required by the application."""
    env_example_path = Path(__file__).parent.parent / ".env.example"
    assert env_example_path.exists()

    with open(env_example_path) as f:
        content = f.read()

    example_keys = set()
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#") and "=" in line:
            key = line.split("=")[0].strip()
            example_keys.add(key)

    # Required keys as per T-109 implementation requirements
    required_keys = {
        "APP_ENV",
        "LOG_LEVEL",
        "DATABASE_URL",
        "REDIS_URL",
        "JWT_PRIVATE_KEY",
        "JWT_PUBLIC_KEY",
        "JWT_ISSUER",
        "JWT_AUDIENCE",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_CHAT_MODEL",
        "OPENAI_EMBEDDING_MODEL",
        "BLOB_STORAGE_BACKEND",
        "BLOB_LOCAL_DIR",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "ARQ_REDIS_URL",
        "LLM_MONTHLY_BUDGET_USD",
        "LLM_MODEL_ALLOWLIST",
    }

    for key in required_keys:
        assert key in example_keys, f"Key {key} missing from .env.example"
