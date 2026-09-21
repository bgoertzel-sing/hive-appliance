"""
Controller reducer: processes events and produces state updates and incidents.

C01 work package — typed records and event store integration.
C07 work package — service_down incident detection.

P0 fixes:
  F7: Receipt only resolves incident when ALL steps verified (composite).
  F10: Deterministic incident IDs; dedup on replay; persist lifecycle.
  F12: Typed diagnosis - unavailable services don't become file_missing.
"""
from __future__ import annotations

from typing import Any

from schemas.types import Event, EventKind, IncidentReport, Severity


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

        # Update state with latest observation
        if event.subject:
            self.state.setdefault(event.subject, {})
            self.state[event.subject].update(event.payload)

        return new_incidents

    def _handle_observation(self, event: Event) -> list[IncidentReport]:
        incidents: list[IncidentReport] = []
        payload = event.payload
        source = event.source.lower()

        # F12: Typed diagnosis — distinguish file vs service observations
        is_file_source = ("file" in source or
                          payload.get("resource_kind") == "file" or
                          "service" not in source)
        is_service_source = "service" in source or "service" in payload

        # Check for missing files (but not for service observations)
        if payload.get("exists") is False and is_file_source and not is_service_source:
            inc = IncidentReport.deterministic(
                component=event.subject,
                symptom="file_missing",
                severity=Severity.WARN,
                evidence=[event.to_dict()],
            )
            incidents.append(inc)

        # Check for service down (from ServiceCollector)
        if (payload.get("active") in ("inactive", "failed")
                and payload.get("exists", False)):
            inc = IncidentReport.deterministic(
                component=payload.get("service", event.subject),
                symptom="service_down",
                severity=Severity.ERROR,
                evidence=[event.to_dict()],
            )
            incidents.append(inc)

        # Check for error payloads
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
        """F7: Register plan step count for composite receipt tracking."""
        plan_payload = event.payload
        plan_id = plan_payload.get("id", "")
        step_count = len(plan_payload.get("steps", []))
        if plan_id and step_count:
            self._plan_step_counts[plan_id] = step_count
            self._plan_receipts[plan_id] = []

    def _handle_receipt(self, event: Event) -> None:
        """F7: Only resolve incident when ALL plan steps are verified."""
        plan_id = event.payload.get("plan_id", "")
        verified = event.payload.get("verified", False)

        if plan_id in self._plan_step_counts:
            # F7: Composite receipt tracking
            self._plan_receipts.setdefault(plan_id, [])
            self._plan_receipts[plan_id].append(verified)

            expected = self._plan_step_counts[plan_id]
            received = self._plan_receipts[plan_id]
            if len(received) >= expected and all(received):
                # All steps verified — resolve incident
                for inc in self.incidents:
                    if inc.plan_id == plan_id:
                        inc.resolved = True
        else:
            # Legacy path: single-receipt resolution
            if verified:
                for inc in self.incidents:
                    if inc.plan_id == plan_id:
                        inc.resolved = True

    def open_incidents(self) -> list[IncidentReport]:
        return [i for i in self.incidents if not i.resolved]

    def snapshot(self) -> dict[str, Any]:
        """Return a snapshot of the current state."""
        return {
            "state": self.state,
            "incidents_total": len(self.incidents),
            "incidents_open": len(self.open_incidents()),
        }

    def restore_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Restore reducer state from a checkpoint snapshot."""
        self.state = snapshot.get("state", {})
        self.incidents = []
        self._seen_incident_ids = set()

    def state_snapshot(self) -> dict[str, Any]:
        """Alias for snapshot() for API compatibility."""
        return self.snapshot()
