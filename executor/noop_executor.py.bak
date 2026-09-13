"""
Noop executor: simulates repair steps without running commands.

C04 work package — dry-run safety control.
"""
from __future__ import annotations

from typing import Any

from executor.base import BaseExecutor
from schemas.types import Receipt, Plan


class NoopExecutor(BaseExecutor):
    """Executes no commands — records what would be done.

    Used in dry-run mode to preview repair plans without side effects.
    """

    name = "noop_executor"

    def execute_step(self, step: dict[str, Any], plan: Plan, step_index: int) -> Receipt:
        command_str = step.get("command", "")
        return Receipt(
            plan_id=plan.id,
            step_index=step_index,
            verb=step.get("verb", "noop"),
            target=command_str,
            exit_code=0,
            stdout=f"[dry-run] would execute: {command_str}",
            stderr="",
            duration_ms=0.0,
            verified=True,  # Always verified in dry-run (no actual execution)
        )
