"""
No-op executor for dry-run / simulation mode.

P0 fixes:
  F5: NoOpExecutor returns simulated receipts that are NOT verified.
  F6: Does not set verified=True.
"""
from __future__ import annotations

from schemas.types import Receipt, Plan


class NoopExecutor:
    """Executor that does nothing but records simulated receipts.

    F5: In dry-run mode, receipts are simulated and NOT verified.
    F6: Does not set verified=True (verifier does that independently).
    """

    name = "noop_executor"

    def execute_step(self, step: dict, plan: Plan, index: int) -> Receipt:
        return Receipt(
            plan_id=plan.id,
            step_index=index,
            verb=step.get("verb", ""),
            target=step.get("target", ""),
            exit_code=0,
            stdout="[noop]",
            stderr="",
            duration_ms=0.0,
            verified=False,  # F5/F6: NOT verified
            simulated=True,
        )

    def execute(self, plan: Plan) -> list[Receipt]:
        receipts: list[Receipt] = []
        for i, step in enumerate(plan.steps):
            receipts.append(self.execute_step(step, plan, i))
        return receipts
