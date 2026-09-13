"""Tests for the shell executor (P0-fixed).

F6: Executor does NOT set verified; only returns raw execution results.
"""
from executor.shell_executor import ShellExecutor
from schemas.types import Plan


class TestShellExecutor:
    def test_execute_success(self):
        executor = ShellExecutor()
        plan = Plan(steps=[{"verb": "noop", "command": "true"}])
        receipt = executor.execute_step(plan.steps[0], plan, 0)
        assert receipt.exit_code == 0
        assert receipt.verified is False  # F6: executor does NOT set verified

    def test_execute_failure(self):
        executor = ShellExecutor()
        plan = Plan(steps=[{"verb": "noop", "command": "false"}])
        receipt = executor.execute_step(plan.steps[0], plan, 0)
        assert receipt.exit_code != 0
        assert receipt.verified is False

    def test_execute_with_output(self):
        executor = ShellExecutor()
        plan = Plan(steps=[{"verb": "noop", "command": "echo hello"}])
        receipt = executor.execute_step(plan.steps[0], plan, 0)
        assert receipt.exit_code == 0
        assert "hello" in receipt.stdout

    def test_receipt_has_plan_id(self):
        executor = ShellExecutor()
        plan = Plan(steps=[{"verb": "noop", "command": "true"}])
        receipt = executor.execute_step(plan.steps[0], plan, 0)
        assert receipt.plan_id == plan.id
        assert receipt.step_index == 0
