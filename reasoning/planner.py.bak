"""
Planner: generates repair plans from incidents.

C02 work package — simple planner / MeTTa reasoning stub.
"""
from __future__ import annotations

from typing import Any

from schemas.types import IncidentReport, Plan, Severity


class SimplePlanner:
    """Generates repair plans using rule-based matching."""

    def __init__(self):
        self.rules: list[dict[str, Any]] = self._default_rules()

    def _default_rules(self) -> list[dict[str, Any]]:
        return [
            {
                "symptom": "file_missing",
                "severity_min": "warn",
                "steps": [
                    {
                        "verb": "touch",
                        "command": "touch {component}",
                        "expected": {"exit_code": 0},
                    },
                    {
                        "verb": "verify",
                        "command": "test -f {component}",
                        "expected": {"exit_code": 0},
                    },
                ],
            },
            {
                "symptom": "collection_error",
                "severity_min": "error",
                "steps": [
                    {
                        "verb": "inspect",
                        "command": "stat {component} 2>&1 || true",
                        "expected": {"exit_code": 0},
                    },
                ],
            },
            {
                "symptom": "service_down",
                "severity_min": "error",
                "steps": [
                    {
                        "verb": "restart",
                        "command": "systemctl restart {component} 2>&1 || true",
                        "expected": {"exit_code": 0},
                    },
                    {
                        "verb": "verify",
                        "command": "systemctl is-active {component}",
                        "expected": {"exit_code": 0, "stdout_contains": "active"},
                    },
                ],
            },
        ]

    def plan(self, incident: IncidentReport) -> Plan:
        """Generate a plan for the given incident."""
        for rule in self.rules:
            if rule["symptom"] == incident.symptom:
                steps = []
                for step in rule["steps"]:
                    s = dict(step)
                    # Substitute {component} in command
                    s["command"] = s["command"].replace("{component}", incident.component)
                    steps.append(s)
                return Plan(
                    incident_id=incident.id,
                    steps=steps,
                    status="proposed",
                )
        # No matching rule — empty plan
        return Plan(
            incident_id=incident.id,
            steps=[],
            status="proposed",
        )

    def add_rule(self, symptom: str, steps: list[dict[str, Any]],
                 severity_min: str = "warn") -> None:
        """Add a custom repair rule."""
        self.rules.append({
            "symptom": symptom,
            "severity_min": severity_min,
            "steps": steps,
        })
