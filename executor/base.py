"""
Executor interface and base implementation.

P0 fixes:
  F6: Executor no longer sets verified; only returns raw execution results.
"""
from __future__ import annotations

import subprocess
import time
from typing import Any

from schemas.types import Receipt, Plan, ALLOWED_VERBS


class BaseExecutor:
    """Base class for executors that run repair steps."""

    def execute_step(self, step: dict[str, Any], plan: Plan,
                     index: int) -> Receipt:
        """Execute a single step and return a Receipt.

        F6: The receipt.verified field is NOT set here.
        Only the independent verifier should set verified.
        """
        raise NotImplementedError

    def execute(self, plan: Plan) -> list[Receipt]:
        """Execute all steps in a plan."""
        receipts: list[Receipt] = []
        for i, step in enumerate(plan.steps):
            receipt = self.execute_step(step, plan, i)
            receipts.append(receipt)
        return receipts


class ShellExecutor(BaseExecutor):
    """Executes shell commands for repair steps."""

    def execute_step(self, step: dict[str, Any], plan: Plan,
                     index: int) -> Receipt:
        verb = step.get("verb", "")
        command = step.get("command", "")
        target = step.get("target", "")
        timeout = step.get("timeout", 30)

        start = time.time()
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration_ms = (time.time() - start) * 1000
            return Receipt(
                plan_id=plan.id,
                step_index=index,
                verb=verb,
                target=target,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=duration_ms,
                verified=False,  # F6: NOT set by executor
            )
        except subprocess.TimeoutExpired as e:
            duration_ms = (time.time() - start) * 1000
            return Receipt(
                plan_id=plan.id,
                step_index=index,
                verb=verb,
                target=target,
                exit_code=-1,
                stdout=e.stdout.decode() if e.stdout else "",
                stderr=e.stderr.decode() if e.stderr else str(e),
                duration_ms=duration_ms,
                verified=False,
            )
