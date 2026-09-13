"""Tests for the simple planner (P0-fixed).

F1: Uses allowed verbs only.
F12: Unknown symptoms get noop step (not empty plan).
"""
from reasoning.planner import SimplePlanner
from schemas.types import IncidentReport, Severity


class TestSimplePlanner:
    def test_plan_for_missing_file(self):
        planner = SimplePlanner()
        inc = IncidentReport(component="/etc/missing", symptom="file_missing")
        plan = planner.plan(inc)
        assert plan.incident_id == inc.id
        assert plan.status == "proposed"
        assert len(plan.steps) == 2
        assert "touch" in plan.steps[0]["command"]
        assert "/etc/missing" in plan.steps[0]["command"]
        assert plan.steps[0]["verb"] == "touch"
        assert plan.steps[1]["verb"] == "verify"

    def test_plan_for_collection_error(self):
        """F12: collection_error gets a noop step with allowed verb."""
        planner = SimplePlanner()
        inc = IncidentReport(component="/proc/x", symptom="collection_error",
                             severity=Severity.ERROR)
        plan = planner.plan(inc)
        assert len(plan.steps) == 1
        assert plan.steps[0]["verb"] == "noop"

    def test_plan_no_matching_rule(self):
        """F12: Unknown symptoms get a noop step (not empty plan)."""
        planner = SimplePlanner()
        inc = IncidentReport(component="x", symptom="unknown_symptom")
        plan = planner.plan(inc)
        assert len(plan.steps) == 1
        assert plan.steps[0]["verb"] == "noop"
        assert plan.status == "proposed"

    def test_add_custom_rule(self):
        planner = SimplePlanner()
        planner.add_rule("custom_symptom", [{"verb": "noop", "command": "true"}])
        inc = IncidentReport(component="x", symptom="custom_symptom")
        plan = planner.plan(inc)
        assert len(plan.steps) == 1
        assert plan.steps[0]["verb"] == "noop"

    def test_service_down_uses_restart_verb(self):
        """F12: service_down plan uses registered restart verb."""
        planner = SimplePlanner()
        inc = IncidentReport(component="ssh", symptom="service_down")
        plan = planner.plan(inc)
        assert plan.steps[0]["verb"] == "restart"
        assert plan.steps[1]["verb"] == "verify"
