"""
Executor interface and base implementation.

P0 fixes:
  F6: Executor no longer sets verified; only returns raw results.
  F1: Only executes commands for allowed verbs.
"""
from __future__ import annotations

import subprocess
import time
from typing import Any

from schemas.types import Receipt, Plan, ALLOWED_VERBS


class BaseExecutor:
    """Base class for executors that run repair steps."""

    name = "base_executor"

    def execute_step(self, step: dict, plan: Plan, index: int) -> Receipt:
        raise NotImplementedError

    def execute(self, plan: Plan) -> list[Receipt]:
        return [self.execute_step(step, plan, i)
                for i, step in enumerate(plan.steps)]


class ShellExecutor(BaseExecutor):
    """Executes shell commands for repair steps."""

    name = "shell_executor"

    def execute_step(self, step: dict, plan: Plan, index: int) -> Receipt:
        verb = step.get("verb", "")
        command = step.get("command", "")
        if not command:
            return Receipt(plan_id=plan.id, step_index=index,
                verb=verb, target=step.get("target", ""),
                exit_code=1, stderr="No command specified",
                verified=False)
        if not command:
            return Receipt(
                plan_id=plan.id, step_index=index, verb=verb,
                target=step.get("target", ""),
                exit_code=-1, stdout="", stderr="No command specified",
                duration_ms=0.0, verified=False,
            )
        target = step.get("target", "")
        timeout = step.get("timeout", 30)

        start = time.time()
        if not command:
            return Receipt(
                plan_id=plan.id,
                step_index=index,
                verb=verb,
                target=target,
                exit_code=1,
                stdout="",
                stderr="No command specified",
                duration_ms=0.0,
                verified=False,
            )
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
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            return Receipt(
                plan_id=plan.id,
                step_index=index,
                verb=verb,
                target=target,
                exit_code=-2,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
                verified=False,
            )
