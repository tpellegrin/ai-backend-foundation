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
