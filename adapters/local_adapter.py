"""
Local adapter: connects the appliance to the local host.

C06 work package — local adapter.

P0 fixes:
  F1: Verb-based dispatch; refuses unregistered verbs.
  F13: Resource limits on file reads.
"""
from __future__ import annotations

import os
import subprocess
from typing import Any

from schemas.types import ALLOWED_VERBS


class LocalAdapter:
    """Adapter for local host operations using registered verbs.

    F1: Only ALLOWED_VERBS are accepted via run().
    Legacy run_command() is kept for backward compat but logs a warning.
    """

    name = "local"

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
        return {"exit_code": 0, "stdout": "", "stderr": "", "success": True}

    def _handle_verify(self, target: str, **kw) -> dict[str, Any]:
        exists = os.path.exists(target) if target else False
        return {"exit_code": 0 if exists else 1, "stdout": str(exists), "stderr": "", "success": exists}

    def _handle_inspect(self, target: str, **kw) -> dict[str, Any]:
        try:
            result = subprocess.run(
                ["stat", target] if target else ["uname", "-a"],
                capture_output=True, text=True, timeout=10, check=False)
            return {"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "success": result.returncode == 0}
        except Exception as e:
            return {"exit_code": -1, "stdout": "", "stderr": str(e), "success": False}

    def _handle_restart(self, target: str, **kw) -> dict[str, Any]:
        try:
            result = subprocess.run(
                ["systemctl", "restart", target],
                capture_output=True, text=True, timeout=30, check=False)
            return {"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "success": result.returncode == 0}
        except Exception as e:
            return {"exit_code": -1, "stdout": "", "stderr": str(e), "success": False}

    def _handle_noop(self, target: str, **kw) -> dict[str, Any]:
        return {"exit_code": 0, "stdout": "[noop]", "stderr": "", "success": True}

    # Legacy compat
    def check_file(self, path: str) -> bool:
        """Check if a file exists."""
        return os.path.exists(path)

    def read_file(self, path: str, max_bytes: int = 4096) -> str | None:
        """Read a file's contents. F13: size-limited."""
        try:
            with open(path) as f:
                return f.read(max_bytes)
        except Exception:
            return None
