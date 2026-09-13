"""
Local adapter for executing operations on the local host.

P0 fixes:
  F1: Removed generic command execution; uses registered verbs only.
"""
from __future__ import annotations

import os
import subprocess
from typing import Any

from schemas.types import ALLOWED_VERBS


class LocalAdapter:
    """Adapter for local host operations using registered verbs."""

    def __init__(self):
        self._verb_handlers = {
            "touch": self._handle_touch,
            "verify": self._handle_verify,
            "inspect": self._handle_inspect,
            "restart": self._handle_restart,
            "noop": self._handle_noop,
        }

    def run(self, verb: str, target: str = "", **kwargs) -> dict[str, Any]:
        """F1: Execute a registered verb, not arbitrary commands."""
        if verb not in ALLOWED_VERBS:
            raise ValueError(f"Verb '{verb}' not allowed. Allowed: {ALLOWED_VERBS}")
        handler = self._verb_handlers.get(verb)
        if not handler:
            raise ValueError(f"No handler for verb '{verb}'")
        return handler(target, **kwargs)

    def _handle_touch(self, target: str, **kw) -> dict[str, Any]:
        if not target:
            raise ValueError("touch requires a target path")
        open(target, "a").close()
        return {"exit_code": 0, "stdout": "", "stderr": ""}

    def _handle_verify(self, target: str, **kw) -> dict[str, Any]:
        exists = os.path.exists(target) if target else False
        return {"exit_code": 0 if exists else 1, "stdout": str(exists), "stderr": ""}

    def _handle_inspect(self, target: str, **kw) -> dict[str, Any]:
        result = subprocess.run(
            ["systemctl", "status", target],
            capture_output=True, text=True, timeout=10
        )
        return {"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}

    def _handle_restart(self, target: str, **kw) -> dict[str, Any]:
        result = subprocess.run(
            ["systemctl", "restart", target],
            capture_output=True, text=True, timeout=30
        )
        return {"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}

    def _handle_noop(self, target: str, **kw) -> dict[str, Any]:
        return {"exit_code": 0, "stdout": "[noop]", "stderr": ""}

    def read_file(self, path: str, max_bytes: int = 4096) -> str:
        """Read file with size limit (F13: resource limits)."""
        with open(path, "r") as f:
            return f.read(max_bytes)
