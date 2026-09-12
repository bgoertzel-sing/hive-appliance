"""Tests for M1 controlled repair loop (C04-C07)."""

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
        """Planner should generate restart + verify steps for service_down."""
        from reasoning.planner import SimplePlanner
        from schemas.types import IncidentReport
        planner = SimplePlanner()
        inc = IncidentReport(component="ssh", symptom="service_down")
        plan = planner.plan(inc)
        assert len(plan.steps) == 2
        assert plan.steps[0]["verb"] == "restart"
        assert plan.steps[1]["verb"] == "verify"

    def test_repair_service_dry_run(self):
        """Dry-run service repair should produce 2 verified receipts."""
        app = Appliance(":memory:")
        app.set_planner(SimplePlanner())
        app.set_executor(NoopExecutor())
        app.set_verifier(ExitCodeVerifier())
        inc = IncidentReport(component="ssh", symptom="service_down")
        receipts = app.repair(inc, dry_run=True)
        assert len(receipts) == 2
        assert all(r.verified for r in receipts)
        assert inc.resolved is True
        app.close()

    def test_repair_service_records_plan_event(self):
        """Service repair should persist PLAN event."""
        app = Appliance(":memory:")
        app.set_planner(SimplePlanner())
        app.set_executor(NoopExecutor())
        app.set_verifier(ExitCodeVerifier())
        inc = IncidentReport(component="ssh", symptom="service_down")
        app.repair(inc, dry_run=True)
        plans = app.store.query(kind=EventKind.PLAN)
        assert len(plans) == 1
        app.close()


class TestDryRunMode:
    def test_dry_run_no_side_effects(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "noop.txt")
            app = Appliance(":memory:")
            app.set_planner(SimplePlanner())
            app.set_executor(NoopExecutor())
            app.set_verifier(ExitCodeVerifier())
            inc = IncidentReport(component=target, symptom="file_missing")
            receipts = app.repair(inc, dry_run=True)
            assert len(receipts) == 2
            assert all(r.verified for r in receipts)
            assert not os.path.exists(target)
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
            assert False, "Should have raised"
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
            assert False, "Should have raised"
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
            assert False, "Should have raised"
        except RuntimeError as e:
            assert "verifier" in str(e).lower()
        app.close()

    def test_max_steps_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "limited.txt")
            app = Appliance(":memory:")
            app.set_planner(SimplePlanner())
            app.set_executor(ShellExecutor())
            app.set_verifier(ExitCodeVerifier())
            app.max_steps = 1
            inc = IncidentReport(component=target, symptom="file_missing")
            receipts = app.repair(inc)
            assert len(receipts) == 1
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
            for inc_id, receipts in results.items():
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
            subject="nonexist",
            payload={"service": "nonexist", "active": "inactive", "exists": False},
            severity=Severity.WARN,
        )
        incidents = reducer.reduce(event)
        assert all(i.symptom != "service_down" for i in incidents)


class TestNoopExecutor:
    def test_noop_always_exit_zero(self):
        executor = NoopExecutor()
        plan = Plan(incident_id="inc-1", steps=[{"command": "touch /tmp/x"}])
        receipt = executor.execute_step({"command": "touch /tmp/x"}, plan, 0)
        assert receipt.exit_code == 0
        assert receipt.verified is True

    def test_noop_name(self):
        assert NoopExecutor.name == "noop_executor"


class TestFileVerifier:
    def test_file_exists_verified(self):
        with tempfile.NamedTemporaryFile() as f:
            verifier = FileVerifier()
            receipt = Receipt(
                plan_id="p1", step_index=0, verb="touch",
                target=f.name, exit_code=0, stdout="", stderr="",
            )
            result = verifier.verify(receipt, {"file_exists": f.name})
            assert result is True
            assert receipt.verified is True

    def test_file_not_exists_not_verified(self):
        verifier = FileVerifier()
        receipt = Receipt(
            plan_id="p1", step_index=0, verb="touch",
            target="/nonexistent/path", exit_code=0, stdout="", stderr="",
        )
        result = verifier.verify(receipt, {"file_exists": "/nonexistent/path"})
        assert result is False
        assert receipt.verified is False

    def test_file_verifier_falls_back_to_exit_code(self):
        verifier = FileVerifier()
        receipt = Receipt(
            plan_id="p1", step_index=0, verb="test",
            target="x", exit_code=0, stdout="hello", stderr="",
        )
        result = verifier.verify(receipt, {"exit_code": 0, "stdout_contains": "hello"})
        assert result is True
        assert receipt.verified is True
