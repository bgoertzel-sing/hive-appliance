"""
Tests for P0 fixes from the Astra M0-M1 review.
"""
import pytest
import os
import tempfile
from unittest.mock import patch
import subprocess

from schemas.types import (
    Event, EventKind, Severity, IncidentReport, Plan, Receipt,
    ALLOWED_VERBS,
)
from controller.appliance import Appliance
from controller.reducer import Reducer
from reasoning.planner import SimplePlanner
from executor.base import ShellExecutor
from executor.noop_executor import NoopExecutor
from verifier.exit_code_verifier import ExitCodeVerifier


def make_app(executor=None, recovery_ready=False):
    a = Appliance()
    a.set_planner(SimplePlanner())
    a.set_executor(executor or NoopExecutor())
    a.set_verifier(ExitCodeVerifier())
    a.recovery_ready = recovery_ready
    return a


class TestF1NoBypass:
    def test_run_plan_removed_from_cli(self):
        """F1: The run-plan subcommand should not exist in CLI."""
        import cli
        import inspect
        source = inspect.getsource(cli)
        # Check that no subparser named 'run-plan' exists
        assert "run-plan" not in source.replace("Removed run-plan bypass", "")

    def test_allowed_verbs_enforced(self):
        assert "inspect" in ALLOWED_VERBS
        assert "rm" not in ALLOWED_VERBS

    def test_local_adapter_rejects_unknown_verb(self):
        from adapters.local_adapter import LocalAdapter
        adapter = LocalAdapter()
        with pytest.raises(ValueError, match="not allowed"):
            adapter.run("rm", target="/tmp/x")


class TestF2StrictSchema:
    def test_reject_unknown_fields(self):
        with pytest.raises(ValueError, match="Unknown plan fields"):
            Plan.from_dict({"steps": [], "unknown_effect": True})

    def test_plan_validate_rejects_bad_verb(self):
        plan = Plan(steps=[{"verb": "rm", "command": "echo hi"}])
        errors = plan.validate()
        assert len(errors) > 0

    def test_plan_compute_digest(self):
        plan = Plan(incident_id="inc1",
                    steps=[{"verb": "touch", "command": "touch /tmp/x"}])
        assert len(plan.compute_digest()) == 64


class TestF3RecoveryGate:
    def test_repair_refused_without_recovery_ready(self):
        app = make_app(ShellExecutor(), recovery_ready=False)
        inc = IncidentReport(component="/tmp/test_f3", symptom="file_missing")
        with pytest.raises(RuntimeError, match="recovery_ready"):
            app.repair(inc)
        app.close()

    def test_dry_run_allowed_without_recovery_ready(self):
        app = make_app(ShellExecutor(), recovery_ready=False)
        inc = IncidentReport(component="/tmp/f3dry", symptom="file_missing")
        receipts = app.repair(inc, dry_run=True)
        assert all(r.simulated for r in receipts)
        app.close()


class TestF5DryRunBoundary:
    def test_dry_run_no_subprocess(self):
        app = make_app(ShellExecutor(), recovery_ready=True)
        inc = IncidentReport(component="/tmp/f5", symptom="file_missing")
        with patch("executor.base.subprocess.run",
                   return_value=subprocess.CompletedProcess([], 0, "", "")) as run:
            receipts = app.repair(inc, dry_run=True)
            assert run.call_count == 0
        assert all(r.simulated for r in receipts)
        app.close()

    def test_dry_run_does_not_resolve(self):
        app = make_app(ShellExecutor(), recovery_ready=True)
        inc = IncidentReport(component="/tmp/f5r", symptom="file_missing")
        app.reducer.incidents.append(inc)
        app.repair(inc, dry_run=True)
        assert not inc.resolved
        app.close()

    def test_dry_run_stores_simulated_events(self):
        app = make_app(ShellExecutor(), recovery_ready=True)
        inc = IncidentReport(component="/tmp/f5s", symptom="file_missing")
        app.repair(inc, dry_run=True)
        simulated = app.store.query(kind=EventKind.SIMULATED)
        assert len(simulated) == 2
        app.close()


class TestF6IndependentVerification:
    def test_executor_does_not_set_verified(self):
        executor = ShellExecutor()
        plan = Plan(steps=[{"verb": "noop", "command": "true"}])
        receipt = executor.execute_step(plan.steps[0], plan, 0)
        assert receipt.verified is False

    def test_inactive_not_active(self):
        v = ExitCodeVerifier()
        r = Receipt(exit_code=0, stdout="inactive")
        assert v.verify(r, {"exit_code": 0, "stdout_contains": "active"}) is False


class TestF7PartialComposite:
    def test_partial_failure_does_not_resolve(self):
        app = Appliance()
        app.set_planner(SimplePlanner())
        app.set_verifier(ExitCodeVerifier())
        app.recovery_ready = True

        class Partial:
            def execute_step(self, step, plan, i):
                return Receipt(plan_id=plan.id, step_index=i,
                               exit_code=0 if i == 0 else 1,
                               verb=step.get("verb", ""))

        app.set_executor(Partial())
        inc = IncidentReport(component="/tmp/f7", symptom="file_missing")
        app.reducer.incidents.append(inc)
        receipts = app.repair(inc)
        assert not inc.resolved
        assert len(app.open_incidents()) > 0
        app.close()

    def test_over_budget_rejected(self):
        app = make_app(ShellExecutor(), recovery_ready=True)
        app.max_steps = 1
        inc = IncidentReport(component="/tmp/f7b", symptom="file_missing")
        with pytest.raises(ValueError, match="too large|max_steps"):
            app.repair(inc)
        app.close()

    def test_zero_step_budget_rejected(self):
        app = make_app(ShellExecutor(), recovery_ready=True)
        app.max_steps = 0
        inc = IncidentReport(component="/tmp/f7c", symptom="file_missing")
        with pytest.raises(ValueError, match="max_steps|steps"):
            app.repair(inc)
        app.close()


class TestF8DurableAttempts:
    def test_duplicate_repair_deduplicated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "dedup.txt")
            app = make_app(ShellExecutor(), recovery_ready=True)
            inc = IncidentReport(component=target, symptom="file_missing")
            app.repair(inc)
            assert inc.resolved
            receipts = app.repair(inc)
            assert len(receipts) == 0
            app.close()

    def test_attempt_id_on_receipts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "attempt.txt")
            app = make_app(ShellExecutor(), recovery_ready=True)
            inc = IncidentReport(component=target, symptom="file_missing")
            receipts = app.repair(inc)
            for r in receipts:
                assert r.attempt_id != ""
            app.close()


class TestF9ConflictExclusion:
    def test_target_conflict_rejected(self):
        app = make_app(ShellExecutor(), recovery_ready=True)
        inc = IncidentReport(component="/tmp/f9", symptom="file_missing")
        app._active_targets["/tmp/f9"] = "plan_existing"
        with pytest.raises(RuntimeError, match="conflict"):
            app.repair(inc)
        app.close()


class TestF10Replay:
    def test_replay_on_startup(self):
        from schemas.event_store import EventStore
        s = EventStore()
        s.append(Event(kind=EventKind.OBSERVATION,
                       source="file_collector",
                       subject="/etc/missing",
                       payload={"exists": False, "path": "/etc/missing"}))
        import controller.appliance as appmod
        with patch.object(appmod, "EventStore", return_value=s):
            app = Appliance(":memory:")
        assert len(app.open_incidents()) == 1
        app.close()

    def test_deterministic_incident_ids(self):
        r1 = Reducer()
        r2 = Reducer()
        e = Event(kind=EventKind.OBSERVATION, source="file_collector",
                  subject="/etc/missing",
                  payload={"exists": False, "path": "/etc/missing"})
        r1.reduce(e)
        r2.reduce(e)
        assert r1.incidents[0].id == r2.incidents[0].id

    def test_dedup_on_replay(self):
        r = Reducer()
        e = Event(kind=EventKind.OBSERVATION, source="file_collector",
                  subject="/etc/missing",
                  payload={"exists": False, "path": "/etc/missing"})
        r.reduce(e)
        r.reduce(e)
        assert len(r.incidents) == 1


class TestF12TypedDiagnosis:
    def test_service_not_file_missing(self):
        r = Reducer()
        e = Event(kind=EventKind.OBSERVATION,
                  source="service_collector",
                  subject="ssh",
                  payload={"service": "ssh", "exists": False})
        incidents = r.reduce(e)
        symptoms = [i.symptom for i in incidents]
        assert "file_missing" not in symptoms

    def test_service_restart_uses_registered_verb(self):
        planner = SimplePlanner()
        inc = IncidentReport(component="ssh", symptom="service_down")
        plan = planner.plan(inc)
        assert plan.steps[0]["verb"] == "restart"
