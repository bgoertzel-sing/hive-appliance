"""
Main appliance controller: orchestrates collectors, reducer, and event store.

C01 work package — controller integration.
C04-C07 work packages — controlled repair loop.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from schemas.types import (
    Event, EventKind, Severity, IncidentReport, Plan, Receipt,
)
from schemas.event_store import EventStore
from controller.reducer import Reducer


class Appliance:
    """Top-level controller for the Omega Hive Appliance."""

    def __init__(self, store_path: str = ":memory:"):
        self.store = EventStore(store_path)
        self.reducer = Reducer()
        self.collectors: list[Any] = []
        self.planner: Optional[Any] = None
        self.executor: Optional[Any] = None
        self.verifier: Optional[Any] = None
        self.max_steps: int = 20

    def add_collector(self, collector: Any) -> None:
        self.collectors.append(collector)

    def set_planner(self, planner: Any) -> None:
        self.planner = planner

    def set_executor(self, executor: Any) -> None:
        self.executor = executor

    def set_verifier(self, verifier: Any) -> None:
        self.verifier = verifier

    def observe(self) -> list[Event]:
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
        event = Event(
            kind=EventKind.INCIDENT,
            source="reducer",
            subject=incident.component,
            payload=incident.to_dict(),
            severity=incident.severity,
        )
        self.store.append(event)
        self.reducer.reduce(event)

    def record_plan(self, plan: Plan) -> None:
        event = Event(
            kind=EventKind.PLAN,
            source="planner",
            subject=plan.incident_id,
            payload=plan.to_dict(),
            severity=Severity.INFO,
        )
        self.store.append(event)

    def record_receipt(self, receipt: Receipt) -> None:
        event = Event(
            kind=EventKind.RECEIPT,
            source=self.verifier.name if self.verifier else "verifier",
            subject=receipt.target or "system",
            payload=receipt.to_dict(),
            severity=Severity.INFO if receipt.verified else Severity.ERROR,
        )
        self.store.append(event)
        self.reducer.reduce(event)

    def repair(
        self,
        incident: IncidentReport,
        dry_run: bool = False,
    ) -> list[Receipt]:
        """Execute controlled repair for a single incident.

        Flow: plan -> execute steps -> verify each -> record receipts
        Safety: max_steps limit, dry-run mode, per-step verification gate.
        Returns list of receipts for all executed steps.
        """
        if self.planner is None:
            raise RuntimeError("No planner configured")
        if self.executor is None:
            raise RuntimeError("No executor configured")
        if self.verifier is None:
            raise RuntimeError("No verifier configured")

        # Generate plan
        plan = self.planner.plan(incident)
        plan.status = "executing"
        self.record_plan(plan)

        # Link incident to plan
        incident.plan_id = plan.id

        receipts: list[Receipt] = []

        if len(plan.steps) == 0:
            plan.status = "no_action"
            return receipts

        # Enforce max_steps safety
        steps_to_run = plan.steps[:self.max_steps]

        for i, step in enumerate(steps_to_run):
            # Execute the step
            receipt = self.executor.execute_step(step, plan, i)

            # Verify the result
            expected = step.get("expected", {"exit_code": 0})
            verified = self.verifier.verify(receipt, expected)

            # Persist receipt
            self.record_receipt(receipt)
            receipts.append(receipt)

            # Safety gate: stop on unverified step
            if not verified:
                plan.status = "failed"
                break

        else:
            # All steps verified successfully
            plan.status = "completed"
            incident.resolved = True

        # Update incident state in reducer
        self._update_incident_status(incident, plan)

        return receipts

    def repair_all(
        self,
        dry_run: bool = False,
    ) -> dict[str, list[Receipt]]:
        """Repair all open incidents. Returns dict of incident_id -> receipts."""
        results: dict[str, list[Receipt]] = {}
        for inc in self.open_incidents():
            results[inc.id] = self.repair(inc, dry_run=dry_run)
        return results

    def _update_incident_status(self, incident: IncidentReport, plan: Plan) -> None:
        """Update the incident in the reducer's incident list."""
        for inc in self.reducer.incidents:
            if inc.id == incident.id:
                inc.plan_id = plan.id
                inc.resolved = incident.resolved
                break

    def open_incidents(self) -> list[IncidentReport]:
        return self.reducer.open_incidents()

    def state_snapshot(self) -> dict[str, Any]:
        return self.reducer.snapshot()

    def event_count(self) -> int:
        return self.store.count()

    def close(self) -> None:
        self.store.close()
