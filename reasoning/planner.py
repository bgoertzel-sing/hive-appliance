"""
Simple rule-based planner.

P0 fixes:
  F1: Uses allowed verbs only.
  F12: Typed diagnosis - doesn't propose file creation for service issues.
"""
from __future__ import annotations

from schemas.types import IncidentReport, Plan


class SimplePlanner:
    """Rule-based planner that generates repair plans from incidents."""

    def plan(self, incident: IncidentReport) -> Plan:
        """Generate a repair plan for the given incident."""
        steps: list[dict] = []

        if incident.symptom == "file_missing":
            steps.append({
                "verb": "touch",
                "command": f"touch {incident.component}",
                "target": incident.component,
                "expected": {"exit_code": 0},
            })
            steps.append({
                "verb": "verify",
                "command": f"test -f {incident.component}",
                "target": incident.component,
                "expected": {"exit_code": 0},
            })
        elif incident.symptom == "service_down":
            # F12: Use registered verb, not raw shell with redirect operators
            service = incident.component
            steps.append({
                "verb": "restart",
                "command": f"systemctl restart {service}",
                "target": service,
                "expected": {"exit_code": 0},
            })
            steps.append({
                "verb": "verify",
                "command": f"systemctl is-active {service}",
                "target": service,
                "expected": {"exit_code": 0, "stdout_contains": "active"},
            })
        else:
            steps.append({
                "verb": "noop",
                "command": "true",
                "target": incident.component,
                "expected": {"exit_code": 0},
            })

        return Plan(
            incident_id=incident.id,
            steps=steps,
        )
