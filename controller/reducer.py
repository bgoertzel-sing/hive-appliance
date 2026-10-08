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

# N10 (7160): global bound for historical migration diagnostics lists/maps
MAX_DIAG_ENTRIES = 256
# N9 (7173): per-kind receipt ids retained in a rebind audit record
MAX_EFFECT_IDS = 32
EFFECT_KINDS = ("credited", "failure_recorded", "consumed_no_effect", "still_held")


def _as_int(x: Any) -> int:
    if isinstance(x, bool):
        return 0
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0

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
        # receipts are buffered and they cannot complete until a trusted
        # operator calls rebind_plan_owner() (N6 7146 / N9 7160).
        self._owner_unproven: set[str] = set()
        # N7 (7133): durable migration diagnostics (persisted in snapshots)
        self.migration_diagnostics: dict[str, Any] = {}
        # N6 (7133): conflicting PLAN re-registrations rejected
        self.rejected_plan_registrations = 0
        # F-foreign-progress (Astra 7582): incident named by the receipt that
        # last set each step's verified/failed state ('' = plan-only receipt).
        # A rebind keeps only steps whose evidence named '' or the NEW owner.
        self._plan_step_src: dict[str, dict[int, str]] = {}
        # F-hold-expiry (Astra 7582): plans ever held as ownerless_linked; they
        # get an owner ONLY via the audited rebind_plan_owner().
        self._held_ownerless: set[str] = set()
        self._quiet = False   # preview simulations log at debug level

    def reduce(self, event: Event) -> list[IncidentReport]:
        """Process an event, update state, and return any new incidents."""
        new_incidents: list[IncidentReport] = []
        # N6 (7146): a conflicting PLAN re-registration is rejected before ANY
        # reducer mutation, including the component-state merge below.
        if event.kind == EventKind.PLAN and self._reject_conflicting_plan(event.payload or {}):
            return new_incidents

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

        self._latch_holds()   # F-hold-expiry (Astra 7582)
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
            # N8 (7146): a late INCIDENT is linked to the plan it owns and all
            # eligible pending evidence is drained before any completion.
            owned = self._owned_plans(incident.id)
            if not incident.plan_id and len(owned) == 1:
                incident.plan_id = owned[0]
            # H2 (7160): re-check completion of every plan this incident OWNS,
            # so a late INCIDENT after all successes closes without waiting for
            # another trigger.  A mere payload link to an ownerless plan does
            # not (old evidence must not auto-close a newly reported incident).
            self._drain_pending(set(owned))
            # Late-link (Astra 7562): linking to an already complete OWNERLESS
            # plan emits the same WARNING as the in-order case.  For an
            # ownerless plan _maybe_resolve only logs; it closes nothing.
            lp = incident.plan_id
            if (lp and lp in self._plan_step_counts
                    and lp not in self._owner_unproven
                    and not self._plan_owner.get(lp)):
                self._maybe_resolve(lp)

    def _owned_plans(self, inc_id: str) -> list[str]:
        return sorted(p for p, o in self._plan_owner.items() if o == inc_id)

    def _reject_conflicting_plan(self, p: dict) -> bool:
        plan_id = p.get("id", "") or ""
        inc_id = p.get("incident_id", "") or ""
        owner = self._plan_owner.get(plan_id, "") if plan_id else ""
        if inc_id and owner and owner != inc_id:
            self.rejected_plan_registrations += 1
            logger.warning("Rejecting PLAN %s -> %s: plan is owned by incident %s",
                           plan_id, inc_id, owner)
            return True
        return False

    def _drain_pending(self, touched: set, outcome: Any = None) -> None:
        """Apply every newly eligible pending receipt (arrival order), THEN
        decide completion once per touched plan (N3/N8).

        N9 (7173): when outcome is a dict, the effect on EVERY buffered
        receipt is recorded from the actual before/after state
        (credited / failure_recorded / consumed_no_effect / still_held)."""
        touched = set(touched)
        for rid, rp in list(self._pending_receipts.items()):
            if outcome is not None:
                v0 = {k: frozenset(v) for k, v in self._plan_verified.items()}
                f0 = {k: frozenset(v) for k, v in self._plan_failed_steps.items()}
            got = self._handle_receipt(SimpleNamespace(payload=rp, id=rid),
                                       resolve=False)
            if got:
                touched.add(got)
            if outcome is not None:
                outcome[rid] = self._receipt_effect(rid, rp, got, v0, f0)
        for pid in sorted(touched):
            self._maybe_resolve(pid)

    def _receipt_effect(self, rid: str, rp: dict, got: str, v0: dict,
                        f0: dict) -> dict[str, Any]:
        rec = {"id": rid,
               "plan_id": copy.deepcopy(rp.get("plan_id") or ""),
               "incident_id": copy.deepcopy(rp.get("incident_id") or ""),
               "step_index": copy.deepcopy(rp.get("step_index")),
               "verified": copy.deepcopy(rp.get("verified")),
               "applied_to": got or ""}
        if rid in self._pending_receipts:
            rec["outcome"] = "still_held"
            return rec
        grew = lost = failed = False
        for k in set(v0) | set(self._plan_verified):
            a, b = v0.get(k, frozenset()), set(self._plan_verified.get(k, ()))
            grew = grew or bool(b - a)
            lost = lost or bool(a - b)
        for k in set(f0) | set(self._plan_failed_steps):
            a, b = f0.get(k, frozenset()), set(self._plan_failed_steps.get(k, ()))
            failed = failed or bool(b - a)
        rec["outcome"] = ("credited" if grew else
                          "failure_recorded" if (failed or lost) else
                          "consumed_no_effect")
        return rec

    @staticmethod
    def _group_effects(outcome: dict) -> dict[str, list]:
        groups: dict[str, list] = {k: [] for k in EFFECT_KINDS}
        for rec in outcome.values():
            groups[rec["outcome"]].append(rec)
        return groups

    def _pending_blocks(self, plan_id: str, owner: str) -> bool:
        """N8 (7146): completion is refused while any pending receipt still
        addresses the plan or its owner/linked incident."""
        linked = {i.id for i in self.incidents if i.plan_id == plan_id}
        if owner:
            linked.add(owner)
        for rp in self._pending_receipts.values():
            pid = rp.get("plan_id") or ""
            if pid == plan_id or (not pid and (rp.get("incident_id") or "") in linked):
                return True
        return False

    def _rebind_check(self, plan_id: str, incident_id: str,
                      allow_non_candidate: bool):
        if (plan_id not in self._owner_unproven
                and not self._ownerless_linked(plan_id)
                and not self._held_latched(plan_id)):
            return False, "plan is not quarantined", None
        if not incident_id:
            return False, "no target incident", None
        inc = self._find_incident(incident_id)
        if inc is None:
            return False, "unknown target incident", None
        if inc.resolved:
            return False, "target incident is already resolved", inc
        if inc.plan_id and inc.plan_id != plan_id:
            return False, "target incident is linked to another plan", inc
        cands = (self.migration_diagnostics.get("owner_candidates") or {}).get(plan_id, [])
        if incident_id not in cands and not allow_non_candidate:
            return False, "target is not a recorded owner candidate", inc
        return True, "", inc

    def _apply_rebind(self, plan_id: str, incident_id: str, inc: Any,
                      outcome: Any = None) -> list[int]:
        # F-foreign-progress (Astra 7582): evidence that named another
        # incident never counts for the new owner (re-prove those steps).
        foreign = self._discard_foreign_steps(plan_id, incident_id)
        self._held_ownerless.discard(plan_id)
        self._owner_unproven.discard(plan_id)
        self._plan_owner[plan_id] = incident_id
        if not inc.plan_id:
            inc.plan_id = plan_id
        (self.migration_diagnostics.get("owner_candidates") or {}).pop(plan_id, None)
        self._drain_pending({plan_id}, outcome)
        return foreign

    def _discard_foreign_steps(self, plan_id: str, incident_id: str) -> list[int]:
        src = self._plan_step_src.get(plan_id, {})
        steps = (set(self._plan_verified.get(plan_id, ()))
                 | set(self._plan_failed_steps.get(plan_id, ())))
        # unknown provenance (pre-7582 snapshot) is treated as foreign
        foreign = sorted(i for i in steps if src.get(i) not in ("", incident_id))
        for i in foreign:
            self._plan_verified.get(plan_id, set()).discard(i)
            self._plan_failed_steps.get(plan_id, set()).discard(i)
            src.pop(i, None)
        if foreign:
            (logger.debug if self._quiet else logger.warning)(
                "Rebind of plan %s -> %s discarded step evidence %s that did "
                "not name the new owner; those steps must be re-proven",
                plan_id, incident_id, foreign)
        return foreign

    def preview_rebind(self, plan_id: str, incident_id: str,
                       allow_non_candidate: bool = False) -> dict[str, Any]:
        """N9 (7160/7173): side-effect-free preview of rebind_plan_owner().

        Returns whether it is allowed (and why not), recorded candidates,
        held_receipts (buffered receipts that directly name the plan or the
        target) and, derived from a simulated rebind on a deep copy, effects:
        EVERY buffered receipt grouped by what the rebind would do to it
        (credited / failure_recorded / consumed_no_effect / still_held),
        effect_counts and would_close.  The whole result is deep-copied, so
        it never aliases live reducer state."""
        ok, why, _ = self._rebind_check(plan_id, incident_id, allow_non_candidate)
        cands = list((self.migration_diagnostics.get("owner_candidates") or {}).get(plan_id, []))
        held = []
        for rid, rp in self._pending_receipts.items():
            pid = rp.get("plan_id") or ""
            if pid == plan_id or (not pid and (rp.get("incident_id") or "") == incident_id):
                held.append({"id": rid, "plan_id": pid,
                             "incident_id": rp.get("incident_id") or "",
                             "step_index": rp.get("step_index"),
                             "verified": rp.get("verified")})
        would_close: list[str] = []
        effects: dict[str, list] = {k: [] for k in EFFECT_KINDS}
        foreign: list[int] = []
        if ok:
            sim = copy.deepcopy(self)
            sim._quiet = True
            before = {i.id for i in sim.open_incidents()}
            out: dict[str, Any] = {}
            foreign = sim._apply_rebind(plan_id, incident_id,
                                        sim._find_incident(incident_id), out)
            would_close = sorted(before - {i.id for i in sim.open_incidents()})
            effects = self._group_effects(out)
        return copy.deepcopy({
            "plan_id": plan_id, "incident_id": incident_id, "allowed": ok,
            "hold_reason": self.quarantine_reasons().get(plan_id, ""),
            "refusal": why, "candidates": cands,
            "is_candidate": incident_id in cands, "held_receipts": held,
            "effects": effects,
            "effect_counts": {k: len(v) for k, v in effects.items()},
            "foreign_steps_discarded": foreign,
            "would_close": would_close})

    def rebind_plan_owner(self, plan_id: str, incident_id: str, *, actor: str,
                          reason: str, allow_non_candidate: bool = False) -> bool:
        """N6 (7146) / N9 (7160, 7173): explicit TRUSTED-OPERATOR owner rebind
        for a HELD plan: quarantined by legacy migration (owner_unproven) or
        a registered ownerless plan linked to an open incident
        (ownerless_linked; Ben msg 7547 option (a), Astra 7562).

        This is an authority override, not proof of lost history: the caller
        supplies the ownership evidence.  Never expose it as an ordinary event
        or an unauthenticated endpoint.  Requirements:
          - non-empty actor and reason (recorded in owner_rebinds);
          - the plan is quarantined; the target exists, is OPEN, and is not
            linked to another plan;
          - the target is a recorded owner candidate (proposed by a PLAN after
            migration) unless allow_non_candidate=True is passed deliberately.
        Call preview_rebind() first to see held evidence and what would close.
        The audit record accounts for EVERY buffered receipt the rebind
        drained, from the actual before/after state: pending_before,
        effect_counts and bounded effect_ids per kind.
        Returns True if applied.
        """
        if not (isinstance(actor, str) and actor.strip()):
            raise ValueError("rebind_plan_owner requires a non-empty actor")
        if not (isinstance(reason, str) and reason.strip()):
            raise ValueError("rebind_plan_owner requires a non-empty reason")
        ok, why, inc = self._rebind_check(plan_id, incident_id, allow_non_candidate)
        if not ok:
            logger.warning("Refused rebind of plan %s -> %s by %s: %s",
                           plan_id, incident_id, actor, why)
            return False
        cands = (self.migration_diagnostics.get("owner_candidates") or {}).get(plan_id, [])
        is_cand = incident_id in cands
        hold = self.quarantine_reasons().get(plan_id, "ownerless_linked")
        before = {i.id for i in self.open_incidents()}
        out: dict[str, Any] = {}
        foreign = self._apply_rebind(plan_id, incident_id, inc, out)
        closed = sorted(before - {i.id for i in self.open_incidents()})
        eff = self._group_effects(out)
        counts = {k: len(v) for k, v in eff.items()}
        d = self.migration_diagnostics
        recs = d.setdefault("owner_rebinds", [])
        d["owner_rebinds_total"] = _as_int(d.get("owner_rebinds_total", len(recs))) + 1
        recs.append({"plan_id": plan_id, "incident_id": incident_id,
                     "actor": actor, "reason": reason, "candidate": is_cand,
                     "hold_reason": hold,
                     "pending_before": len(out), "effect_counts": counts,
                     "effect_ids": {k: [str(r["id"]) for r in v][:MAX_EFFECT_IDS]
                                    for k, v in eff.items()},
                     "closed": closed,
                     "foreign_steps_discarded": foreign[:MAX_EFFECT_IDS]})
        del recs[:-MAX_DIAG_ENTRIES]
        logger.warning("Operator rebind by %s (%s): plan %s [%s] owner set to "
                       "incident %s (candidate=%s, pending_before=%d, effects=%s, "
                       "closed=%s)", actor, reason, plan_id, hold, incident_id,
                       is_cand, len(out), counts, closed)
        return True

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
        if self._reject_conflicting_plan(p):
            return
        held = ("owner unproven after legacy migration"
                if plan_id in self._owner_unproven else
                "ownerless plan linked to an open incident"
                if self._ownerless_linked(plan_id) else
                "previously held ownerless plan (owner only via audited rebind)"
                if self._held_latched(plan_id) else "")
        if inc_id and held:
            # N6 (7146) / Ben msg 7547 option (a) (Astra 7562): an ordinary
            # PLAN never sets the owner of a HELD plan; it is only recorded
            # as a candidate for a previewed, audited operator rebind.
            d = self.migration_diagnostics
            cmap = d.setdefault("owner_candidates", {})
            if plan_id not in cmap and len(cmap) >= MAX_DIAG_ENTRIES:
                d["owner_candidates_dropped"] = int(d.get("owner_candidates_dropped", 0)) + 1
            else:
                lst = cmap.setdefault(plan_id, [])
                if inc_id not in lst and len(lst) < 8:
                    lst.append(inc_id)
            logger.warning("PLAN %s -> %s held (%s): recorded as owner "
                           "candidate only; use preview_rebind() then "
                           "rebind_plan_owner()", plan_id, inc_id, held)
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
        self._drain_pending({plan_id})

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
        if not eff and inc_id:
            # N8 (7146): incident-only receipt for a not-yet-linked incident
            # counts toward the unique plan that incident owns.
            owned = self._owned_plans(inc_id)
            if len(owned) == 1:
                eff = owned[0]
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
            # F-foreign-progress (Astra 7582): remember whose evidence it is
            self._plan_step_src.setdefault(eff, {})[idx] = inc_id
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
        """Close the owning incident when plan_id is fully verified.

        MULTI-PLAN POLICY (decided by Ben Goertzel, 2026-10-06; see
        docs/POLICY_MULTI_PLAN_SUPERSESSION.md): an incident may own several
        repair plans.  ANY one of them that completes (every step verified, no
        failed step, owner proven, no blocking pending evidence) closes the
        incident, even if a sibling plan for the same incident failed.  No
        newest-plan selection and no explicit supersedes relation is required;
        a sibling failure before or after the closure never blocks or reopens
        it.  Only plans OWNED by the incident can close it.
        """
        n = self._plan_step_counts.get(plan_id, 0)
        if not n or self._plan_failed_steps.get(plan_id):
            return
        if len(self._plan_verified.get(plan_id, ())) != n:
            return
        if plan_id in self._owner_unproven:
            return
        owner = self._plan_owner.get(plan_id, "")
        if self._pending_blocks(plan_id, owner):
            return
        # P3-ownerless (Astra 7519): the immutable owner is the SOLE
        # completion authority.  A plan with no proven owner (e.g. PLAN with an
        # empty incident_id) never closes anything, not even incidents that
        # link to it via inc.plan_id -- linkage alone is not ownership.
        if not owner:
            # Ben msg 7547 option (a) (Astra 7562): the stuck plan is HELD
            # in quarantined_plans() and repaired by audited rebind.
            linked = sorted(i.id for i in self.incidents
                            if not i.resolved and i.plan_id == plan_id)
            if linked:
                logger.warning(
                    "Plan %s is complete but has no proven owner; it closes "
                    "nothing (linked open incidents %s stay open). It is HELD "
                    "in quarantined_plans() (ownerless_linked); repair with "
                    "preview_rebind()/rebind_plan_owner() for %s. A re-sent "
                    "PLAN only records an owner candidate.", plan_id, linked,
                    plan_id)
            return
        for inc in self.incidents:
            if inc.id == owner:
                if not inc.plan_id:
                    inc.plan_id = plan_id
                inc.resolved = True

    def quarantined_plans(self) -> list[str]:
        """Authoritative CURRENT hold list, sorted: every plan awaiting an
        operator preview_rebind()/rebind_plan_owner() -- owner_unproven
        (legacy migration) AND ownerless_linked (Ben msg 7547 option (a),
        Astra 7562).  Use this, not migration_diagnostics
        ["legacy_ownerless_plans"] (a capped historical sample)."""
        return sorted(self.quarantine_reasons())

    def _ownerless_linked(self, plan_id: str) -> bool:
        return (bool(plan_id) and plan_id in self._plan_step_counts
                and plan_id not in self._owner_unproven
                and not self._plan_owner.get(plan_id)
                and any(not i.resolved and i.plan_id == plan_id
                        for i in self.incidents))

    def _held_latched(self, plan_id: str) -> bool:
        return (plan_id in self._held_ownerless
                and plan_id in self._plan_step_counts
                and not self._plan_owner.get(plan_id))

    def _latch_holds(self) -> None:
        """F-hold-expiry (Astra 7582): remember every plan currently held as
        ownerless_linked so it stays held (ownerless_held) after its linked
        incidents are resolved by other means."""
        for inc in self.incidents:
            pid = inc.plan_id
            if (not inc.resolved and pid and pid not in self._held_ownerless
                    and self._ownerless_linked(pid)):
                self._held_ownerless.add(pid)

    def quarantine_reasons(self) -> dict[str, str]:
        """Held plans (same keys as quarantined_plans()) with their reason.

        NOT every plan that cannot close an incident: owned-but-incomplete or
        failed plans are intentionally absent.  Result is a derived view with
        no global size cap (Astra 7562 O-bound, Low): one entry per held plan.

        - ``owner_unproven``: owner lost in legacy migration.
        - ``ownerless_linked`` (Ben msg 7547 option (a), Astra 7562): a
          registered plan with NO owner that an open incident links to via
          plan_id.  Linkage is never treated as ownership.  A re-sent PLAN
          declaring incident_id only records an owner candidate.
        - ``ownerless_held`` (Astra 7582 F-hold-expiry): a plan that WAS held
          ownerless_linked and still has no owner, even after its linked
          incidents were resolved some other way.

        Both are repaired the same way: preview_rebind() then the audited
        rebind_plan_owner().  Derived from durable state, so it survives
        snapshot/restore.
        """
        out = {pid: "owner_unproven" for pid in self._owner_unproven}
        for inc in self.incidents:
            pid = inc.plan_id
            if (not inc.resolved and pid and pid not in out
                    and pid in self._plan_step_counts
                    and not self._plan_owner.get(pid)):
                out[pid] = "ownerless_linked"
        for pid in self._held_ownerless:
            if pid not in out and self._held_latched(pid):
                out[pid] = "ownerless_held"
        return dict(sorted(out.items()))

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
            # Astra 7582: step provenance + hold latch survive restore
            "plan_step_src": {k: {str(i): v2 for i, v2 in v.items()}
                              for k, v in self._plan_step_src.items()},
            "held_ownerless": sorted(self._held_ownerless),
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
        legacy_payloads: list[Any] = []
        if isinstance(raw, dict):
            # N5 (7075): the legacy (7003) bucketed format {bucket: {rid: payload}}
            # cannot recover the original arrival interleaving (streams with
            # opposite latest outcomes yield byte-identical snapshots), so this
            # ambiguous pending evidence is DISCARDED (fail closed): affected
            # steps must be re-proven by fresh receipts.
            self.legacy_pending_discarded = sum(
                len(b) if isinstance(b, dict) else 1 for b in raw.values())
            legacy_payloads = [x for b in raw.values()
                               for x in (b.values() if isinstance(b, dict) else [b])]
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
        self._held_ownerless = set(snapshot.get("held_ownerless", []) or [])
        self._plan_step_src = {}
        for k, v in (snapshot.get("plan_step_src") or {}).items():
            if isinstance(v, dict):
                self._plan_step_src[k] = {int(i): str(s2) for i, s2 in v.items()
                                          if str(i).isdigit()}
        self._latch_holds()
        if "plan_owner" not in snapshot:
            # N6 (7133): pre-owner snapshot.  An owner is rebuilt ONLY from an
            # unambiguous durable link (exactly one incident linked to the
            # plan).  Plans with no link (PLAN-before-INCIDENT) or conflicting
            # links are quarantined: previously admitted progress cannot be
            # revalidated, so it is dropped, receipts are buffered, and the
            # plan cannot complete until an operator rebind_plan_owner().
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
                # N10 (7160): bounded history + total; the actionable current
                # quarantine is persisted separately as owner_unproven.
                prev = list(diag.get("legacy_ownerless_plans", []) or [])
                new = sorted(self._owner_unproven - set(prev))
                diag["legacy_ownerless_total"] = int(
                    diag.get("legacy_ownerless_total", len(prev))) + len(new)
                diag["legacy_ownerless_plans"] = (prev + new)[:MAX_DIAG_ENTRIES]
                diag["legacy_verified_discarded"] = int(
                    diag.get("legacy_verified_discarded", 0)) + dropped
                logger.warning("Legacy snapshot without plan owners: plans %s "
                               "quarantined (%d verified step(s) discarded) until "
                               "an operator calls rebind_plan_owner()",
                               sorted(self._owner_unproven), dropped)
        # N5 (7146): successes that discarded pending evidence could have
        # superseded are invalidated, INDEPENDENT of owner reconstruction.
        invalidated = 0
        for rp in legacy_payloads:
            rp = rp if isinstance(rp, dict) else {}
            pid = rp.get("plan_id") or ""
            iid = rp.get("incident_id") or ""
            if pid:
                affected = {pid}
            elif iid:
                affected = ({i.plan_id for i in incidents if i.id == iid and i.plan_id}
                            | {p for p, o in self._plan_owner.items() if o == iid})
                if not affected:
                    affected = set(self._plan_verified)   # cannot tell: all
            elif rp:
                affected = set()                          # untargeted
            else:
                affected = set(self._plan_verified)
            idx = rp.get("step_index")
            for p in affected:
                v = self._plan_verified.get(p)
                if not v:
                    continue
                if isinstance(idx, int) and not isinstance(idx, bool):
                    if idx in v:
                        v.discard(idx)
                        invalidated += 1
                else:
                    invalidated += len(v)
                    v.clear()
        if invalidated:
            diag["legacy_verified_invalidated"] = int(
                diag.get("legacy_verified_invalidated", 0)) + invalidated
            logger.warning("Legacy pending discard invalidated %d verified step(s); "
                           "they must be re-proven", invalidated)
        if discarded_now:
            diag["legacy_pending_discarded"] = int(
                diag.get("legacy_pending_discarded", 0)) + discarded_now
        if diag:
            # 7195 follow-up 1: owner_unproven is the authoritative CURRENT
            # quarantine; legacy_ownerless_plans is a capped historical sample.
            diag["recovery"] = (
                "Discarded legacy evidence is not replayed; affected plan steps "
                "must be re-proven by fresh, uniquely identified receipts. The "
                "authoritative CURRENT hold list is Reducer.quarantined_plans() "
                "(reasons via quarantine_reasons()): owner_unproven (legacy "
                "migration), ownerless_linked and ownerless_held (Astra 7562/"
                "7582); owner_unproven alone is NOT the full hold list. "
                "legacy_ownerless_plans is only a capped HISTORICAL SAMPLE of "
                "plans quarantined at migration (see legacy_ownerless_total); it "
                "is not updated by rebinds and must not be used to enumerate "
                "actionable plans. A held plan stays quarantined "
                "until an operator calls rebind_plan_owner(plan_id, incident_id, "
                "actor=..., reason=...) after preview_rebind(); targets must be "
                "open and a recorded owner candidate unless "
                "allow_non_candidate=True. An ordinary PLAN does not re-establish "
                "a lost owner.")
        # N7 (7133): persisted + cumulative across later snapshot/restore
        # N10 (7173): bounds enforced on EVERY restore (incl. upgraded ones)
        self._normalize_diagnostics(diag, set(self._owner_unproven)
                                    | set(self.quarantine_reasons()))
        self.migration_diagnostics = diag
        self.legacy_pending_discarded = int(diag.get("legacy_pending_discarded", 0))

    @staticmethod
    def _normalize_diagnostics(diag: dict, unproven: set) -> None:
        """N10 (7173): enforce MAX_DIAG_ENTRIES on every restore, including
        current-format snapshots written by earlier versions.  Totals are
        initialised from the pre-pruned history.  The safety-critical
        owner_unproven set is persisted separately and is NEVER capped;
        candidate keys of still-quarantined plans are kept first."""
        lop = diag.get("legacy_ownerless_plans")
        if lop is not None:
            lop = list(lop) if isinstance(lop, (list, tuple, set)) else []
            diag["legacy_ownerless_total"] = max(
                _as_int(diag.get("legacy_ownerless_total")), len(lop))
            diag["legacy_ownerless_plans"] = lop[:MAX_DIAG_ENTRIES]
        recs = diag.get("owner_rebinds")
        if recs is not None:
            recs = list(recs) if isinstance(recs, (list, tuple)) else []
            diag["owner_rebinds_total"] = max(
                _as_int(diag.get("owner_rebinds_total")), len(recs))
            diag["owner_rebinds"] = recs[-MAX_DIAG_ENTRIES:]
        cmap = diag.get("owner_candidates")
        if cmap is not None:
            cmap = cmap if isinstance(cmap, dict) else {}
            keys = sorted(cmap, key=lambda k: (k not in unproven, str(k)))
            kept = keys[:MAX_DIAG_ENTRIES]
            if len(keys) > len(kept):
                diag["owner_candidates_dropped"] = _as_int(
                    diag.get("owner_candidates_dropped")) + len(keys) - len(kept)
            diag["owner_candidates"] = {
                k: (list(cmap[k]) if isinstance(cmap[k], (list, tuple)) else [])[:8]
                for k in kept}

    def state_snapshot(self) -> dict[str, Any]:
        """Alias for snapshot() for API compatibility."""
        return self.snapshot()
