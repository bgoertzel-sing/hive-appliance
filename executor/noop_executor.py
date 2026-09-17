"""
No-op executor for dry-run / simulation mode.

C03 work package — executor stub.

P0 fixes:
  F5: Receipts marked simulated=True.
  F6: Never sets verified=True.
"""
from __future__ import annotations

from typing import Any

from schemas.types import Receipt, Plan
from executor.base import BaseExecutor


class NoopExecutor(BaseExecutor):
    """Simulates execution without side effects."""

    name = "noop"
    is_simulation = True  # F5/F6: Signals dry-run mode

    def execute_step(self, step: dict[str, Any], plan: Plan, step_index: int) -> Receipt:
        """Return a simulated receipt without executing anything.

        F5: Receipt is marked simulated=True.
        F6: verified is always False (verifier decides).
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
                simulated=True,
                attempt_id=getattr(plan, "attempt_id", ""),
            )

        return Receipt(
            plan_id=plan.id,
            step_index=step_index,
            verb=step.get("verb", "noop"),
            target=step.get("command", ""),
            exit_code=0,
            stdout="[simulated]",
            stderr="",
            duration_ms=0.0,
            verified=False,  # F6: Never set by executor
            simulated=True,  # F5: Dry-run marker
            attempt_id=getattr(plan, "attempt_id", ""),
        )
