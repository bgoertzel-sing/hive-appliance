"""
Shell executor: runs shell commands for repair steps.

C03 work package — controlled repair executor.
"""
from __future__ import annotations

import shlex
from typing import Any

from executor.base import BaseExecutor
from schemas.types import Receipt, Plan


class ShellExecutor(BaseExecutor):
    """Executes shell command steps."""

    name = "shell_executor"

    def execute_step(self, step: dict[str, Any], plan: Plan, step_index: int) -> Receipt:
        command_str = step.get("command", "")
        timeout = step.get("timeout", 30)

        if not command_str:
            return Receipt(
                plan_id=plan.id,
                step_index=step_index,
                verb="noop",
                target="",
                exit_code=1,
                stderr="No command specified",
                verified=False,
            )

        command = shlex.split(command_str)
        receipt = self._run_command(command, timeout=timeout)
        receipt.plan_id = plan.id
        receipt.step_index = step_index
        return receipt
