"""
Controller reducer: processes events and produces state updates and incidents.

P0 fixes:
  F7: Receipt only resolves incident when ALL steps verified (composite).
  F10: Deterministic incident IDs; dedup on replay; persist lifecycle.
  F12: Typed diagnosis - unavailable services don't become file_missing.
"""
from __future__ import annotations

from typing import Any

from schemas.types import Event, EventKind, Severity, IncidentReport
from schemas.types import _deterministic_id


class Reducer:
    """Processes events and reduces them into state/decisions."""

    def __init__(self):
        self.incidents: list[IncidentReport] = []
        self.state: dict[str, Any] = {}
        # F10: Track seen incident IDs for dedup
        self._seen_incident_ids: set[str] = set()
        # F7: Track plan receipts for composite verification
        self._plan_receipts: dict[str, list[bool]] = {}
        self._plan_step_counts: dict[str, int] = {}

    def reduce(self, event: Event) -> list[IncidentReport]:
        """Process an event, update state, and return any new incidents."""
        new_incidents: list[IncidentReport] = []

        if event.kind == EventKind.OBSERVATION:
            new_incidents.extend(self._handle_observation(event))
        elif event.kind == EventKind.INCIDENT:
            self._handle_incident(event)
        elif event.kind == EventKind.RECEIPT:
            self._handle_receipt(event)
        elif event.kind == EventKind.PLAN:
            self._handle_plan(event)

        # F10: Deduplicate incidents
        for inc in new_incidents:
            if inc.id not in self._seen_incident_ids:
                self.incidents.append(inc)
                self._seen_incident_ids.add(inc.id)

        # Update state
        if event.subject:
            self.state.setdefault(event.subject, {})
            self.state[event.subject].update(event.payload)

        return new_incidents

    def _handle_observation(self, event: Event) -> list[IncidentReport]:
        incidents: list[IncidentReport] = []
        payload = event.payload
        source = event.source.lower()

        is_file_source = ("file" in source or
                          payload.get("resource_kind") == "file" or
                          "service" not in source)
        is_service_source = "service" in source or "service" in payload

        if payload.get("exists") is False and is_file_source and not is_service_source:
            inc = IncidentReport.deterministic(
                component=event.subject,
                symptom="file_missing",
                severity=Severity.WARN,
                evidence=[event.to_dict()],
            )
            incidents.append(inc)

        # Service down
        if (payload.get("active") in ("inactive", "failed")
                and payload.get("exists", False)):
            inc = IncidentReport.deterministic(
                component=payload.get("service", event.subject),
                symptom="service_down",
                severity=Severity.ERROR,
                evidence=[event.to_dict()],
            )
            incidents.append(inc)

        # Error payloads
        if "error" in payload:
            inc = IncidentReport.deterministic(
                component=event.subject,
                symptom="collection_error",
                severity=Severity.ERROR,
                evidence=[event.to_dict()],
            )
            incidents.append(inc)

        return incidents

    def _handle_incident(self, event: Event) -> None:
        incident = IncidentReport.from_dict(event.payload)
        if incident.id not in self._seen_incident_ids:
            self.incidents.append(incident)
            self._seen_incident_ids.add(incident.id)

    def _handle_plan(self, event: Event) -> None:
        plan_payload = event.payload
        plan_id = plan_payload.get("id", "")
        step_count = len(plan_payload.get("steps", []))
        if plan_id:
            self._plan_step_counts[plan_id] = step_count
            self._plan_receipts.setdefault(plan_id, [])

    def _handle_receipt(self, event: Event) -> None:
        """F7: Only resolve incident when ALL steps are verified."""
        if not event.payload.get("verified"):
            return
        if event.payload.get("simulated"):
            return

        plan_id = event.payload.get("plan_id", "")
        if not plan_id:
            return

        self._plan_receipts.setdefault(plan_id, [])
        self._plan_receipts[plan_id].append(True)

        expected = self._plan_step_counts.get(plan_id, 0)
        actual = len(self._plan_receipts[plan_id])

        if expected > 0 and actual >= expected:
            for inc in self.incidents:
                if inc.plan_id == plan_id and not inc.resolved:
                    inc.resolved = True

    def resolve_incident(self, incident_id: str, plan_id: str) -> None:
        """Explicitly resolve an incident (called by appliance)."""
        for inc in self.incidents:
            if inc.id == incident_id:
                inc.resolved = True
                inc.plan_id = plan_id

    def open_incidents(self) -> list[IncidentReport]:
        return [i for i in self.incidents if not i.resolved]

    def snapshot(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "incidents_total": len(self.incidents),
            "incidents_open": len(self.open_incidents()),
        }
