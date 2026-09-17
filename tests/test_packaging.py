"""M2 (C08) — Packaging smoke tests.

Verify the project can be built, installed, and the entry point resolves.
"""
import importlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# ---- importability ----

def test_import_cli():
    """cli module is importable."""
    import cli  # noqa: F401


def test_import_controller():
    """controller.appliance is importable."""
    from controller import appliance  # noqa: F401


def test_import_schemas():
    """schemas.types is importable."""
    from schemas import types  # noqa: F401


def test_import_collectors():
    """All collector modules are importable."""
    from collectors import base, file_collector, host_collector, service_collector  # noqa: F401


def test_import_adapters():
    """adapters.local_adapter is importable."""
    from adapters import local_adapter  # noqa: F401


def test_import_executor():
    """executor modules are importable."""
    from executor import base, shell_executor, noop_executor  # noqa: F401


def test_import_verifier():
    """verifier modules are importable."""
    from verifier import base, exit_code_verifier, file_verifier  # noqa: F401


def test_import_reasoning():
    """reasoning.planner is importable."""
    from reasoning import planner  # noqa: F401


def test_import_profiles():
    """profiles.manager is importable."""
    from profiles import manager  # noqa: F401


# ---- pyproject.toml ----

def test_pyproject_exists():
    """pyproject.toml exists at repo root."""
    assert (ROOT / "pyproject.toml").is_file()


def test_pyproject_parseable():
    """pyproject.toml is valid TOML (Python 3.11+ has tomllib)."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]
    data = (ROOT / "pyproject.toml").read_text()
    parsed = tomllib.loads(data)
    assert parsed["project"]["name"] == "hive-appliance"
    assert "version" in parsed["project"]


# ---- entry-point resolution ----

def test_cli_main_callable():
    """cli.main is a callable function."""
    from cli import main
    assert callable(main)


# ---- wheel build (slow, only if build is available) ----

def test_wheel_build():
    """python -m build --wheel succeeds."""
    try:
        import build as _  # noqa: F401
    except ImportError:
        import pytest
        pytest.skip("build package not installed")
    result = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(ROOT / "dist")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"Build failed:\n{result.stderr}"
    wheels = list((ROOT / "dist").glob("hive_appliance-*.whl"))
    assert len(wheels) >= 1, "No wheel produced"


# ---- Dockerfile exists ----

def test_dockerfile_exists():
    """Dockerfile exists at repo root."""
    assert (ROOT / "Dockerfile").is_file()


# ---- Makefile exists ----

def test_makefile_exists():
    """Makefile exists at repo root."""
    assert (ROOT / "Makefile").is_file()
