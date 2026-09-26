"""
Main appliance controller: orchestrates collectors, reducer, and event store.

C01 work package — controller integration.
C04-C07 work packages — controlled repair loop.

P0 fixes (Astra review):
- F1: Allowed verbs only — validated at planner + executor boundary
- F2: Strict plan schema validation
- F3: Recovery-ready gate — checkpoint before repair, rollback on failure
- F5: dry_run enforced at dispatch boundary, not just executor selection
- F6: NoopExecutor receipts not treated as real verification
- F7: Composite receipt — resolve only when ALL steps verified
- F8: Deduplicate repair requests (idempotency by incident id)
- F10: Replay events from store on construction
- F13: Resource limits (step count, timeouts)
"""
from __future__ import annotations

import logging
import os
import tempfile
from typing import Any, Optional

from controller.reducer import Reducer
from recovery.checkpoint import CheckpointManager, StateCheckpoint
from recovery.upgrade import UpgradeController, UpgradeManifest, UpgradeResult
from schemas.event_store import EventStore
from schemas.types import (
    Event,
    EventKind,
    IncidentReport,
    Plan,
    Receipt,
    Severity,
)

logger = logging.getLogger(__name__)

# U1: distinct repair outcomes (see Appliance.repair_outcomes)
OUTCOME_RESOLVED = "resolved"
OUTCOME_SIMULATED = "simulated"
OUTCOME_BLOCKED_NO_CHECKPOINT = "blocked_no_checkpoint"
OUTCOME_ROLLED_BACK = "rolled_back"
OUTCOME_ROLLBACK_FAILED = "rollback_failed"
OUTCOME_REJECTED = "rejected"
OUTCOME_NO_PLAN = "no_plan"


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
        self._completed_repairs: set[str] = set()  # F8: track completed repairs
        # U1: last outcome per incident id (durable copy is a RECOVERY event)
        self.repair_outcomes: dict[str, str] = {}

        # M3: Recovery — checkpoint & upgrade support
        if store_path == ":memory:":
            _ckpt_dir = tempfile.mkdtemp(prefix="hive-ckpt-")
        elif os.path.isfile(store_path) or store_path.endswith(".db"):
            _ckpt_dir = os.path.dirname(os.path.abspath(store_path))
        else:
            _ckpt_dir = store_path
        self._checkpoint_mgr = CheckpointManager(_ckpt_dir)
        self._upgrade_ctrl = UpgradeController(
            self._checkpoint_mgr, self.executor, self.verifier
        )

        # F10: Replay existing events into reducer on construction
        existing = self.store.query()
        for event in existing:
            self.reducer.reduce(event)

    def add_collector(self, collector: Any) -> None:
        """Execute add collector operation."""
        self.collectors.append(collector)

    def set_planner(self, planner: Any) -> None:
        """Execute set planner operation."""
        self.planner = planner

    def set_executor(self, executor: Any) -> None:
        """Execute set executor operation."""
        self.executor = executor
        # Update upgrade controller reference
        self._upgrade_ctrl = UpgradeController(
            self._checkpoint_mgr, self.executor, self.verifier
        )

    def set_verifier(self, verifier: Any) -> None:
        """Execute set verifier operation."""
        self.verifier = verifier
        self._upgrade_ctrl = UpgradeController(
            self._checkpoint_mgr, self.executor, self.verifier
        )

    def observe(self) -> list[Event]:
        """Execute observe operation."""
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
        """Execute record incident operation."""
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
        """Execute record plan operation."""
        event = Event(
            kind=EventKind.PLAN,
            source="planner",
            subject=plan.incident_id,
            payload=plan.to_dict(),
            severity=Severity.INFO,
        )
        self.store.append(event)
        self.reducer.reduce(event)  # F7: reducer tracks plan step count

    def record_receipt(self, receipt: Receipt) -> None:
        """Execute record receipt operation."""
        kind = EventKind.SIMULATED if receipt.simulated else EventKind.RECEIPT
        event = Event(
            kind=kind,
            source=self.verifier.name if self.verifier else "verifier",
            subject=receipt.target or "system",
            payload=receipt.to_dict(),
            severity=Severity.INFO if receipt.verified else Severity.ERROR,
        )
        self.store.append(event)
        self.reducer.reduce(event)

    def _is_simulation(self) -> bool:
        """F5/F6: Check if current executor is a simulation (noop) executor."""
        return getattr(self.executor, "is_simulation", False)

    def repair(
        self,
        incident: IncidentReport,
        dry_run: bool = False,
    ) -> list[Receipt]:
        """Execute controlled repair for a single incident.

        Flow: plan -> validate -> checkpoint -> execute steps -> verify -> record
        Safety: max_steps limit, dry-run mode, per-step verification gate.
        Returns list of receipts for all executed steps.

        P0 fixes applied:
        - F1: Verb validation via plan.validate()
        - F2: Strict plan schema
        - F3: Recovery-ready gate — checkpoint before repair, rollback on failure
        - F5: dry_run enforced at dispatch boundary (uses NoopExecutor)
        - F6: Simulated receipts never pass verification
        - F7: Composite receipt — incident only resolved when ALL steps verified
        - F8: Dedup by incident id
        - F13: Step count and timeout limits
        """
        missing = []
        if not self.planner:
            missing.append("planner")
        if not self.executor:
            missing.append("executor")
        if not self.verifier:
            missing.append("verifier")
        if missing:
            raise RuntimeError(f"Repair requires: {', '.join(missing)}")

        # F8: Deduplication — skip if already repaired or currently repairing
        if incident.id in self._completed_repairs:
            return []
        if incident.id in self._active_repairs:
            return []
        self._active_repairs.add(incident.id)

        try:
            result = self._do_repair(incident, dry_run)
            if result:  # Non-empty = repair was attempted
                self._completed_repairs.add(incident.id)
            return result
        finally:
            self._active_repairs.discard(incident.id)

    def _record_recovery(self, incident: IncidentReport, outcome: str,
                         plan: Optional[Plan] = None, **extra: Any) -> None:
        """U1: Persist the repair outcome as a RECOVERY event (durable)."""
        self.repair_outcomes[incident.id] = outcome
        payload: dict[str, Any] = {
            "incident_id": incident.id,
            "outcome": outcome,
            "plan_id": plan.id if plan else "",
        }
        payload.update(extra)
        sev = Severity.INFO if outcome in (OUTCOME_RESOLVED, OUTCOME_SIMULATED) else Severity.ERROR
        event = Event(
            kind=EventKind.RECOVERY,
            source="appliance",
            subject=incident.component or incident.id,
            payload=payload,
            severity=sev,
        )
        self.store.append(event)
        self.reducer.reduce(event)

    def _do_repair(
        self,
        incident: IncidentReport,
        dry_run: bool = False,
    ) -> list[Receipt]:
        """Internal repair implementation after dedup check.

        U1: fail-closed.  A real (non-dry-run) repair is never dispatched
        unless a pre-repair checkpoint was created *and* can be read back.
        Outcomes are recorded in self.repair_outcomes and as a durable
        RECOVERY event; a failed rollback is reported as "rollback_failed"
        rather than silently swallowed.
        """
        # Generate plan
        plan = self.planner.plan(incident)
        if not plan.steps:
            self.repair_outcomes[incident.id] = OUTCOME_NO_PLAN
            return []

        # F1/F2: Validate plan
        errors = plan.validate()
        if errors:
            plan.status = "rejected"
            self.record_plan(plan)
            self.repair_outcomes[incident.id] = OUTCOME_REJECTED
            return []

        # F13: Enforce max steps — reject over-budget plans
        if len(plan.steps) > self.max_steps:
            plan.status = "rejected_over_budget"
            self.record_plan(plan)
            self.repair_outcomes[incident.id] = OUTCOME_REJECTED
            return []

        # F3/U1: Recovery-ready gate — checkpoint BEFORE any dispatch.
        checkpoint: Optional[StateCheckpoint] = None
        if not dry_run:
            ckpt_error = ""
            try:
                state = self.reducer.state_snapshot()
                checkpoint = self._checkpoint_mgr.create(
                    state, label=f"pre_repair_{incident.id}",
                    metadata={"incident_id": incident.id, "plan_id": plan.id},
                )
                # Must be readable back, otherwise rollback is impossible.
                if self._checkpoint_mgr.load(checkpoint.id) is None:
                    ckpt_error = f"checkpoint {checkpoint.id} not readable after create"
                    checkpoint = None
            except Exception as exc:
                logger.warning("Failed to create checkpoint before repair", exc_info=True)
                ckpt_error = f"{type(exc).__name__}: {exc}"
                checkpoint = None
            if checkpoint is None:
                plan.status = "blocked_no_checkpoint"
                self.record_plan(plan)
                self._record_recovery(incident, OUTCOME_BLOCKED_NO_CHECKPOINT,
                                      plan, error=ckpt_error)
                return []

        # Link plan to incident
        incident.plan_id = plan.id
        plan.status = "approved"

        # Record the plan (F7: reducer now tracks step count)
        self.record_plan(plan)

        # F5: Determine executor — enforce dry_run at dispatch boundary
        if dry_run:
            from executor.noop_executor import NoopExecutor
            executor = NoopExecutor()
        else:
            executor = self.executor

        # Execute steps
        receipts: list[Receipt] = []
        all_verified = True

        for i, step in enumerate(plan.steps):
            receipt = executor.execute_step(step, plan, i)

            # F6: Verify — verifier handles simulated check
            expected = step.get("expected", {"exit_code": 0})
            self.verifier.verify(receipt, expected)

            self.record_receipt(receipt)
            receipts.append(receipt)

            if not receipt.verified:
                all_verified = False
                # Stop on first failure (unless simulated)
                if not receipt.simulated:
                    break

        if dry_run:
            self.repair_outcomes[incident.id] = OUTCOME_SIMULATED
            return receipts

        # F7: Mark incident resolved when ALL steps verified
        if all_verified:
            incident.resolved = True
            self._record_recovery(incident, OUTCOME_RESOLVED, plan,
                                  checkpoint_id=checkpoint.id)
            return receipts

        # F3/U1: Rollback on failure — failures are reported, not swallowed.
        rollback_error = ""
        try:
            restored = self._checkpoint_mgr.load(checkpoint.id)
            if restored is None:
                rollback_error = f"checkpoint {checkpoint.id} missing at rollback"
            else:
                self.reducer.restore_snapshot(restored.appliance_state)
        except Exception as exc:
            logger.warning("Failed to rollback after repair failure", exc_info=True)
            rollback_error = f"{type(exc).__name__}: {exc}"

        if rollback_error:
            self._record_recovery(incident, OUTCOME_ROLLBACK_FAILED, plan,
                                  checkpoint_id=checkpoint.id, error=rollback_error)
        else:
            self._record_recovery(incident, OUTCOME_ROLLED_BACK, plan,
                                  checkpoint_id=checkpoint.id)
        return receipts

    def repair_all(self, dry_run: bool = False) -> dict[str, list[Receipt]]:
        """Repair all open incidents. Returns {incident_id: [receipts]}."""
        results: dict[str, list[Receipt]] = {}
        for incident in self.open_incidents():
            receipts = self.repair(incident, dry_run=dry_run)
            results[incident.id] = receipts
        return results

    def open_incidents(self) -> list[IncidentReport]:
        """Execute open incidents operation."""
        return self.reducer.open_incidents()

    def state_snapshot(self) -> dict[str, Any]:
        """Execute state snapshot operation."""
        return self.reducer.state_snapshot()

    def event_count(self) -> int:
        """Return the number of events in the store."""
        return self.store.count()

    def close(self) -> None:
        """Execute close operation."""
        self.store.close()

    # ── M3 Recovery API ──────────────────────────────────

    def checkpoint(self, label: str = "") -> StateCheckpoint:
        """Take a state checkpoint for recovery."""
        state = self.reducer.state_snapshot()
        return self._checkpoint_mgr.create(state, label=label)

    def list_checkpoints(self) -> list[StateCheckpoint]:
        """List all checkpoints."""
        return self._checkpoint_mgr.list()

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint by id."""
        return self._checkpoint_mgr.delete(checkpoint_id)

    def prune_checkpoints(self, keep: int = 5) -> int:
        """Prune old checkpoints, keeping only the newest *keep*."""
        return self._checkpoint_mgr.prune(keep=keep)

    def restore(self, checkpoint_id: str) -> bool:
        """Restore state from a checkpoint."""
        ckpt = self._checkpoint_mgr.load(checkpoint_id)
        if ckpt:
            self.reducer.restore_snapshot(ckpt.appliance_state)
            return True
        return False

    def upgrade(self, manifest: UpgradeManifest, dry_run: bool = False) -> UpgradeResult:
        """Execute an upgrade with automatic rollback on failure."""
        state = self.reducer.state_snapshot()
        return self._upgrade_ctrl.execute(
            manifest, state, dry_run=dry_run,
            restore_fn=self.reducer.restore_snapshot,  # U2: real restore
        )
