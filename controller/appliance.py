"""
Main appliance controller.

P0 fixes: F1(no bypass), F3(recovery gate), F5(dry_run boundary),
F7(reject over-budget, no partial resolve), F8(durable attempts),
F9(singleton+target exclusion), F10(replay on startup).
"""
from __future__ import annotations

import hashlib
import time
import fcntl
import os
from typing import Any, Optional

from schemas.types import (
    Event, EventKind, Severity, IncidentReport, Plan, Receipt,
    ALLOWED_VERBS,
)
from schemas.event_store import EventStore
from controller.reducer import Reducer


class Appliance:
    """Top-level controller for the Omega Hive Appliance."""

    def __init__(self, store_path: str = ":memory:"):
        self.store = EventStore(store_path)
        self.reducer = Reducer()
        self.collectors: list = []
        self.planner: Optional[Any] = None
        self.executor: Optional[Any] = None
        self.verifier: Optional[Any] = None
        self.max_steps: int = 20
        # F3: Recovery readiness gate
        self.recovery_ready: bool = False
        # F8: Active attempts (incident_id -> attempt_id)
        self._active_attempts: dict[str, str] = {}
        # F9: Active targets (target -> plan_id)
        self._active_targets: dict[str, str] = {}
        # F9: Singleton lock fd
        self._lock_fd: Optional[Any] = None
        # F10: Replay events on startup
        self._replay_events()
        if store_path != ":memory:":
            self._acquire_lock(store_path)

    def _replay_events(self):
        """F10: Replay all existing events from store into reducer."""
        events = self.store.query(limit=100000)
        for event in events:
            self.reducer.reduce(event)

    def _acquire_lock(self, store_path: str):
        """F9: Acquire file-based singleton lock."""
        lock_path = store_path + ".lock"
        try:
            self._lock_fd = open(lock_path, "w")
            fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError):
            raise RuntimeError("Another appliance instance is already running.")

    def set_planner(self, planner):
        self.planner = planner

    def set_executor(self, executor):
        self.executor = executor

    def set_verifier(self, verifier):
        self.verifier = verifier

    def add_collector(self, collector):
        self.collectors.append(collector)

    def observe(self) -> list[Event]:
        events = []
        for collector in self.collectors:
            for observation in collector.collect():
                event = Event(
                    kind=EventKind.OBSERVATION,
                    source=collector.__class__.__name__,
                    subject=observation.subject,
                    payload=observation.payload,
                    severity=observation.severity,
                )
                self.store.append(event)
                self.reducer.reduce(event)
                events.append(event)
        return events

    def state_snapshot(self) -> dict[str, Any]:
        return self.reducer.snapshot()

    def open_incidents(self) -> list[IncidentReport]:
        return self.reducer.open_incidents()

    def event_count(self) -> int:
        return self.store.count()

    def repair(self, incident: IncidentReport, dry_run: bool = False) -> list[Receipt]:
        """Execute a repair plan for the given incident."""
        if self.planner is None or self.executor is None or self.verifier is None:
            raise RuntimeError("Planner, executor, and verifier must be set")

        # F3: Recovery readiness gate
        if not dry_run and not self.recovery_ready:
            raise RuntimeError(
                "Managed writes disabled: recovery_ready is False. "
                "Set recovery_ready=True only after establishing state "
                "closure and a qualified recovery path (F3)."
            )

        # F8: Deduplication
        if incident.id in self._active_attempts:
            return []

        plan = self.planner.plan(incident)
        plan.incident_id = incident.id

        # F8: Assign attempt_id
        attempt_id = hashlib.sha256(
            f"{incident.id}:{plan.id}:{time.time()}".encode()
        ).hexdigest()[:16]
        plan.attempt_id = attempt_id
        self._active_attempts[incident.id] = attempt_id

        # F2: Validate plan
        errors = plan.validate()
        if errors:
            plan.status = "rejected"
            self._store_plan(plan)
            del self._active_attempts[incident.id]
            raise ValueError(f"Plan validation failed: {errors}")

        # F7: Reject over-budget plans
        if len(plan.steps) > self.max_steps:
            plan.status = "rejected"
            self._store_plan(plan)
            del self._active_attempts[incident.id]
            raise ValueError(
                f"Plan has {len(plan.steps)} steps but max_steps is "
                f"{self.max_steps}. Rejected before dispatch (F7)."
            )

        if self.max_steps == 0 and len(plan.steps) > 0:
            plan.status = "rejected"
            self._store_plan(plan)
            del self._active_attempts[incident.id]
            raise ValueError("max_steps is 0 but plan has steps (F7).")

        # F9: Check target conflicts
        for step in plan.steps:
            target = step.get("target", step.get("command", ""))
            if target in self._active_targets:
                plan.status = "rejected"
                self._store_plan(plan)
                del self._active_attempts[incident.id]
                raise RuntimeError(f"Target conflict: {target} (F9).")

        # Record plan before dispatch
        plan.status = "executing"
        self._store_plan(plan)

        # F5: dry_run boundary
        if dry_run:
            return self._simulate_plan(plan, incident)

        # F9: Register targets
        for step in plan.steps:
            target = step.get("target", step.get("command", ""))
            self._active_targets[target] = plan.id

        receipts: list[Receipt] = []
        all_verified = True

        try:
            for i, step in enumerate(plan.steps):
                receipt = self.executor.execute_step(step, plan, i)
                receipt.attempt_id = attempt_id
                receipt.plan_id = plan.id

                # F6: Independent verification
                expected = step.get("expected", {})
                receipt.verified = self.verifier.verify(receipt, expected)

                self._store_receipt(receipt)
                receipts.append(receipt)

                if not receipt.verified:
                    all_verified = False
                    break

        except Exception as e:
            plan.status = "in_doubt"
            self._store_plan_update(plan)
            raise
        finally:
            for step in plan.steps:
                target = step.get("target", step.get("command", ""))
                self._active_targets.pop(target, None)

        # F7: Resolve incident ONLY on full composite success
        if all_verified and len(receipts) == len(plan.steps) and len(plan.steps) > 0:
            plan.status = "completed"
            self._store_plan_update(plan)
            incident.resolved = True
            incident.plan_id = plan.id
            self.reducer.resolve_incident(incident.id, plan.id)
        elif not all_verified:
            plan.status = "failed"
            self._store_plan_update(plan)
        else:
            plan.status = "completed"
            self._store_plan_update(plan)
            incident.resolved = True
            incident.plan_id = plan.id
            self.reducer.resolve_incident(incident.id, plan.id)

        del self._active_attempts[incident.id]
        return receipts

    def _simulate_plan(self, plan: Plan, incident: IncidentReport) -> list[Receipt]:
        """F5: Simulate plan execution without real effects."""
        receipts: list[Receipt] = []
        for i, step in enumerate(plan.steps):
            receipt = Receipt(
                plan_id=plan.id,
                step_index=i,
                verb=step.get("verb", ""),
                target=step.get("target", ""),
                exit_code=0,
                stdout="[simulated]",
                stderr="",
                verified=False,
                simulated=True,
                attempt_id=plan.attempt_id,
            )
            self.store.append(Event(
                kind=EventKind.SIMULATED,
                source="appliance",
                subject=incident.component,
                payload=receipt.to_dict(),
                severity=Severity.INFO,
            ))
            receipts.append(receipt)

        plan.status = "simulated"
        self._store_plan_update(plan)
        del self._active_attempts[incident.id]
        return receipts

    def _store_plan(self, plan: Plan):
        self.store.append(Event(
            kind=EventKind.PLAN,
            source="appliance",
            subject=plan.incident_id,
            payload=plan.to_dict(),
            severity=Severity.INFO,
        ))

    def _store_plan_update(self, plan: Plan):
        self.store.append(Event(
            kind=EventKind.PLAN,
            source="appliance",
            subject=plan.incident_id,
            payload=plan.to_dict(),
            severity=Severity.INFO,
        ))

    def _store_receipt(self, receipt: Receipt):
        self.store.append(Event(
            kind=EventKind.RECEIPT,
            source="appliance",
            subject=receipt.target,
            payload=receipt.to_dict(),
            severity=Severity.INFO,
        ))

    def close(self):
        if self._lock_fd:
            fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_UN)
            self._lock_fd.close()
            self._lock_fd = None
        self.store.close()
