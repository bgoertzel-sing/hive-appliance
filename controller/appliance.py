"""
Main appliance controller: orchestrates collectors, reducer, and event store.

C01 work package — controller integration.
C04-C07 work packages — controlled repair loop.

P0 fixes (Astra review):
- F5: dry_run enforced at dispatch boundary, not just executor selection
- F7: reject over-budget plans before dispatch; resolve only on full completion
- F8: deduplicate repair requests (idempotency by incident id)
- F6: NoopExecutor receipts not treated as real verification
- F10: replay events from store on construction
"""
from __future__ import annotations

import time
from typing import Any, Optional

from schemas.types import (
    Event, EventKind, Severity, IncidentReport, Plan, Receipt,
)
from schemas.event_store import EventStore
from controller.reducer import Reducer
import tempfile
from recovery.checkpoint import CheckpointManager, StateCheckpoint
from recovery.upgrade import UpgradeController, UpgradeManifest, UpgradeResult


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
        self._active_repairs: set[str] = set()  # F8: track active repairs


        # M3: Recovery — checkpoint & upgrade support
        self._checkpoint_mgr = CheckpointManager(
            store_path if store_path != ":memory:" else tempfile.mkdtemp(prefix="hive-ckpt-")
        )
        self._upgrade_ctrl = UpgradeController(
            self._checkpoint_mgr, self.executor, self.verifier
        )

        # F10: Replay existing events into reducer on construction
        existing = self.store.query()
        for event in existing:
            self.reducer.reduce(event)

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

    def _is_simulation(self) -> bool:
        """F6/F5: Check if current executor is a simulation (noop) executor."""
        from executor.noop_executor import NoopExecutor
        return isinstance(self.executor, NoopExecutor)

    def repair(
        self,
        incident: IncidentReport,
        dry_run: bool = False,
    ) -> list[Receipt]:
        """Execute controlled repair for a single incident.

        Flow: plan -> execute steps -> verify each -> record receipts
        Safety: max_steps limit, dry-run mode, per-step verification gate.
        Returns list of receipts for all executed steps.

        P0 fixes:
        - F5: dry_run is enforced at the dispatch boundary. In dry_run mode,
          no real effects are dispatched and no incident is resolved.
        - F7: Plans exceeding max_steps are rejected before any dispatch.
          Incident is resolved only when ALL steps are verified.
        - F8: Duplicate repair requests for the same incident are rejected.
        - F6: Simulation (noop) receipts are not treated as real verification.
        """
        if self.planner is None:
            raise RuntimeError("No planner configured")
        if self.executor is None:
            raise RuntimeError("No executor configured")
        if self.verifier is None:
            raise RuntimeError("No verifier configured")

        # F8: Deduplicate repair requests by component+symptom
        repair_key = (incident.component, incident.symptom)
        if repair_key in self._active_repairs:
            plan = self.planner.plan(incident)
            plan.status = "duplicate"
            self.record_plan(plan)
            return []
        # Also check if this specific incident is already resolved
        if incident.resolved:
            plan = self.planner.plan(incident)
            plan.status = "duplicate"
            self.record_plan(plan)
            return []
        # Also check if a previous repair already resolved this component+symptom
        for inc in self.reducer.incidents:
            if (inc.component == incident.component and
                inc.symptom == incident.symptom and inc.resolved):
                plan = self.planner.plan(incident)
                plan.status = "duplicate"
                self.record_plan(plan)
                return []
        self._active_repairs.add(repair_key)

        try:
            return self._do_repair(incident, dry_run)
        finally:
            self._active_repairs.discard(repair_key)

    def _do_repair(self, incident: IncidentReport, dry_run: bool) -> list[Receipt]:
        # Generate plan
        plan = self.planner.plan(incident)
        plan.status = "executing"

        # Link incident to plan
        incident.plan_id = plan.id

        receipts: list[Receipt] = []

        # F7: Reject over-budget plans before any dispatch
        if len(plan.steps) > self.max_steps:
            plan.status = "rejected_over_budget"
            self.record_plan(plan)
            self._update_incident_status(incident, plan)
            return receipts

        if len(plan.steps) == 0:
            plan.status = "no_action"
            self.record_plan(plan)
            self._update_incident_status(incident, plan)
            return receipts

        self.record_plan(plan)

        # F5/F6: Determine simulation mode
        is_simulation = self._is_simulation()

        for i, step in enumerate(plan.steps):
            # F5: In dry_run mode, don't dispatch real effects
            if dry_run:
                receipt = Receipt(
                    plan_id=plan.id,
                    step_index=i,
                    verb=step.get("verb", ""),
                    target=step.get("target", ""),
                    exit_code=0,
                    stdout="[dry-run] preview",
                    stderr="",
                    verified=False,  # F6: preview receipts are NOT verified
                )
                self.record_receipt(receipt)
                receipts.append(receipt)
                continue

            # Execute the step
            receipt = self.executor.execute_step(step, plan, i)

            # F6: Simulation receipts should not be treated as verified
            if is_simulation:
                receipt.verified = False

            # Verify the result
            expected = step.get("expected", {"exit_code": 0})
            verified = self.verifier.verify(receipt, expected)

            # F6: In simulation mode, don't trust executor attestation
            if is_simulation:
                verified = False

            receipt.verified = verified

            # Persist receipt
            self.record_receipt(receipt)
            receipts.append(receipt)

            # Safety gate: stop on unverified step
            if not verified:
                plan.status = "failed"
                break

        else:
            # All steps processed
            if dry_run:
                plan.status = "previewed"
                # F5: dry_run must NOT resolve the incident
            elif is_simulation:
                plan.status = "simulated"
                # F6: Simulation mode does not resolve
            else:
                plan.status = "completed"
                incident.resolved = True

        # Update incident state in reducer
        self._update_incident_status(incident, plan)

        return receipts

    def _update_incident_status(self, incident: IncidentReport, plan: Plan) -> None:
        """Update the incident in the reducer's incident list."""
        for inc in self.reducer.incidents:
            if inc.id == incident.id:
                inc.plan_id = plan.id
                inc.resolved = incident.resolved
                break

    def repair_all(
        self,
        dry_run: bool = False,
    ) -> dict[str, list[Receipt]]:
        """Repair all open incidents. Returns dict of incident_id -> receipts."""
        results: dict[str, list[Receipt]] = {}
        for inc in self.open_incidents():
            results[inc.id] = self.repair(inc, dry_run=dry_run)
        return results

    def open_incidents(self) -> list[IncidentReport]:
        return self.reducer.open_incidents()

    def state_snapshot(self) -> dict[str, Any]:
        return self.reducer.state_snapshot()

    def event_count(self) -> int:
        return self.store.count()


    # ── M3: State Recovery (C09) ──────────────────────────

    def checkpoint(self, label: str = "") -> StateCheckpoint:
        """Create a state checkpoint of the current appliance state."""
        state = self.state_snapshot()
        # Include event count and open incident ids as metadata
        meta = {
            "event_count": self.event_count(),
            "open_incidents": [i.id for i in self.open_incidents()],
        }
        return self._checkpoint_mgr.create(state, label=label, metadata=meta)

    def restore(self, ckpt_id: str) -> bool:
        """Restore appliance state from a checkpoint.

        This resets the reducer to the checkpointed state.  The event store
        is *not* truncated (events are append-only), but the reducer's
        derived state (services, incidents, etc.) is replaced wholesale.

        Returns True if the checkpoint was found and restored.
        """
        ckpt = self._checkpoint_mgr.load(ckpt_id)
        if ckpt is None:
            return False
        self.reducer.restore_snapshot(ckpt.appliance_state)
        # Record a restoration event
        evt = Event(
            kind=EventKind.OBSERVATION,
            source="recovery",
            subject="checkpoint_restore",
            payload={"checkpoint_id": ckpt_id, "label": ckpt.label},
            severity=Severity.INFO,
        )
        self.store.append(evt)
        return True

    def list_checkpoints(self) -> list[StateCheckpoint]:
        """List all persisted checkpoints."""
        return self._checkpoint_mgr.list()

    def delete_checkpoint(self, ckpt_id: str) -> bool:
        """Delete a checkpoint by id."""
        return self._checkpoint_mgr.delete(ckpt_id)

    def prune_checkpoints(self, keep: int = 5) -> int:
        """Keep only the newest *keep* checkpoints."""
        return self._checkpoint_mgr.prune(keep)

    # ── M3: Controlled Upgrades (C10) ─────────────────────

    def upgrade(self, manifest: UpgradeManifest,
                dry_run: bool = False) -> UpgradeResult:
        """Execute a controlled upgrade with checkpoint safety net.

        On failure, the pre-upgrade checkpoint is available for
        manual or automatic rollback via restore().
        """
        # Wire current executor/verifier into upgrade controller
        self._upgrade_ctrl._executor = self.executor
        self._upgrade_ctrl._verifier = self.verifier
        state = self.state_snapshot()
        result = self._upgrade_ctrl.execute(manifest, state, dry_run=dry_run)
        if result.rolled_back and result.pre_checkpoint_id:
            self.restore(result.pre_checkpoint_id)
        return result

    def close(self) -> None:
        self.store.close()
