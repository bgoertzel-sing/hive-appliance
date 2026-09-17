"""
Controller reducer: processes events and produces state updates and incidents.

C01 work package — typed records and event store integration.
C07 work package — service_down incident detection.
"""
from __future__ import annotations

from typing import Any

from schemas.types import Event, EventKind, Severity, IncidentReport


class Reducer:
    """Processes events and reduces them into state/decisions."""

    def __init__(self):
        self.incidents: list[IncidentReport] = []
        self.state: dict[str, Any] = {}

    def reduce(self, event: Event) -> list[IncidentReport]:
        """Process an event, update state, and return any new incidents."""
        new_incidents: list[IncidentReport] = []

        if event.kind == EventKind.OBSERVATION:
            new_incidents.extend(self._handle_observation(event))
        elif event.kind == EventKind.INCIDENT:
            self._handle_incident(event)
        elif event.kind == EventKind.RECEIPT:
            self._handle_receipt(event)

        # Store new incidents in self.incidents
        for inc in new_incidents:
            self.incidents.append(inc)

        # Update state with latest observation
        if event.subject:
            self.state.setdefault(event.subject, {})
            self.state[event.subject].update(event.payload)

        return new_incidents

    def _handle_observation(self, event: Event) -> list[IncidentReport]:
        incidents: list[IncidentReport] = []

        # Check for missing files (but not for service observations)
        if event.payload.get("exists") is False and "service" not in event.payload:
            incidents.append(IncidentReport(
                severity=Severity.WARN,
                component=event.subject,
                symptom="file_missing",
                evidence=[event.to_dict()],
            ))

        # Check for service down (from ServiceCollector)
        payload = event.payload
        if (payload.get("active") in ("inactive", "failed")
                and payload.get("exists", False)):
            incidents.append(IncidentReport(
                severity=Severity.ERROR,
                component=event.payload.get("service", event.subject),
                symptom="service_down",
                evidence=[event.to_dict()],
            ))

        # Check for error payloads
        if "error" in event.payload:
            incidents.append(IncidentReport(
                severity=Severity.ERROR,
                component=event.subject,
                symptom="collection_error",
                evidence=[event.to_dict()],
            ))

        return incidents

    def _handle_incident(self, event: Event) -> None:
        incident = IncidentReport.from_dict(event.payload)
        self.incidents.append(incident)

    def _handle_receipt(self, event: Event) -> None:
        if event.payload.get("verified"):
            plan_id = event.payload.get("plan_id", "")
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
        """Restore reducer state from a checkpoint snapshot.

        Replaces the current derived state wholesale.  Incidents are
        rebuilt from the snapshot's incident list if present.
        """
        self.state = snapshot.get("state", {})
        # Rebuild incidents list from snapshot if available
        self.incidents = []
        # The snapshot from state_snapshot() contains counts, not full incidents.
        # A full restore would need the incident objects stored separately;
        # for now we reset to empty (events are still in the append-only store).
        self.incidents = []

    def state_snapshot(self) -> dict[str, Any]:
        """Alias for snapshot() for API compatibility."""
        return self.snapshot()
