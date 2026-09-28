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
import logging

from types import SimpleNamespace
from typing import Any

from schemas.types import Event, EventKind, IncidentReport, Severity

logger = logging.getLogger(__name__)


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
        # H2 (6986): receipts not yet applicable (plan unknown), replayed on
        # PLAN.  N5 (7024): ONE buffer keyed by receipt id, in arrival order
        # (same shape as the hive reducer), never per-plan/per-incident buckets.
        self._pending_receipts: dict[str, dict[str, Any]] = {}
        self._seen_receipt_ids: set[str] = set()
        # N6 (7075): durable plan -> owning incident (first PLAN wins),
        # independent of incident open/closed state.
        self._plan_owner: dict[str, str] = {}
        # N5 (7075): count of ambiguous legacy pending receipts discarded
        self.legacy_pending_discarded = 0
        # N6 (7133): plans whose owner a legacy snapshot could not prove; their
        # receipts are buffered and they cannot complete until a PLAN
        # re-establishes the owner.
        self._owner_unproven: set[str] = set()
        # N7 (7133): durable migration diagnostics (persisted in snapshots)
        self.migration_diagnostics: dict[str, Any] = {}
        # N6 (7133): conflicting PLAN re-registrations rejected
        self.rejected_plan_registrations = 0

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
        incident (PLAN.incident_id -> incident.plan_id), then re-examine
        EVERY pending receipt in arrival order.

        N5 (7024): a single arrival-ordered buffer, so the latest evidence per
        step index wins regardless of plan- vs incident-addressing.
        N4 (7024): every pending receipt is re-checked for identity
        contradiction after each PLAN, exactly as the hive reducer does, so
        the rejection point does not depend on unrelated incident lifecycles.
        N3 (7003): the whole eligible batch is applied first, then completion
        is decided once per touched plan.
        """
        p = event.payload or {}
        plan_id = p.get("id", "")
        steps = p.get("steps", []) or []
        if not plan_id or not steps:
            return
        inc_id = p.get("incident_id", "") or ""
        owner = self._plan_owner.get(plan_id, "")
        if inc_id and owner and owner != inc_id:
            # N6 (7133): a conflicting re-registration is rejected before ANY
            # mutation (no relink, no pending replay, no completion).
            self.rejected_plan_registrations += 1
            logger.warning("Rejecting PLAN %s -> %s: plan is owned by incident %s",
                           plan_id, inc_id, owner)
            return
        if plan_id not in self._plan_step_counts:
            self._plan_step_counts[plan_id] = len(steps)
            self._plan_verified[plan_id] = set()
            self._plan_failed_steps[plan_id] = set()
        if inc_id:
            # N6 (7075): durable plan owner, first non-empty PLAN owner wins
            self._plan_owner.setdefault(plan_id, inc_id)
            self._owner_unproven.discard(plan_id)       # N6 (7133)
            for inc in self.incidents:
                if inc.id == inc_id and not inc.plan_id:
                    inc.plan_id = plan_id
        touched = {plan_id}
        for rid, rp in list(self._pending_receipts.items()):
            got = self._handle_receipt(SimpleNamespace(payload=rp, id=rid),
                                       resolve=False)
            if got:
                touched.add(got)
        for pid in sorted(touched):
            self._maybe_resolve(pid)

    def _handle_receipt(self, event: Any, resolve: bool = True) -> str:
        """F7/N2/H2 (6986), N4/N5 (7024): same admission contract as
        hive.reducer.HiveReducer._handle_receipt.

        - no plan_id and no incident_id => resolves nothing (untargeted);
        - naming an open incident linked to a DIFFERENT plan => rejected;
        - incident-only receipt => plan of the linked open incident;
        - plan unknown (missing/late PLAN) => buffered in arrival order,
          re-examined after every PLAN (never fail-open);
        - step_index must be an int (not bool) in [0, steps);
        - latest receipt per index wins: verified adds it, a failed receipt
          marks it failed (a later verified retry of that index clears it);
        - receipt ids are applied at most once.
        Returns the effective plan id when the receipt was applied, else "".
        """
        p = dict(event.payload or {})
        rid = p.get("id") or getattr(event, "id", "") or ""
        p["id"] = rid
        if rid in self._seen_receipt_ids:
            return ""
        plan_id = p.get("plan_id", "") or ""
        inc_id = p.get("incident_id", "") or ""
        if not plan_id and not inc_id:
            self._seen_receipt_ids.add(rid)
            self._pending_receipts.pop(rid, None)
            return ""
        # N6 (7075): identity is checked against DURABLE linkage (incident
        # link in any lifecycle state + the plan's registered owner), before
        # any step progress is recorded.
        target = self._find_incident(inc_id) if inc_id else None
        if plan_id and inc_id and self._contradicts(plan_id, inc_id, target):
            self._seen_receipt_ids.add(rid)          # N4/N6: identity contradiction
            self._pending_receipts.pop(rid, None)
            return ""
        eff = plan_id or ((target.plan_id or "") if target is not None else "")
        if not plan_id and eff:
            # N6 (7133): an incident-only receipt counts toward the inferred
            # plan only if that plan's immutable owner is the named incident.
            owner = self._plan_owner.get(eff, "")
            if owner and owner != inc_id:
                self._seen_receipt_ids.add(rid)
                self._pending_receipts.pop(rid, None)
                return ""
        if (not eff or eff not in self._plan_step_counts
                or eff in self._owner_unproven):
            self._pending_receipts.setdefault(rid, p)
            return ""
        self._seen_receipt_ids.add(rid)
        self._pending_receipts.pop(rid, None)
        idx = p.get("step_index")
        if _valid_index(idx, self._plan_step_counts[eff]):
            if p.get("verified") is True:
                self._plan_verified[eff].add(idx)
                self._plan_failed_steps[eff].discard(idx)
            else:
                self._plan_failed_steps[eff].add(idx)
                self._plan_verified[eff].discard(idx)
        if resolve:
            self._maybe_resolve(eff)
        return eff

    def _find_incident(self, inc_id: str):
        return next((i for i in self.incidents if i.id == inc_id), None)

    def _contradicts(self, plan_id: str, inc_id: str, target: Any) -> bool:
        """N6 (7075): a dual-addressed receipt is contradictory if the named
        incident is (durably) linked to another plan, or the plan's declared
        owner is a different incident.  Lifecycle state is irrelevant."""
        owner = self._plan_owner.get(plan_id, "")
        if owner:
            # N6 (7133): the immutable owner decides (a plan may be a retry for
            # an incident already linked to an earlier plan).
            return owner != inc_id
        return bool(target is not None and target.plan_id
                    and target.plan_id != plan_id)

    def _open_incident(self, inc_id: str):
        return next((i for i in self.incidents
                     if i.id == inc_id and not i.resolved), None)

    def _maybe_resolve(self, plan_id: str) -> None:
        n = self._plan_step_counts.get(plan_id, 0)
        if not n or self._plan_failed_steps.get(plan_id):
            return
        if len(self._plan_verified.get(plan_id, ())) != n:
            return
        if plan_id in self._owner_unproven:
            return
        owner = self._plan_owner.get(plan_id, "")
        for inc in self.incidents:
            # N6 (7133): the immutable owner is the sole completion authority;
            # a plan with no declared owner may only close incidents linked to it.
            if (inc.id == owner) if owner else (inc.plan_id == plan_id):
                if not inc.plan_id:
                    inc.plan_id = plan_id
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
            # N5: arrival-ordered list of pending receipt payloads
            "pending_receipts": [copy.deepcopy(v) for v in self._pending_receipts.values()],
            "seen_receipt_ids": sorted(self._seen_receipt_ids),
            "plan_owner": dict(self._plan_owner),
            "pending_format": "arrival-v1",
            "owner_unproven": sorted(self._owner_unproven),
            "migration_diagnostics": copy.deepcopy(self.migration_diagnostics),
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
        raw = snapshot.get("pending_receipts", []) or []
        self.legacy_pending_discarded = 0
        if isinstance(raw, dict):
            # N5 (7075): the legacy (7003) bucketed format {bucket: {rid: payload}}
            # cannot recover the original arrival interleaving (streams with
            # opposite latest outcomes yield byte-identical snapshots), so this
            # ambiguous pending evidence is DISCARDED (fail closed): affected
            # steps must be re-proven by fresh receipts.
            self.legacy_pending_discarded = sum(
                len(b) if isinstance(b, dict) else 1 for b in raw.values())
            raw = []
            if self.legacy_pending_discarded:
                logger.warning("Legacy bucketed pending snapshot: discarded %d "
                               "pending receipt(s); affected steps need fresh "
                               "receipts", self.legacy_pending_discarded)
        self._pending_receipts = {}
        for rp in raw:
            rp = copy.deepcopy(rp)
            self._pending_receipts.setdefault(rp.get("id", "") or "", rp)
        self._seen_receipt_ids = set(snapshot.get("seen_receipt_ids", []))
        discarded_now = self.legacy_pending_discarded
        diag = copy.deepcopy(snapshot.get("migration_diagnostics") or {})
        self._plan_owner = dict(snapshot.get("plan_owner", {}) or {})
        self._owner_unproven = set(snapshot.get("owner_unproven", []) or [])
        if "plan_owner" not in snapshot:
            # N6 (7133): pre-owner snapshot.  An owner is rebuilt ONLY from an
            # unambiguous durable link (exactly one incident linked to the
            # plan).  Plans with no link (PLAN-before-INCIDENT) or conflicting
            # links are quarantined: previously admitted progress cannot be
            # revalidated, so it is dropped, receipts are buffered, and the
            # plan cannot complete until a PLAN re-establishes its owner.
            links: dict[str, set[str]] = {}
            for inc in incidents:
                if inc.plan_id:
                    links.setdefault(inc.plan_id, set()).add(inc.id)
            for pid, ids in links.items():
                if len(ids) == 1:
                    self._plan_owner[pid] = next(iter(ids))
            dropped = 0
            for pid in sorted(self._plan_step_counts):
                if pid in self._plan_owner:
                    continue
                self._owner_unproven.add(pid)
                dropped += len(self._plan_verified.get(pid, ()))
                self._plan_verified[pid] = set()
            if self._owner_unproven:
                diag["legacy_ownerless_plans"] = sorted(
                    set(diag.get("legacy_ownerless_plans", [])) | self._owner_unproven)
                diag["legacy_verified_discarded"] = int(
                    diag.get("legacy_verified_discarded", 0)) + dropped
                logger.warning("Legacy snapshot without plan owners: plans %s "
                               "quarantined (%d verified step(s) discarded) until "
                               "a PLAN re-establishes the owner",
                               sorted(self._owner_unproven), dropped)
        if discarded_now:
            diag["legacy_pending_discarded"] = int(
                diag.get("legacy_pending_discarded", 0)) + discarded_now
        if diag:
            diag.setdefault("recovery", "Discarded legacy evidence is not replayed; "
                            "affected plan steps must be re-proven by fresh, "
                            "uniquely identified receipts.")
        # N7 (7133): persisted + cumulative across later snapshot/restore
        self.migration_diagnostics = diag
        self.legacy_pending_discarded = int(diag.get("legacy_pending_discarded", 0))

    def state_snapshot(self) -> dict[str, Any]:
        """Alias for snapshot() for API compatibility."""
        return self.snapshot()
