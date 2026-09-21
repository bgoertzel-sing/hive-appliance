"""
Planner: generates repair plans from incidents.

C02 work package — simple planner / MeTTa reasoning stub.

P0 fixes:
  F1: Only ALLOWED_VERBS in plan steps.
  F2: Strict plan schema validation.
  F13: Resource limits (max steps, timeout caps).
"""
from __future__ import annotations

import uuid
from typing import Any

from schemas.types import ALLOWED_VERBS, IncidentReport, Plan

# F13: Resource limits
MAX_PLAN_STEPS = 10
MAX_STEP_TIMEOUT = 120  # seconds


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
        """Generate a plan for the given incident.

        F1: All step verbs validated against ALLOWED_VERBS.
        F2: Plan validated before returning.
        F8: attempt_id generated for dedup tracking.
        F13: Step count capped at MAX_PLAN_STEPS.
        """
        attempt_id = "att_" + uuid.uuid4().hex[:12]

        for rule in self.rules:
            if rule["symptom"] == incident.symptom:
                steps = []
                for step in rule["steps"]:
                    s = dict(step)
                    # Substitute {component} in command
                    s["command"] = s["command"].replace("{component}", incident.component)
                    # F13: Cap timeout
                    if "timeout" in s:
                        s["timeout"] = min(s["timeout"], MAX_STEP_TIMEOUT)
                    steps.append(s)

                # F13: Enforce max steps
                steps = steps[:MAX_PLAN_STEPS]

                p = Plan(
                    incident_id=incident.id,
                    steps=steps,
                    status="proposed",
                    attempt_id=attempt_id,
                )

                # F1/F2: Validate
                errors = p.validate()
                if errors:
                    return Plan(
                        incident_id=incident.id,
                        steps=[],
                        status="rejected",
                        attempt_id=attempt_id,
                    )
                return p

        # No matching rule — empty plan
        return Plan(
            incident_id=incident.id,
            steps=[],
            status="proposed",
            attempt_id=attempt_id,
        )

    def add_rule(self, symptom: str, steps: list[dict[str, Any]],
                 severity_min: str = "warn") -> None:
        """Add a custom repair rule.

        F1: Validates verbs at rule-add time.
        """
        for step in steps:
            verb = step.get("verb", "")
            if verb not in ALLOWED_VERBS:
                raise ValueError(f"Verb '{verb}' not in ALLOWED_VERBS: {ALLOWED_VERBS}")
        self.rules.append({
            "symptom": symptom,
            "severity_min": severity_min,
            "steps": steps,
        })
