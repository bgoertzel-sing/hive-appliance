"""
Base executor interface for controlled repair actions.

C03 work package — controlled repair executor.
"""
from __future__ import annotations

import abc
import subprocess
import time
from typing import Any

from schemas.types import Receipt, Plan


class BaseExecutor(abc.ABC):
    """Abstract base for all executors."""

    name: str = "base"

    @abc.abstractmethod
    def execute_step(self, step: dict[str, Any], plan: Plan, step_index: int) -> Receipt:
        """Execute a single plan step and return a receipt."""
        ...

    def _run_command(self, command: list[str], timeout: int = 30) -> Receipt:
        """Helper to run a shell command and build a receipt."""
        start = time.time()
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=timeout
            )
            elapsed = (time.time() - start) * 1000
            return Receipt(
                verb=command[0] if command else "",
                target=" ".join(command[1:]) if len(command) > 1 else "",
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=elapsed,
                verified=(result.returncode == 0),
            )
        except subprocess.TimeoutExpired:
            elapsed = (time.time() - start) * 1000
            return Receipt(
                verb=command[0] if command else "",
                target=" ".join(command[1:]) if len(command) > 1 else "",
                exit_code=-1,
                stdout="",
                stderr=f"Timeout after {timeout}s",
                duration_ms=elapsed,
                verified=False,
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return Receipt(
                verb=command[0] if command else "",
                target=" ".join(command[1:]) if len(command) > 1 else "",
                exit_code=-2,
                stdout="",
                stderr=str(e),
                duration_ms=elapsed,
                verified=False,
            )
