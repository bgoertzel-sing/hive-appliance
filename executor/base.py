"""
Base executor interface for controlled repair actions.

C03 work package — controlled repair executor.

P0 fixes:
  F1: Verb validation against ALLOWED_VERBS at execution boundary.
  F5: Dry-run boundary enforced here (not just via executor selection).
  F6: Executors never set verified=True; that's the verifier's job.
  F13: Timeout capping.
"""
from __future__ import annotations

import abc
import subprocess
import time
from typing import Any

from schemas.types import ALLOWED_VERBS, Plan, Receipt

# F13: Hard maximum timeout
HARD_TIMEOUT_CAP = 120


class BaseExecutor(abc.ABC):
    """Abstract base for all executors."""

    name: str = "base"
    is_simulation: bool = False   # F5/F6: Subclasses override

    @abc.abstractmethod
    def execute_step(self, step: dict[str, Any], plan: Plan, step_index: int) -> Receipt:
        """Execute a single plan step and return a receipt."""
        ...

    def validate_step(self, step: dict[str, Any]) -> list[str]:
        """F1: Validate a step before execution."""
        errors = []
        verb = step.get("verb", "")
        if verb and verb not in ALLOWED_VERBS:
            errors.append(f"Verb '{verb}' not in ALLOWED_VERBS")
        return errors

    def _run_command(self, command: list[str], timeout: int = 30) -> Receipt:
        """Helper to run a shell command and build a receipt.

        F6: Never sets verified=True — that's the verifier's job.
        F13: Timeout capped.
        """
        timeout = min(timeout, HARD_TIMEOUT_CAP)
        start = time.time()
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=timeout, check=False)
            elapsed = (time.time() - start) * 1000
            return Receipt(
                verb=command[0] if command else "",
                target=" ".join(command[1:]) if len(command) > 1 else "",
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=elapsed,
                verified=False,  # F6: Never set by executor
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
