"""
Main appliance controller: orchestrates collectors, reducer, and event store.

C01 work package — controller integration.
"""
from __future__ import annotations

import time
from typing import Any

from schemas.types import Event, EventKind, Severity, IncidentReport
from schemas.event_store import EventStore
from controller.reducer import Reducer


class Appliance:
    """Top-level controller for the Omega Hive Appliance."""

    def __init__(self, store_path: str = ":memory:"):
        self.store = EventStore(store_path)
        self.reducer = Reducer()
        self.collectors: list[Any] = []  # BaseCollector instances

    def add_collector(self, collector: Any) -> None:
        """Register a collector."""
        self.collectors.append(collector)

    def observe(self) -> list[Event]:
        """Run all collectors and persist their events."""
        all_events: list[Event] = []
        for collector in self.collectors:
            try:
                events = collector.collect()
                for event in events:
                    self.store.append(event)
                    self.reducer.reduce(event)
                all_events.extend(events)
            except Exception as e:
                err_event = Event(
                    kind=EventKind.OBSERVATION,
                    source="appliance",
                    subject=collector.name if hasattr(collector, "name") else "unknown",
                    payload={"error": str(e)},
                    severity=Severity.ERROR,
                )
                self.store.append(err_event)
                self.reducer.reduce(err_event)
                all_events.append(err_event)
        return all_events

    def record_incident(self, incident: IncidentReport) -> None:
        """Record an incident in the event store."""
        event = Event(
            kind=EventKind.INCIDENT,
            source="reducer",
            subject=incident.component,
            payload=incident.to_dict(),
            severity=incident.severity,
        )
        self.store.append(event)
        self.reducer.reduce(event)

    def open_incidents(self) -> list[IncidentReport]:
        return self.reducer.open_incidents()

    def state_snapshot(self) -> dict[str, Any]:
        return self.reducer.snapshot()

    def event_count(self) -> int:
        return self.store.count()

    def close(self) -> None:
        self.store.close()
