"""
Simple rule-based planner.

P0 fixes:
  F1: Uses allowed verbs only.
  F12: Typed diagnosis; unknown symptoms get noop step.
"""
from __future__ import annotations

from schemas.types import IncidentReport, Plan


class SimplePlanner:
    """Rule-based planner that generates repair plans from incidents."""

    def __init__(self):
        self._custom_rules: dict[str, list[dict]] = {}

    def add_rule(self, symptom: str, steps: list[dict]):
        """Add a custom planning rule for a symptom."""
        self._custom_rules[symptom] = steps

    def plan(self, incident: IncidentReport) -> Plan:
        """Generate a repair plan for the given incident."""
        # Check custom rules first
        if incident.symptom in self._custom_rules:
            return Plan(incident_id=incident.id,
                        steps=self._custom_rules[incident.symptom])

        steps: list[dict] = []

        if incident.symptom == "file_missing":
            steps.append({
                "verb": "touch",
                "command": "touch " + incident.component,
                "target": incident.component,
                "expected": {"exit_code": 0},
            })
            steps.append({
                "verb": "verify",
                "command": "test -f " + incident.component,
                "target": incident.component,
                "expected": {"exit_code": 0},
            })
        elif incident.symptom == "service_down":
            service = incident.component
            steps.append({
                "verb": "restart",
                "command": "systemctl restart " + service,
                "target": service,
                "expected": {"exit_code": 0},
            })
            steps.append({
                "verb": "verify",
                "command": "systemctl is-active " + service,
                "target": service,
                "expected": {"exit_code": 0, "stdout_contains": "active"},
            })
        elif incident.symptom == "collection_error":
            steps.append({
                "verb": "noop",
                "command": "stat " + incident.component,
                "target": incident.component,
                "expected": {"exit_code": 0},
            })
        else:
            # F12: Unknown symptoms get a noop step (not empty plan)
            steps.append({
                "verb": "noop",
                "command": "true",
                "target": incident.component,
                "expected": {"exit_code": 0},
            })

        return Plan(incident_id=incident.id, steps=steps)
