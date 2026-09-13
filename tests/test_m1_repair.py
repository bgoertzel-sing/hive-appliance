"""Tests for M1 controlled repair loop (C04-C07) - P0 fixed.

F3: Non-dry-run requires recovery_ready=True
F5: Dry-run produces simulated receipts (verified=False), does NOT resolve
F6: Executor does not set verified; verifier does
F7: Partial failure does NOT resolve incident
F8: Deduplication prevents repeated repair for same incident
"""
import tempfile
import os

from controller.appliance import Appliance
from reasoning.planner import SimplePlanner
from executor.shell_executor import ShellExecutor
from executor.noop_executor import NoopExecutor
from verifier.exit_code_verifier import ExitCodeVerifier
from verifier.file_verifier import FileVerifier
from schemas.types import Event, EventKind, Severity, IncidentReport, Plan, Receipt


class TestApplianceRepairSetup:
    def test_set_planner(self):
        app = Appliance(":memory:")
        app.set_planner(SimplePlanner())
        assert app.planner is not None
        app.close()

    def test_set_executor(self):
        app = Appliance(":memory:")
        app.set_executor(ShellExecutor())
        assert app.executor is not None
        app.close()

    def test_set_verifier(self):
        app = Appliance(":memory:")
        app.set_verifier(ExitCodeVerifier())
        assert app.verifier is not None
        app.close()

    def test_max_steps_default(self):
        app = Appliance(":memory:")
        assert app.max_steps == 20
        app.close()


class TestRepairFileMissing:
    def test_repair_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "repaired.txt")
            app = Appliance(":memory:")
            app.set_planner(SimplePlanner())
            app.set_executor(ShellExecutor())
            app.set_verifier(ExitCodeVerifier())
            app.recovery_ready = True
            inc = IncidentReport(component=target, symptom="file_missing")
            receipts = app.repair(inc)
            assert len(receipts) == 2
            assert all(r.verified for r in receipts)
            assert os.path.exists(target)
            assert inc.resolved is True
            app.close()

    def test_repair_records_plan_event(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "test_plan.txt")
            app = Appliance(":memory:")
            app.set_planner(SimplePlanner())
            app.set_executor(ShellExecutor())
            app.set_verifier(ExitCodeVerifier())
            app.recovery_ready = True
            inc = IncidentReport(component=target, symptom="file_missing")
            app.repair(inc)
            plans = app.store.query(kind=EventKind.PLAN)
            assert len(plans) >= 1
            assert plans[0].payload["incident_id"] == inc.id
            app.close()

    def test_repair_records_receipt_events(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "test_rcpt.txt")
            app = Appliance(":memory:")
            app.set_planner(SimplePlanner())
            app.set_executor(ShellExecutor())
            app.set_verifier(ExitCodeVerifier())
            app.recovery_ready = True
            inc = IncidentReport(component=target, symptom="file_missing")
            receipts = app.repair(inc)
            evts = app.store.query(kind=EventKind.RECEIPT)
            assert len(evts) == len(receipts)
            app.close()

    def test_repair_resolves_incident(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "resolved.txt")
            app = Appliance(":memory:")
            app.set_planner(SimplePlanner())
            app.set_executor(ShellExecutor())
            app.set_verifier(ExitCodeVerifier())
            app.recovery_ready = True
            inc = IncidentReport(component=target, symptom="file_missing")
            app.repair(inc)
            assert inc.resolved is True
            assert len(app.open_incidents()) == 0
            app.close()


class TestRepairServiceDown:
    def test_repair_service_plan_has_restart_and_verify(self):
        planner = SimplePlanner()
        inc = IncidentReport(component="ssh", symptom="service_down")
        plan = planner.plan(inc)
        assert len(plan.steps) == 2
        assert plan.steps[0]["verb"] == "restart"
        assert plan.steps[1]["verb"] == "verify"

    def test_repair_service_dry_run(self):
        """F5: Dry-run produces simulated, non-verified receipts; does NOT resolve."""
        app = Appliance(":memory:")
        app.set_planner(SimplePlanner())
        app.set_executor(NoopExecutor())
        app.set_verifier(ExitCodeVerifier())
        inc = IncidentReport(component="ssh", symptom="service_down")
        receipts = app.repair(inc, dry_run=True)
        assert len(receipts) == 2
        assert all(r.simulated for r in receipts)  # F5: simulated
        assert not any(r.verified for r in receipts)  # F5: NOT verified
        assert not inc.resolved  # F5: NOT resolved
        app.close()

    def test_repair_service_records_plan_event(self):
        """F5: Dry-run still records a plan event."""
        app = Appliance(":memory:")
        app.set_planner(SimplePlanner())
        app.set_executor(NoopExecutor())
        app.set_verifier(ExitCodeVerifier())
        inc = IncidentReport(component="ssh", symptom="service_down")
        app.repair(inc, dry_run=True)
        plans = app.store.query(kind=EventKind.PLAN)
        assert len(plans) >= 1
        app.close()


class TestDryRunMode:
    def test_dry_run_no_side_effects(self):
        """F5: Dry-run with ShellExecutor produces zero subprocess calls."""
        import subprocess
        from unittest.mock import patch
        app = Appliance(":memory:")
        app.set_planner(SimplePlanner())
        app.set_executor(ShellExecutor())
        app.set_verifier(ExitCodeVerifier())
        inc = IncidentReport(component="/tmp/test_dry", symptom="file_missing")
        with patch('executor.base.subprocess.run',
                   return_value=subprocess.CompletedProcess([], 0, '', '')) as run:
            receipts = app.repair(inc, dry_run=True)
            assert run.call_count == 0  # F5: no subprocess calls
        assert all(r.simulated for r in receipts)
        app.close()

    def test_dry_run_receipts_show_noop(self):
        """F5: Dry-run receipts show [simulated] in stdout."""
        app = Appliance(":memory:")
        app.set_planner(SimplePlanner())
        app.set_executor(NoopExecutor())
        app.set_verifier(ExitCodeVerifier())
        inc = IncidentReport(component="/tmp/test_noop", symptom="file_missing")
        receipts = app.repair(inc, dry_run=True)
        for r in receipts:
            assert r.simulated is True
            assert r.verified is False
        app.close()


class TestRepairSafety:
    def test_max_steps_limit(self):
        """F7: Over-budget plans are rejected before dispatch."""
        app = Appliance(":memory:")
        app.set_planner(SimplePlanner())
        app.set_executor(ShellExecutor())
        app.set_verifier(ExitCodeVerifier())
        app.recovery_ready = True
        app.max_steps = 1
        inc = IncidentReport(component="/tmp/test_limit", symptom="file_missing")
        # SimplePlanner generates 2 steps for file_missing, max_steps=1
        import pytest
        with pytest.raises(ValueError, match="max_steps|over-budget|steps"):
            app.repair(inc)
        app.close()

    def test_zero_step_budget_rejected(self):
        """F7: max_steps=0 with nonzero plan is rejected."""
        app = Appliance(":memory:")
        app.set_planner(SimplePlanner())
        app.set_executor(ShellExecutor())
        app.set_verifier(ExitCodeVerifier())
        app.recovery_ready = True
        app.max_steps = 0
        inc = IncidentReport(component="/tmp/test_zero", symptom="file_missing")
        import pytest
        with pytest.raises(ValueError, match="max_steps|steps"):
            app.repair(inc)
        app.close()

    def test_recovery_gate_blocks_repair(self):
        """F3: repair() refuses without recovery_ready."""
        app = Appliance(":memory:")
        app.set_planner(SimplePlanner())
        app.set_executor(ShellExecutor())
        app.set_verifier(ExitCodeVerifier())
        inc = IncidentReport(component="/tmp/test_gate", symptom="file_missing")
        import pytest
        with pytest.raises(RuntimeError, match="recovery_ready"):
            app.repair(inc)
        app.close()


class TestRepairAll:
    def test_repair_all_multiple_incidents(self):
        """F3: Repair multiple incidents with recovery_ready=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            app = Appliance(":memory:")
            app.set_planner(SimplePlanner())
            app.set_executor(ShellExecutor())
            app.set_verifier(ExitCodeVerifier())
            app.recovery_ready = True
            for i in range(3):
                target = os.path.join(tmpdir, f"file_{i}.txt")
                inc = IncidentReport(component=target, symptom="file_missing")
                app.repair(inc)
                assert inc.resolved
                assert os.path.exists(target)
            app.close()

    def test_duplicate_repair_deduplicated(self):
        """F8: Repeated repair for same incident is deduplicated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "dedup.txt")
            app = Appliance(":memory:")
            app.set_planner(SimplePlanner())
            app.set_executor(ShellExecutor())
            app.set_verifier(ExitCodeVerifier())
            app.recovery_ready = True
            inc = IncidentReport(component=target, symptom="file_missing")
            app.repair(inc)
            assert inc.resolved
            # Second repair should return empty (deduplicated)
            receipts = app.repair(inc)
            assert len(receipts) == 0
            app.close()


class TestNoopExecutor:
    def test_noop_always_exit_zero(self):
        executor = NoopExecutor()
        plan = Plan(steps=[{"verb": "noop", "command": "true"}])
        receipt = executor.execute_step(plan.steps[0], plan, 0)
        assert receipt.exit_code == 0
        assert receipt.verified is False  # F6: NOT verified by executor

    def test_noop_simulated(self):
        executor = NoopExecutor()
        plan = Plan(steps=[{"verb": "noop", "command": "true"}])
        receipt = executor.execute_step(plan.steps[0], plan, 0)
        assert receipt.simulated is True  # F5: simulated


class TestFileVerifier:
    def test_file_exists_verified(self):
        """F6: FileVerifier independently checks filesystem."""
        with tempfile.NamedTemporaryFile() as f:
            v = FileVerifier()
            r = Receipt(exit_code=0)
            assert v.verify(r, {"file_exists": f.name}) is True

    def test_file_not_exists_not_verified(self):
        v = FileVerifier()
        r = Receipt(exit_code=0)
        assert v.verify(r, {"file_exists": "/nonexistent/path/xyz"}) is False

    def test_file_verifier_no_expectation(self):
        """F6: FileVerifier returns True when no file_exists expectation."""
        v =        v = FileVerifier()
        r = Receipt(exit_code=0)
        assert v.verify(r, {}) is True
