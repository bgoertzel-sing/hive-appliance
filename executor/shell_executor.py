"""
Shell executor: runs repair commands via subprocess.

C03/C04 work packages — real execution.

P0 fixes:
  F1: Verb validation before execution.
  F5: Not a simulation executor.
  F6: Never sets verified=True (verifier's job).
  F13: Timeout capping.
"""
from __future__ import annotations

import subprocess
import time
from typing import Any

from schemas.types import Receipt, Plan, ALLOWED_VERBS
from executor.base import BaseExecutor, HARD_TIMEOUT_CAP


class ShellExecutor(BaseExecutor):
    """Executes repair steps via shell subprocess."""

    name = "shell"
    is_simulation = False

    def execute_step(self, step: dict[str, Any], plan: Plan, step_index: int) -> Receipt:
        """Execute a plan step as a shell command.

        F1: Validates verb against ALLOWED_VERBS.
        F6: Never sets verified=True.
        F13: Timeout capped.
        """
        # F1: Validate verb
        errors = self.validate_step(step)
        if errors:
            return Receipt(
                plan_id=plan.id,
                step_index=step_index,
                verb=step.get("verb", "unknown"),
                target=step.get("command", ""),
                exit_code=-3,
                stdout="",
                stderr=f"Validation errors: {errors}",
                duration_ms=0.0,
                verified=False,
                simulated=False,
                attempt_id=getattr(plan, "attempt_id", ""),
            )

        command = step.get("command", "")
        timeout = min(step.get("timeout", 30), HARD_TIMEOUT_CAP)  # F13

        start = time.time()
        try:
            result = subprocess.run(
                command, shell=True,
                capture_output=True, text=True, timeout=timeout,
            )
            elapsed = (time.time() - start) * 1000
            return Receipt(
                plan_id=plan.id,
                step_index=step_index,
                verb=step.get("verb", ""),
                target=command,
                exit_code=result.returncode,
                stdout=result.stdout[:4096],   # F13: cap output size
                stderr=result.stderr[:4096],
                duration_ms=elapsed,
                verified=False,  # F6: Never set by executor
                simulated=False,
                attempt_id=getattr(plan, "attempt_id", ""),
            )
        except subprocess.TimeoutExpired:
            elapsed = (time.time() - start) * 1000
            return Receipt(
                plan_id=plan.id,
                step_index=step_index,
                verb=step.get("verb", ""),
                target=command,
                exit_code=-1,
                stdout="",
                stderr=f"Timeout after {timeout}s",
                duration_ms=elapsed,
                verified=False,
                simulated=False,
                attempt_id=getattr(plan, "attempt_id", ""),
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return Receipt(
                plan_id=plan.id,
                step_index=step_index,
                verb=step.get("verb", ""),
                target=command,
                exit_code=-2,
                stdout="",
                stderr=str(e)[:4096],
                duration_ms=elapsed,
                verified=False,
                simulated=False,
                attempt_id=getattr(plan, "attempt_id", ""),
            )
