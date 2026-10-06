"""
Tests for P0 fixes from Astra review.

F1:  Allowed verbs only
F2:  Strict plan schema validation
F3:  Recovery-ready gate (checkpoint before repair)
F5:  Dry-run boundary
F6:  Independent verification (simulated != verified)
F7:  Composite receipt (all steps must verify)
F8:  Dedup (attempt_id / active repairs)
F10: Deterministic incident IDs
F12: Typed diagnosis (service_down != file_missing)
F13: Resource limits (max steps, timeout caps)
"""
import pytest

from controller.appliance import Appliance
from controller.reducer import Reducer
from executor.base import HARD_TIMEOUT_CAP
from executor.noop_executor import NoopExecutor
from executor.shell_executor import ShellExecutor
from reasoning.planner import MAX_PLAN_STEPS, MAX_STEP_TIMEOUT, SimplePlanner
from schemas.types import (
    ALLOWED_VERBS,
    Event,
    EventKind,
    IncidentReport,
    Plan,
    Receipt,
    _deterministic_id,
)
from verifier.exit_code_verifier import ExitCodeVerifier

# ── F1: Allowed verbs only ──────────────────────────────

class TestF1AllowedVerbs:
    def test_allowed_verbs_frozenset(self):
        assert isinstance(ALLOWED_VERBS, frozenset)
        assert "touch" in ALLOWED_VERBS
        assert "verify" in ALLOWED_VERBS
        assert "rm" not in ALLOWED_VERBS
        assert "curl" not in ALLOWED_VERBS

    def test_plan_validate_rejects_bad_verb(self):
        plan = Plan(steps=[{"verb": "rm", "command": "rm -rf /"}])
        errors = plan.validate()
        assert len(errors) > 0
        assert "rm" in errors[0]

    def test_plan_validate_accepts_good_verbs(self):
        plan = Plan(steps=[
            {"verb": "touch", "command": "touch /tmp/x"},
            {"verb": "verify", "command": "test -f /tmp/x"},
        ])
        errors = plan.validate()
        assert errors == []

    def test_planner_rejects_bad_rule(self):
        planner = SimplePlanner()
        with pytest.raises(ValueError, match="not in ALLOWED_VERBS"):
            planner.add_rule("test", [{"verb": "curl", "command": "curl evil.com"}])

    def test_noop_executor_rejects_bad_verb(self):
        executor = NoopExecutor()
        plan = Plan(id="p1")
        step = {"verb": "rm", "command": "rm -rf /"}
        receipt = executor.execute_step(step, plan, 0)
        assert receipt.exit_code == -3
        assert "Validation errors" in receipt.stderr

    def test_shell_executor_rejects_bad_verb(self):
        executor = ShellExecutor()
        plan = Plan(id="p1")
        step = {"verb": "rm", "command": "rm -rf /"}
        receipt = executor.execute_step(step, plan, 0)
        assert receipt.exit_code == -3
        assert "Validation errors" in receipt.stderr


# ── F2: Strict plan schema ──────────────────────────────

class TestF2StrictPlanSchema:
    def test_unknown_field_rejected(self):
        with pytest.raises(ValueError, match="Unknown plan fields"):
            Plan.from_dict({"id": "p1", "evil_field": "hack"})

    def test_known_fields_accepted(self):
        plan = Plan.from_dict({
            "id": "p1",
            "steps": [{"verb": "touch", "command": "touch /tmp/x"}],
            "status": "proposed",
        })
        assert plan.id == "p1"

    def test_compute_digest(self):
        plan = Plan(incident_id="inc_1", steps=[{"verb": "touch"}])
        d1 = plan.compute_digest()
        assert isinstance(d1, str) and len(d1) == 64
        # Same content = same digest
        plan2 = Plan(incident_id="inc_1", steps=[{"verb": "touch"}])
        assert plan2.compute_digest() == d1


# ── F5: Dry-run boundary ────────────────────────────────

class TestF5DryRunBoundary:
    def test_noop_executor_marks_simulated(self):
        executor = NoopExecutor()
        plan = Plan(id="p1", attempt_id="att_1")
        step = {"verb": "touch", "command": "touch /tmp/x"}
        receipt = executor.execute_step(step, plan, 0)
        assert receipt.simulated is True
        assert receipt.verified is False

    def test_noop_is_simulation(self):
        assert NoopExecutor.is_simulation is True
        assert ShellExecutor.is_simulation is False


# ── F6: Independent verification ────────────────────────

class TestF6IndependentVerification:
    def test_simulated_receipt_never_verified(self):
        verifier = ExitCodeVerifier()
        receipt = Receipt(exit_code=0, simulated=True)
        result = verifier.verify(receipt, {"exit_code": 0})
        assert result is False
        assert receipt.verified is False

    def test_real_receipt_can_be_verified(self):
        verifier = ExitCodeVerifier()
        receipt = Receipt(exit_code=0, simulated=False)
        result = verifier.verify(receipt, {"exit_code": 0})
        assert result is True
        assert receipt.verified is True

    def test_real_receipt_fails_verification(self):
        verifier = ExitCodeVerifier()
        receipt = Receipt(exit_code=1, simulated=False)
        result = verifier.verify(receipt, {"exit_code": 0})
        assert result is False
        assert receipt.verified is False

    def test_stdout_contains_check(self):
        verifier = ExitCodeVerifier()
        receipt = Receipt(exit_code=0, stdout="active", simulated=False)
        assert verifier.verify(receipt, {"exit_code": 0, "stdout_contains": "active"})
        receipt2 = Receipt(exit_code=0, stdout="inactive", simulated=False)
        assert not verifier.verify(receipt2, {"exit_code": 0, "stdout_contains": "active"})


# ── F7: Composite receipt ───────────────────────────────

class TestF7CompositeReceipt:
    def test_single_receipt_does_not_resolve(self):
        reducer = Reducer()
        # Register a plan with 2 steps
        plan_event = Event(
            kind=EventKind.PLAN,
            source="planner",
            subject="inc_1",
            payload={"id": "plan_1", "steps": [{"verb": "touch"}, {"verb": "verify"}]},
        )
        reducer.reduce(plan_event)

        # Create and link incident
        inc = IncidentReport(id="inc_1", component="test", symptom="missing")
        inc.plan_id = "plan_1"
        reducer.incidents.append(inc)
        reducer._seen_incident_ids.add(inc.id)

        # Only one receipt verified
        receipt_event = Event(
            kind=EventKind.RECEIPT,
            source="verifier",
            payload={"plan_id": "plan_1", "verified": True, "step_index": 0},
        )
        reducer.reduce(receipt_event)
        assert not inc.resolved  # Not resolved yet!

    def test_all_receipts_resolve(self):
        reducer = Reducer()
        plan_event = Event(
            kind=EventKind.PLAN,
            source="planner",
            subject="inc_1",
            payload={"id": "plan_2", "steps": [{"verb": "touch"}, {"verb": "verify"}]},
        )
        reducer.reduce(plan_event)

        inc = IncidentReport(id="inc_1", component="test", symptom="missing")
        inc.plan_id = "plan_2"
        reducer.incidents.append(inc)
        reducer._seen_incident_ids.add(inc.id)

        for i in range(2):
            receipt_event = Event(
                kind=EventKind.RECEIPT,
                source="verifier",
                payload={"plan_id": "plan_2", "verified": True, "step_index": i},
            )
            reducer.reduce(receipt_event)
        assert inc.resolved  # Now resolved

    def test_partial_failure_does_not_resolve(self):
        reducer = Reducer()
        plan_event = Event(
            kind=EventKind.PLAN,
            source="planner",
            subject="inc_1",
            payload={"id": "plan_3", "steps": [{"verb": "touch"}, {"verb": "verify"}]},
        )
        reducer.reduce(plan_event)

        inc = IncidentReport(id="inc_1", component="test", symptom="missing")
        inc.plan_id = "plan_3"
        reducer.incidents.append(inc)
        reducer._seen_incident_ids.add(inc.id)

        # First verified, second not
        reducer.reduce(Event(kind=EventKind.RECEIPT, source="v",
                             payload={"plan_id": "plan_3", "verified": True}))
        reducer.reduce(Event(kind=EventKind.RECEIPT, source="v",
                             payload={"plan_id": "plan_3", "verified": False}))
        assert not inc.resolved


# ── F8: Dedup ───────────────────────────────────────────

class TestF8Dedup:
    def test_attempt_id_generated(self):
        planner = SimplePlanner()
        inc = IncidentReport(component="/tmp/x", symptom="file_missing")
        plan = planner.plan(inc)
        assert plan.attempt_id.startswith("att_")

    def test_receipt_carries_attempt_id(self):
        executor = NoopExecutor()
        plan = Plan(id="p1", attempt_id="att_test123")
        receipt = executor.execute_step({"verb": "noop"}, plan, 0)
        assert receipt.attempt_id == "att_test123"


# ── F10: Deterministic IDs ──────────────────────────────

class TestF10DeterministicIDs:
    def test_deterministic_id_stable(self):
        id1 = _deterministic_id("inc_", "nginx", "service_down")
        id2 = _deterministic_id("inc_", "nginx", "service_down")
        assert id1 == id2

    def test_deterministic_id_differs(self):
        id1 = _deterministic_id("inc_", "nginx", "service_down")
        id2 = _deterministic_id("inc_", "apache", "service_down")
        assert id1 != id2

    def test_incident_deterministic_factory(self):
        inc1 = IncidentReport.deterministic("nginx", "service_down")
        inc2 = IncidentReport.deterministic("nginx", "service_down")
        assert inc1.id == inc2.id

    def test_reducer_dedup_deterministic(self):
        reducer = Reducer()
        event1 = Event(
            kind=EventKind.OBSERVATION,
            source="service_collector",
            subject="nginx",
            payload={"active": "inactive", "exists": True, "service": "nginx"},
        )
        event2 = Event(
            kind=EventKind.OBSERVATION,
            source="service_collector",
            subject="nginx",
            payload={"active": "inactive", "exists": True, "service": "nginx"},
        )
        _inc1 = _ = reducer.reduce(event1)
        _inc2 = _ = reducer.reduce(event2)
        # Second reduce should not create a new incident (dedup)
        assert len(reducer.incidents) == 1


# ── F12: Typed diagnosis ────────────────────────────────

class TestF12TypedDiagnosis:
    def test_service_down_not_file_missing(self):
        reducer = Reducer()
        event = Event(
            kind=EventKind.OBSERVATION,
            source="service_collector",
            subject="nginx",
            payload={"active": "inactive", "exists": True, "service": "nginx"},
        )
        incidents = reducer.reduce(event)
        symptoms = [inc.symptom for inc in incidents]
        assert "service_down" in symptoms
        assert "file_missing" not in symptoms

    def test_file_missing_from_file_collector(self):
        reducer = Reducer()
        event = Event(
            kind=EventKind.OBSERVATION,
            source="file_collector",
            subject="/etc/missing.conf",
            payload={"exists": False, "resource_kind": "file"},
        )
        incidents = reducer.reduce(event)
        symptoms = [inc.symptom for inc in incidents]
        assert "file_missing" in symptoms


# ── F13: Resource limits ────────────────────────────────

class TestF13ResourceLimits:
    def test_max_plan_steps(self):
        assert MAX_PLAN_STEPS == 10

    def test_max_step_timeout(self):
        assert MAX_STEP_TIMEOUT == 120

    def test_hard_timeout_cap(self):
        assert HARD_TIMEOUT_CAP == 120

    def test_planner_caps_steps(self):
        """Planner should respect MAX_PLAN_STEPS."""
        planner = SimplePlanner()
        inc = IncidentReport(component="/tmp/x", symptom="file_missing")
        plan = planner.plan(inc)
        assert len(plan.steps) <= MAX_PLAN_STEPS


# ── F1 via LocalAdapter ────────────────────────────────

class TestF1LocalAdapter:
    def test_adapter_rejects_bad_verb(self):
        from adapters.local_adapter import LocalAdapter
        adapter = LocalAdapter()
        with pytest.raises(ValueError, match="not allowed"):
            adapter.run("rm", "/tmp/x")

    def test_adapter_accepts_noop(self):
        from adapters.local_adapter import LocalAdapter
        adapter = LocalAdapter()
        result = adapter.run("noop")
        assert result["exit_code"] == 0


# ── Integration: full repair cycle ──────────────────────

class TestIntegrationRepairCycle:
    def test_dry_run_repair_no_real_side_effects(self):
        app = Appliance(":memory:")
        from executor.noop_executor import NoopExecutor
        from reasoning.planner import SimplePlanner
        from verifier.exit_code_verifier import ExitCodeVerifier

        app.set_planner(SimplePlanner())
        app.set_executor(NoopExecutor())
        app.set_verifier(ExitCodeVerifier())

        inc = IncidentReport(component="/tmp/test_dry", symptom="file_missing")
        app.record_incident(inc)

        receipts = app.repair(inc, dry_run=True)
        assert len(receipts) > 0
        for r in receipts:
            assert r.simulated is True
            assert r.verified is False  # F6: simulated never verified
        app.close()

    def test_dedup_prevents_double_repair(self):
        app = Appliance(":memory:")
        from executor.noop_executor import NoopExecutor
        from reasoning.planner import SimplePlanner
        from verifier.exit_code_verifier import ExitCodeVerifier

        app.set_planner(SimplePlanner())
        app.set_executor(NoopExecutor())
        app.set_verifier(ExitCodeVerifier())

        inc = IncidentReport(id="inc_dedup_test", component="/tmp/x", symptom="file_missing")
        app.record_incident(inc)

        # Simulate active repair
        app._active_repairs.add("inc_dedup_test")
        receipts = app.repair(inc, dry_run=True)
        assert receipts == []  # F8: deduped
        app._active_repairs.discard("inc_dedup_test")
        app.close()
