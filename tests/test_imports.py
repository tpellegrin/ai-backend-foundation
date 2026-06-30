import pytest
import shutil
import subprocess


@pytest.mark.unit
def test_import_linter_passes() -> None:
    """Verifies that the import linter runs and finds no violations."""
    uv_path = shutil.which("uv")
    if not uv_path:
        msg = "uv executable not found"
        raise RuntimeError(msg)

    # Intentionally no --config flag: relies on auto-discovery of `.importlinter`.
    # Adding --config would mask a missing/renamed config file and drift from the
    # Makefile / pre-commit / CI invocation (see docs/implementation/rules.md §5).
    result = subprocess.run(  # noqa: S603
        [uv_path, "run", "lint-imports"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"Import linter failed with output:\n{result.stdout}\n{result.stderr}"
    )
