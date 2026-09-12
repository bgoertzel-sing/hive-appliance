"""
Local adapter: connects the appliance to the local host.

C06 work package — local adapter.
"""
from __future__ import annotations

import subprocess
from typing import Any

from schemas.types import Event, Severity
from collectors.base import BaseCollector


class LocalAdapter:
    """Adapter for the local host — runs commands locally."""

    name = "local"

    def run(self, command: list[str], timeout: int = 30) -> dict[str, Any]:
        """Run a command locally and return result dict."""
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=timeout
            )
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0,
            }
        except Exception as e:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False,
            }

    def check_file(self, path: str) -> bool:
        """Check if a file exists."""
        import os
        return os.path.exists(path)

    def read_file(self, path: str) -> str | None:
        """Read a file's contents."""
        try:
            with open(path) as f:
                return f.read()
        except Exception:
            return None
