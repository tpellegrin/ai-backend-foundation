import tomllib
from pathlib import Path


def test_ruff_config_present():
    expected_line_length = 100
    expected_target_version = "py313"
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)
    assert "ruff" in config["tool"]
    assert config["tool"]["ruff"]["line-length"] == expected_line_length
    assert config["tool"]["ruff"]["target-version"] == expected_target_version


def test_mypy_strict_on_app():
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)
    assert config["tool"]["mypy"]["strict"] is True
    assert "app" in config["tool"]["mypy"]["files"]
    assert config["tool"]["mypy"]["python_version"] == "3.13"
