"""Tests for M1 controlled repair loop (C04-C07).

Updated for P0 safety fixes from Astra review:
- F5: dry_run does not resolve incidents, produces unverified preview receipts
- F6: NoopExecutor/simulation receipts are NOT verified
- F7: over-budget plans rejected before any dispatch (0 receipts)
- F8: duplicate repair requests rejected
- F10: events replayed from store on construction
"""

import os
import tempfile

from controller.appliance import Appliance
from executor.noop_executor import NoopExecutor
from executor.shell_executor import ShellExecutor
from reasoning.planner import SimplePlanner
from schemas.types import Event, EventKind, IncidentReport, Plan, Receipt, Severity
from verifier.exit_code_verifier import ExitCodeVerifier
from verifier.file_verifier import FileVerifier


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
            inc = IncidentReport(component=target, symptom="file_missing")
            app.repair(inc)
            plans = app.store.query(kind=EventKind.PLAN)
            assert len(plans) == 1
            assert plans[0].payload["incident_id"] == inc.id
            app.close()

    def test_repair_records_receipt_events(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "test_rcpt.txt")
            app = Appliance(":memory:")
            app.set_planner(SimplePlanner())
            app.set_executor(ShellExecutor())
            app.set_verifier(ExitCodeVerifier())
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
        """Dry-run service repair should produce 2 unverified preview receipts.

        P0-F5: dry_run must NOT resolve the incident.
        P0-F6: simulation receipts are NOT verified.
        """
        app = Appliance(":memory:")
        app.set_planner(SimplePlanner())
        app.set_executor(NoopExecutor())
        app.set_verifier(ExitCodeVerifier())
        inc = IncidentReport(component="ssh", symptom="service_down")
        receipts = app.repair(inc, dry_run=True)
        assert len(receipts) == 2
        assert all(not r.verified for r in receipts)
        assert inc.resolved is not True
        app.close()

    def test_repair_service_records_plan_event(self):
        app = Appliance(":memory:")
        app.set_planner(SimplePlanner())
        app.set_executor(NoopExecutor())
        app.set_verifier(ExitCodeVerifier())
        inc = IncidentReport(component="ssh", symptom="service_down")
        app.repair(inc)
        plans = app.store.query(kind=EventKind.PLAN)
        assert len(plans) == 1
        app.close()


class TestDryRunMode:
    def test_dry_run_no_side_effects(self):
        """Dry-run must not create files or resolve incidents.

        P0-F5: dry_run enforced at dispatch boundary, no real effects.
        P0-F6: preview receipts are NOT verified.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "noop.txt")
            app = Appliance(":memory:")
            app.set_planner(SimplePlanner())
            app.set_executor(NoopExecutor())
            app.set_verifier(ExitCodeVerifier())
            inc = IncidentReport(component=target, symptom="file_missing")
            receipts = app.repair(inc, dry_run=True)
            assert len(receipts) == 2
            assert all(not r.verified for r in receipts)
            assert not os.path.exists(target)
            assert inc.resolved is not True
            app.close()

    def test_dry_run_receipts_show_noop(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "noop2.txt")
            app = Appliance(":memory:")
            app.set_planner(SimplePlanner())
            app.set_executor(NoopExecutor())
            app.set_verifier(ExitCodeVerifier())
            inc = IncidentReport(component=target, symptom="file_missing")
            receipts = app.repair(inc, dry_run=True)
            assert "[dry-run]" in receipts[0].stdout
            app.close()


class TestRepairSafety:
    def test_repair_requires_planner(self):
        app = Appliance(":memory:")
        app.set_executor(ShellExecutor())
        app.set_verifier(ExitCodeVerifier())
        inc = IncidentReport(component="/tmp/x", symptom="file_missing")
        try:
            app.repair(inc)
            raise AssertionError("Should have raised")
        except RuntimeError as e:
            assert "planner" in str(e).lower()
        app.close()

    def test_repair_requires_executor(self):
        app = Appliance(":memory:")
        app.set_planner(SimplePlanner())
        app.set_verifier(ExitCodeVerifier())
        inc = IncidentReport(component="/tmp/x", symptom="file_missing")
        try:
            app.repair(inc)
            raise AssertionError("Should have raised")
        except RuntimeError as e:
            assert "executor" in str(e).lower()
        app.close()

    def test_repair_requires_verifier(self):
        app = Appliance(":memory:")
        app.set_planner(SimplePlanner())
        app.set_executor(ShellExecutor())
        inc = IncidentReport(component="/tmp/x", symptom="file_missing")
        try:
            app.repair(inc)
            raise AssertionError("Should have raised")
        except RuntimeError as e:
            assert "verifier" in str(e).lower()
        app.close()

    def test_max_steps_limit(self):
        """Over-budget plans are rejected before any dispatch.

        P0-F7: plans exceeding max_steps produce 0 receipts.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "limited.txt")
            app = Appliance(":memory:")
            app.set_planner(SimplePlanner())
            app.set_executor(ShellExecutor())
            app.set_verifier(ExitCodeVerifier())
            app.max_steps = 1
            inc = IncidentReport(component=target, symptom="file_missing")
            receipts = app.repair(inc)
            assert len(receipts) == 0
            assert inc.resolved is not True
            app.close()


class TestRepairAll:
    def test_repair_all_multiple_incidents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = Appliance(":memory:")
            app.set_planner(SimplePlanner())
            app.set_executor(ShellExecutor())
            app.set_verifier(ExitCodeVerifier())
            for i in range(3):
                target = os.path.join(tmpdir, "file%d.txt" % i)
                inc = IncidentReport(component=target, symptom="file_missing")
                app.reducer.incidents.append(inc)
            results = app.repair_all()
            assert len(results) == 3
            for _inc_id, receipts in results.items():
                assert len(receipts) == 2
                assert all(r.verified for r in receipts)
            assert len(app.open_incidents()) == 0
            app.close()


class TestReducerServiceDown:
    def test_service_down_detected(self):
        from controller.reducer import Reducer
        reducer = Reducer()
        event = Event(
            kind=EventKind.OBSERVATION,
            source="service_collector",
            subject="ssh",
            payload={"service": "ssh", "active": "inactive", "exists": True},
            severity=Severity.WARN,
        )
        incidents = reducer.reduce(event)
        assert len(incidents) == 1
        assert incidents[0].symptom == "service_down"
        assert incidents[0].severity == Severity.ERROR

    def test_service_running_no_incident(self):
        from controller.reducer import Reducer
        reducer = Reducer()
        event = Event(
            kind=EventKind.OBSERVATION,
            source="service_collector",
            subject="ssh",
            payload={"service": "ssh", "active": "active", "exists": True},
            severity=Severity.INFO,
        )
        incidents = reducer.reduce(event)
        assert len(incidents) == 0

    def test_service_not_found_no_service_down(self):
        from controller.reducer import Reducer
        reducer = Reducer()
        event = Event(
            kind=EventKind.OBSERVATION,
            source="service_collector",
            subject="ssh",
            payload={"service": "ssh", "active": "inactive", "exists": False},
            severity=Severity.WARN,
        )
        incidents = reducer.reduce(event)
        assert len(incidents) == 0


class TestNoopExecutor:
    def test_noop_name(self):
        executor = NoopExecutor()
        assert executor.name == "noop_executor"

    def test_noop_always_exit_zero(self):
        executor = NoopExecutor()
        plan = Plan(steps=[{"verb": "touch", "command": "touch /tmp/x"}])
        receipt = executor.execute_step(plan.steps[0], plan, 0)
        assert receipt.exit_code == 0
        assert "touch" in receipt.stdout


class TestFileVerifier:
    def test_file_exists_verified(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "exists.txt")
            with open(target, "w") as f:
                f.write("hello")
            verifier = FileVerifier()
            receipt = Receipt(target=target, exit_code=0)
            assert verifier.verify(receipt, {"file_exists": target})

    def test_file_not_exists_not_verified(self):
        verifier = FileVerifier()
        receipt = Receipt(target="/nonexistent/path", exit_code=0)
        assert not verifier.verify(receipt, {"file_exists": "/nonexistent/path"})

    def test_file_verifier_falls_back_to_exit_code(self):
        verifier = FileVerifier()
        receipt = Receipt(exit_code=1)
        assert not verifier.verify(receipt, {"exit_code": 0})


class TestP0SafetyFixes:
    """Tests specifically for P0 Astra review fixes."""

    def test_dry_run_does_not_resolve(self):
        """F5: dry_run must not set incident.resolved = True."""
        app = Appliance(":memory:")
        app.set_planner(SimplePlanner())
        app.set_executor(ShellExecutor())
        app.set_verifier(ExitCodeVerifier())
        inc = IncidentReport(component="/tmp/dry_test", symptom="file_missing")
        app.repair(inc, dry_run=True)
        assert inc.resolved is not True
        app.close()

    def test_simulation_not_verified(self):
        """F6: NoopExecutor receipts must not be verified even without dry_run."""
        app = Appliance(":memory:")
        app.set_planner(SimplePlanner())
        app.set_executor(NoopExecutor())
        app.set_verifier(ExitCodeVerifier())
        inc = IncidentReport(component="/tmp/sim_test", symptom="file_missing")
        receipts = app.repair(inc)
        assert all(not r.verified for r in receipts)
        assert inc.resolved is not True
        app.close()

    def test_over_budget_rejected_before_dispatch(self):
        """F7: over-budget plan produces 0 receipts and no resolution."""
        app = Appliance(":memory:")
        app.set_planner(SimplePlanner())
        app.set_executor(ShellExecutor())
        app.set_verifier(ExitCodeVerifier())
        app.max_steps = 1
        inc = IncidentReport(component="/tmp/overbudget", symptom="file_missing")
        receipts = app.repair(inc)
        assert len(receipts) == 0
        assert inc.resolved is not True
        # Check plan was recorded with rejected status
        plans = app.store.query(kind=EventKind.PLAN)
        assert len(plans) >= 1
        assert plans[0].payload["status"] == "rejected_over_budget"
        app.close()

    def test_duplicate_repair_rejected(self):
        """F8: calling repair twice for same incident returns empty second time."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "dup.txt")
            app = Appliance(":memory:")
            app.set_planner(SimplePlanner())
            app.set_executor(ShellExecutor())
            app.set_verifier(ExitCodeVerifier())
            inc = IncidentReport(component=target, symptom="file_missing")
            first = app.repair(inc)
            assert len(first) == 2
            second = app.repair(inc)
            assert len(second) == 0
            app.close()

    def test_event_replay_on_construction(self):
        """F10: new Appliance replays existing events from store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            app1 = Appliance(db_path)
            app1.record_incident(IncidentReport(component="/tmp/x", symptom="file_missing"))
            app1.close()
            # New appliance should replay events
            app2 = Appliance(db_path)
            assert len(app2.reducer.incidents) >= 1
            app2.close()
