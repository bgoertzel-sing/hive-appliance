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
import copy

from typing import Any

from schemas.types import Event, EventKind, IncidentReport, Severity


# N4 (7003): buffer key for incident-only receipts whose plan is not yet known
_INC_KEY = "@inc:"


def _valid_index(idx: Any, count: int) -> bool:
    """N2/H2 (6986): a step index must be a real int (not bool) in range."""
    return isinstance(idx, int) and not isinstance(idx, bool) and 0 <= idx < count


class Reducer:
    """Processes events and reduces them into state/decisions."""

    def __init__(self):
        self.incidents: list[IncidentReport] = []
        self.state: dict[str, Any] = {}
        # F10: Track seen incident IDs for dedup
        self._seen_incident_ids: set[str] = set()
        # F7: Track plan receipts for composite verification
        self._plan_step_counts: dict[str, int] = {}
        # N2 (6986): distinct verified / failed step indices per plan
        self._plan_verified: dict[str, set[int]] = {}
        self._plan_failed_steps: dict[str, set[int]] = {}
        # H2 (6986): receipts that arrived before their PLAN, replayed on PLAN
        self._pending_receipts: dict[str, dict[str, dict[str, Any]]] = {}
        self._seen_receipt_ids: set[str] = set()

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

        # Update state with latest observation.
        # U1: RECOVERY events are audit records of repair outcomes; they must
        # not be merged into component state (otherwise a post-rollback
        # outcome record would re-mutate the just-restored state).
        if event.subject and event.kind != EventKind.RECOVERY:
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
        """F7/N1 (6986): register the plan's step count, link it to its
        incident (PLAN.incident_id -> incident.plan_id), then replay any
        receipts that arrived before the plan."""
        p = event.payload or {}
        plan_id = p.get("id", "")
        steps = p.get("steps", []) or []
        if not plan_id or not steps:
            return
        if plan_id not in self._plan_step_counts:
            self._plan_step_counts[plan_id] = len(steps)
            self._plan_verified[plan_id] = set()
            self._plan_failed_steps[plan_id] = set()
        inc_id = p.get("incident_id", "")
        if inc_id:
            for inc in self.incidents:
                if inc.id == inc_id and not inc.plan_id:
                    inc.plan_id = plan_id
        # N3: apply the entire buffer, THEN decide completion once.
        batch = list(self._pending_receipts.pop(plan_id, {}).items())
        if inc_id:
            t = self._open_incident(inc_id)
            if t is not None and t.plan_id == plan_id:
                batch += [(rid, dict(rp, plan_id=plan_id)) for rid, rp in
                          self._pending_receipts.pop(_INC_KEY + inc_id, {}).items()]
        for rid, rp in batch:
            self._apply_receipt(plan_id, rp)
        self._maybe_resolve(plan_id)

    def _handle_receipt(self, event: Event) -> None:
        """F7/N2/H2 (6986): composite completion by DISTINCT step index.

        - no plan_id => resolves nothing (untargeted);
        - plan not yet registered => buffered (never fail-open), replayed
          when the PLAN arrives;
        - step_index must be an int (not bool) in [0, steps);
        - latest receipt per index wins: verified adds it, a failed receipt
          marks it failed (a later verified retry of that index clears it);
        - the incident resolves only when every index is verified and none
          is currently failed.
        """
        p = dict(event.payload or {})
        rid = p.get("id") or getattr(event, "id", "") or ""
        p["id"] = rid
        if rid in self._seen_receipt_ids:
            return
        plan_id = p.get("plan_id", "") or ""
        inc_id = p.get("incident_id", "") or ""
        if not plan_id and not inc_id:
            self._seen_receipt_ids.add(rid)          # untargeted: resolves nothing
            return
        if self._contradicts(p, plan_id):
            self._seen_receipt_ids.add(rid)          # N4: identity contradiction
            return
        if not plan_id:
            # N4: incident-only receipt -> plan of the linked open incident
            target = self._open_incident(inc_id)
            plan_id = (target.plan_id or "") if target is not None else ""
            if not plan_id:
                self._pending_receipts.setdefault(_INC_KEY + inc_id, {}).setdefault(rid, p)
                return
        if plan_id not in self._plan_step_counts:
            self._pending_receipts.setdefault(plan_id, {}).setdefault(rid, p)
            return
        self._apply_receipt(plan_id, p)
        self._maybe_resolve(plan_id)

    def _apply_receipt(self, plan_id: str, p: dict[str, Any]) -> None:
        rid = p.get("id", "")
        if rid in self._seen_receipt_ids:
            return
        self._seen_receipt_ids.add(rid)
        if self._contradicts(p, plan_id):
            return
        idx = p.get("step_index")
        if not _valid_index(idx, self._plan_step_counts[plan_id]):
            return
        if p.get("verified") is True:
            self._plan_verified[plan_id].add(idx)
            self._plan_failed_steps[plan_id].discard(idx)
        else:
            self._plan_failed_steps[plan_id].add(idx)
            self._plan_verified[plan_id].discard(idx)

    def _open_incident(self, inc_id: str):
        return next((i for i in self.incidents
                     if i.id == inc_id and not i.resolved), None)

    def _contradicts(self, p: dict[str, Any], plan_id: str) -> bool:
        """N4 (7003): same identity contract as the hive reducer -- a receipt
        naming an open incident that is linked to a DIFFERENT plan is
        rejected and counts for nothing."""
        inc_id = p.get("incident_id", "") or ""
        if not inc_id or not plan_id:
            return False
        t = self._open_incident(inc_id)
        return t is not None and bool(t.plan_id) and t.plan_id != plan_id

    def _maybe_resolve(self, plan_id: str) -> None:
        n = self._plan_step_counts.get(plan_id, 0)
        if not n or self._plan_failed_steps.get(plan_id):
            return
        if len(self._plan_verified.get(plan_id, ())) != n:
            return
        for inc in self.incidents:
            if inc.plan_id == plan_id:
                inc.resolved = True

    def open_incidents(self) -> list[IncidentReport]:
        """Execute open incidents operation."""
        return [i for i in self.incidents if not i.resolved]

    def snapshot(self) -> dict[str, Any]:
        """Return a snapshot of the current state.

        U3: includes the full incident records (and composite-receipt
        tracking) so that restore_snapshot() round-trips them.
        """
        import copy
        return {
            "state": copy.deepcopy(self.state),
            "incidents": [i.to_dict() for i in self.incidents],
            "plan_step_counts": dict(self._plan_step_counts),
            # N2: plan_receipts = sorted distinct VERIFIED step indices
            "plan_receipts": {k: sorted(v) for k, v in self._plan_verified.items()},
            "plan_failed_steps": {k: sorted(v) for k, v in self._plan_failed_steps.items()},
            "pending_receipts": copy.deepcopy(self._pending_receipts),
            "seen_receipt_ids": sorted(self._seen_receipt_ids),
            "incidents_total": len(self.incidents),
            "incidents_open": len(self.open_incidents()),
        }

    def restore_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Restore reducer state from a checkpoint snapshot.

        U3: incident records, the seen-id dedup set and plan tracking are
        rebuilt from the snapshot.  A snapshot that reports incidents but
        carries no records (legacy/corrupt) raises ValueError instead of
        silently dropping them; nothing is mutated in that case.
        """
        import copy
        records = snapshot.get("incidents")
        if records is None:
            if snapshot.get("incidents_total", 0):
                raise ValueError(
                    "snapshot has incidents_total>0 but no incident records; "
                    "refusing lossy restore"
                )
            records = []
        incidents = [IncidentReport.from_dict(r) for r in records]
        self.state = copy.deepcopy(snapshot.get("state", {}))
        self.incidents = incidents
        self._seen_incident_ids = {i.id for i in incidents}
        self._plan_step_counts = dict(snapshot.get("plan_step_counts", {}))
        # N2: legacy bool lists carry no step identity and are dropped
        # (fail closed: completion must be re-proven).
        self._plan_verified = {
            k: {i for i in v if _valid_index(i, self._plan_step_counts.get(k, 0))}
            for k, v in snapshot.get("plan_receipts", {}).items()}
        for k in self._plan_step_counts:
            self._plan_verified.setdefault(k, set())
        self._plan_failed_steps = {k: set(v) for k, v in
                                   snapshot.get("plan_failed_steps", {}).items()}
        for k in self._plan_step_counts:
            self._plan_failed_steps.setdefault(k, set())
        self._pending_receipts = copy.deepcopy(snapshot.get("pending_receipts", {}))
        self._seen_receipt_ids = set(snapshot.get("seen_receipt_ids", []))

    def state_snapshot(self) -> dict[str, Any]:
        """Alias for snapshot() for API compatibility."""
        return self.snapshot()
