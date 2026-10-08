"""Tests for the shell executor."""

from executor.shell_executor import ShellExecutor
from schemas.types import Plan


class TestShellExecutor:
    def test_execute_success(self):
        executor = ShellExecutor()
        plan = Plan(steps=[{"command": "true"}])
        receipt = executor.execute_step(plan.steps[0], plan, 0)
        assert receipt.exit_code == 0
        assert receipt.verified is True

    def test_execute_failure(self):
        executor = ShellExecutor()
        plan = Plan(steps=[{"command": "false"}])
        receipt = executor.execute_step(plan.steps[0], plan, 0)
        assert receipt.exit_code != 0
        assert receipt.verified is False

    def test_execute_no_command(self):
        executor = ShellExecutor()
        plan = Plan(steps=[{}])
        receipt = executor.execute_step(plan.steps[0], plan, 0)
        assert receipt.exit_code == 1
        assert receipt.verified is False

    def test_execute_with_output(self):
        executor = ShellExecutor()
        plan = Plan(steps=[{"command": "echo hello"}])
        receipt = executor.execute_step(plan.steps[0], plan, 0)
        assert receipt.exit_code == 0
        assert "hello" in receipt.stdout

    def test_receipt_has_plan_id(self):
        executor = ShellExecutor()
        plan = Plan(steps=[{"command": "true"}])
        receipt = executor.execute_step(plan.steps[0], plan, 0)
        assert receipt.plan_id == plan.id
        assert receipt.step_index == 0
