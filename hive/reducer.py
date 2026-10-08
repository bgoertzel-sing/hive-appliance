"""
HiveReducer — consumes HiveEventBus stream and derives hive-level state.

M5 component: performs cross-agent incident correlation, agent health
rollup, resource aggregation, and drift detection.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import time
import uuid
from types import SimpleNamespace
from typing import Any

from hive.types import (
    AgentHealth,
    AgentHealthSummary,
    HiveEvent,
    HiveIncident,
    HiveState,
)
from schemas.types import EventKind, Severity

logger = logging.getLogger(__name__)

# ── Correlation config ───────────────────────────────────

DEFAULT_CORRELATION_WINDOW = 300.0  # seconds
DEFAULT_CORRELATION_THRESHOLD = 2   # min agents for cross-agent incident
MAX_AGENT_INCIDENTS = 500           # per-agent incident history cap
MAX_HIVE_INCIDENTS = 1000           # total hive-level incident cap
MAX_HIVE_REBIND_RECORDS = 200      # bounded rebind audit trail
MAX_HIVE_REBIND_IDS = 50           # receipt ids kept per audit record
MAX_HIVE_CANDIDATES = 8            # owner candidates kept per held plan
MAX_HIVE_CANDIDATE_KEYS = 256      # Astra 7638 (Low): held plans with candidates
MAX_HIVE_JOURNAL_BYTES = 64 * 1024 * 1024   # Astra 7638 (Low): journal admission cap


class _JournalIndeterminate(Exception):
    """Astra 7638 F-journal-refused-fsync: a journal append failed AND its
    rollback failed, so whether the entry survives a restart is unknown."""

# H1: severity ordering used when merging polled health with reducer state
_HEALTH_RANK = {
    AgentHealth.UNKNOWN: 0,
    AgentHealth.HEALTHY: 1,
    AgentHealth.DEGRADED: 2,
    AgentHealth.FAILED: 3,
}


def _valid_step_index(idx: Any, count: int) -> bool:
    """H2 (6986): step index must be a real int (not bool) in range."""
    return isinstance(idx, int) and not isinstance(idx, bool) and 0 <= idx < count


class HiveReducer:
    """Processes HiveEvents and maintains HiveState.

    Key reduction rules:
    - Agent health rollup from latest state snapshots
    - Incident correlation: same symptom across N agents within time window
    - Resource aggregation across agents
    - Drift detection (config/version divergence)
    """

    def __init__(
        self,
        correlation_window: float = DEFAULT_CORRELATION_WINDOW,
        correlation_threshold: int = DEFAULT_CORRELATION_THRESHOLD,
        rebind_journal: str | None = None,
        volatile_rebinds: bool = True,
    ):
        self._state = HiveState()
        self._correlation_window = correlation_window
        self._correlation_threshold = correlation_threshold
        # Track per-agent incident events for correlation
        self._agent_incidents: dict[str, list[dict[str, Any]]] = {}
        # Track seen hive incident IDs for dedup
        self._seen_hive_incidents: set[str] = set()
        # H2: receipt identities already applied (replay dedupe)
        self._seen_receipts: set[str] = set()
        # H2 (6949): composite plan tracking, keyed "agent:plan_id"
        self._plan_steps: dict[str, int] = {}
        self._plan_verified_steps: dict[str, set[int]] = {}
        self._plan_failed: dict[str, set[int]] = {}   # 6986: failed step indices
        # H2 (6986): receipts awaiting their PLAN, per agent: {rid: payload}
        self._pending_receipts: dict[str, dict[str, dict[str, Any]]] = {}
        # N6 (7075): durable plan owner, "agent:plan_id" -> incident id
        self._plan_owner: dict[str, str] = {}
        # N6 (7133): conflicting PLAN re-registrations rejected
        self.rejected_plan_registrations = 0
        # Ben msg 7547 option (a) (Astra 7562): owner candidates proposed by a
        # re-sent PLAN for a HELD plan ("agent:plan_id" -> [incident ids]) and
        # the bounded audit trail of operator rebinds.
        self.owner_candidates: dict[str, list[str]] = {}
        self.owner_rebinds: list[dict[str, Any]] = []
        self.owner_rebinds_total = 0
        self.owner_candidates_dropped = 0   # Astra 7638 (Low): key cap
        # F-foreign-progress (Astra 7582): incident named by the receipt that
        # last set each step ("agent:plan" -> {idx: incident, '' = plan-only}).
        self._plan_step_src: dict[str, dict[int, str]] = {}
        # F-hold-expiry (Astra 7582): plans ever held ownerless_linked; they
        # get an owner ONLY via the audited rebind_plan_owner().
        self._held_ownerless: set[str] = set()
        self._quiet = False   # preview simulations log at debug level
        # Astra 7582/7638: durable operator rebind journal (JSONL, fsync'd
        # write-ahead).  Each entry records the event-stream POSITION (count
        # of events reduced) and a hash chain of the events up to it; after a
        # restart it is re-applied only at exactly that position and only if
        # the replayed stream hashes identically (F-journal-order).
        self._journal_path = rebind_journal
        # volatile_rebinds=False: without a journal, rebinds are REFUSED
        # rather than silently lost on restart (HiveAppliance default).
        self._volatile_rebinds = volatile_rebinds
        self._event_seq = 0
        self._stream_digest = ""
        self._journal_unapplied: list[dict[str, Any]] = []
        self._journal_indeterminate: dict[str, Any] | None = None
        self._journal_set_aside: list[str] = []
        self._journal_invalid_lines = 0
        self._journal_pending: list[dict[str, Any]] = (
            self._open_journal(rebind_journal) if rebind_journal else [])
        self._replay_journal()

    @property
    def state(self) -> HiveState:
        """Return state."""
        return self._state

    def reduce(self, hive_event: HiveEvent) -> list[HiveIncident]:
        """Process a HiveEvent and return any new HiveIncidents."""
        new_incidents: list[HiveIncident] = []
        agent_id = hive_event.source_agent
        event = hive_event.original_event

        if event is None:
            return new_incidents
        # N6 (7146): conflicting PLAN re-registration rejected before ANY
        # mutation (including timestamps and the event-stream position: a
        # rejected PLAN is deterministic on replay and changes no state).
        if event.kind == EventKind.PLAN and self._reject_conflicting_plan(
                agent_id, event.payload or {}):
            return new_incidents
        self._advance_stream(agent_id, event)   # Astra 7638 F-journal-order

        # Update agent last-event timestamp
        if agent_id in self._state.agents:
            self._state.agents[agent_id].last_event_ts = event.ts
            self._state.agents[agent_id].last_updated = time.time()

        # Handle by event kind
        if event.kind == EventKind.INCIDENT:
            new_incidents.extend(self._handle_incident(agent_id, event))
        elif event.kind == EventKind.OBSERVATION:
            self._handle_observation(agent_id, event)
        elif event.kind == EventKind.PLAN:
            self._handle_plan(agent_id, event)
        elif event.kind == EventKind.RECEIPT:
            self._handle_receipt(agent_id, event)

        self._latch_holds()      # F-hold-expiry (Astra 7582)
        self._replay_journal()   # Astra 7582: durable rebinds
        self._state.last_updated = time.time()
        return new_incidents

    def update_agent_health(self, agent_id: str, summary: AgentHealthSummary) -> None:
        """Update an agent's health summary directly (from polling).

        If the reducer has unresolved incidents for this agent, polled
        health is overridden to at least DEGRADED (or FAILED for
        critical/error incidents) so that a healthy poll cannot mask
        active incident state.
        """
        # H1: merge for every poll, not only HEALTHY ones.  A non-healthy
        # poll (e.g. DEGRADED with open_incidents=0) must not erase the
        # reducer's open-incident count or downgrade FAILED to DEGRADED.
        open_list = self._open_agent_incidents(agent_id)
        if open_list:
            has_critical = any(
                i.get("severity") in ("critical", "error") for i in open_list
            )
            floor = AgentHealth.FAILED if has_critical else AgentHealth.DEGRADED
            if _HEALTH_RANK.get(summary.health, 0) < _HEALTH_RANK[floor]:
                summary.health = floor
            summary.open_incidents = max(summary.open_incidents, len(open_list))
        self._state.agents[agent_id] = summary
        self._state.last_updated = time.time()

    def quarantine_reasons(self) -> dict[str, str]:
        """Plans ("agent:plan_id") held for an ownership reason, with reason.

        Not every plan that cannot close an incident (owned-but-incomplete or
        failed plans are absent).  Derived view, no global size cap; complete
        because open incidents are never pruned (Astra 7562 O-retention).

        ``ownerless_linked`` (Ben msg 7547 option (a), Astra 7562): a
        registered plan with no owner that an open incident links to.  Linkage
        is never ownership.  The plan is HELD (quarantined_plans()); a re-sent
        PLAN declaring incident_id only records an owner candidate; repair is
        preview_rebind() then the audited rebind_plan_owner().
        """
        out: dict[str, str] = {}
        for agent_id, incs in self._agent_incidents.items():
            for inc in incs:
                pid = inc.get("plan_id")
                if inc.get("resolved") or not pid:
                    continue
                key = f"{agent_id}:{pid}"
                if key in self._plan_steps and not self._plan_owner.get(key):
                    out[key] = "ownerless_linked"
        # F-hold-expiry (Astra 7582): once held, held until audited rebind
        for key in self._held_ownerless:
            if key not in out and self._held_latched_key(key):
                out[key] = "ownerless_held"
        return dict(sorted(out.items()))

    def quarantined_plans(self) -> list[str]:
        """CURRENT hold list ("agent:plan_id"), sorted: every plan awaiting an
        operator preview_rebind()/rebind_plan_owner()."""
        return sorted(self.quarantine_reasons())

    def _ownerless_linked(self, agent_id: str, plan_id: str) -> bool:
        key = f"{agent_id}:{plan_id}"
        return (bool(plan_id) and key in self._plan_steps
                and not self._plan_owner.get(key)
                and any(i.get("plan_id") == plan_id
                        for i in self._open_agent_incidents(agent_id)))

    def _held_latched_key(self, key: str) -> bool:
        return (key in self._held_ownerless and key in self._plan_steps
                and not self._plan_owner.get(key))

    def _held_latched(self, agent_id: str, plan_id: str) -> bool:
        return bool(plan_id) and self._held_latched_key(f"{agent_id}:{plan_id}")

    def _latch_holds(self) -> None:
        for agent_id, incs in self._agent_incidents.items():
            for inc in incs:
                pid = inc.get("plan_id")
                if inc.get("resolved") or not pid:
                    continue
                key = f"{agent_id}:{pid}"
                if (key not in self._held_ownerless and key in self._plan_steps
                        and not self._plan_owner.get(key)):
                    self._held_ownerless.add(key)

    def _rebind_check(self, agent_id: str, plan_id: str, incident_id: str,
                      allow_non_candidate: bool):
        if not (self._ownerless_linked(agent_id, plan_id)
                or self._held_latched(agent_id, plan_id)):
            return False, "plan is not quarantined", None
        if not incident_id:
            return False, "no target incident", None
        inc = next((i for i in self._agent_incidents.get(agent_id, [])
                    if i["incident_id"] == incident_id), None)
        if inc is None:
            return False, "unknown target incident", None
        if inc.get("resolved"):
            return False, "target incident is already resolved", inc
        if inc.get("plan_id") and inc["plan_id"] != plan_id:
            return False, "target incident is linked to another plan", inc
        cands = self.owner_candidates.get(f"{agent_id}:{plan_id}", [])
        if incident_id not in cands and not allow_non_candidate:
            return False, "target is not a recorded owner candidate", inc
        return True, "", inc

    def _apply_rebind(self, agent_id: str, plan_id: str, incident_id: str,
                      inc: dict) -> list[int]:
        key = f"{agent_id}:{plan_id}"
        # F-foreign-progress (Astra 7582): evidence naming another incident
        # never counts for the new owner.  Qualification (Astra 7638): a
        # plan-only receipt names no incident -- it proves a step of THIS
        # plan and is kept; the operator vouches the plan fits the target; buffered receipts are rechecked by
        # _drain_pending against the new owner (foreign ones are rejected).
        foreign = self._discard_foreign_steps(key, incident_id)
        self._held_ownerless.discard(key)
        self._plan_owner[key] = incident_id
        if not inc.get("plan_id"):
            inc["plan_id"] = plan_id
        self.owner_candidates.pop(key, None)
        self._drain_pending(agent_id, {plan_id})
        return foreign

    def _discard_foreign_steps(self, key: str, incident_id: str) -> list[int]:
        src = self._plan_step_src.get(key, {})
        steps = (set(self._plan_verified_steps.get(key, ()))
                 | set(self._plan_failed.get(key, ())))
        foreign = sorted(i for i in steps if src.get(i) not in ("", incident_id))
        for i in foreign:
            self._plan_verified_steps.get(key, set()).discard(i)
            self._plan_failed.get(key, set()).discard(i)
            src.pop(i, None)
        if foreign:
            (logger.debug if self._quiet else logger.warning)(
                "Rebind of plan %s -> %s discarded step evidence %s that did "
                "not name the new owner; those steps must be re-proven",
                key, incident_id, foreign)
        return foreign

    # ── Astra 7582/7638: durable rebind journal ──
    def _advance_stream(self, agent_id: str, event: Any) -> None:
        kind = getattr(event.kind, "value", str(event.kind))
        self._event_seq += 1
        self._stream_digest = hashlib.sha256(json.dumps(
            [self._stream_digest, agent_id, str(getattr(event, "id", "")),
             str(kind)]).encode("utf-8")).hexdigest()

    @staticmethod
    def _fsync_dir(path: str) -> None:
        dfd = os.open(os.path.dirname(os.path.abspath(path)), os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)

    def _set_aside_tail(self, fd: int, size: int) -> int:
        """F-journal-tail (Astra 7638): move an unterminated (torn) last line
        to <journal>.torn-<ns> and truncate the journal to its last complete
        line BEFORE any new write.  Returns the new size.  Raises OSError on
        failure (callers then write nothing)."""
        data = os.pread(fd, size, 0)
        keep = data.rfind(b"\n") + 1
        aside = f"{self._journal_path}.torn-{time.time_ns()}"
        afd = os.open(aside, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(afd, data[keep:])
            os.fsync(afd)
        finally:
            os.close(afd)
        os.ftruncate(fd, keep)
        os.fsync(fd)
        self._fsync_dir(aside)
        self._journal_set_aside.append(aside)
        logger.error("Rebind journal %s ended with a torn line (%d bytes); set "
                     "aside to %s before further writes", self._journal_path,
                     size - keep, aside)
        return keep

    def _open_journal(self, path: str) -> list[dict[str, Any]]:
        created = not os.path.exists(path)
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            size = os.fstat(fd).st_size
            if size and os.pread(fd, 1, size - 1) != b"\n":
                size = self._set_aside_tail(fd, size)
            data = os.pread(fd, size, 0) if size else b""
            if created:
                os.fsync(fd)
        finally:
            os.close(fd)
        if created:
            self._fsync_dir(path)          # the new file's directory entry
        return self._parse_journal(path, data)

    def _parse_journal(self, path: str, data: bytes) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for n, raw in enumerate(data.split(b"\n"), 1):
            if not raw.strip():
                continue
            try:
                e = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                self._journal_invalid_lines += 1
                logger.warning("Rebind journal %s line %d unreadable; skipped", path, n)
                continue
            if not (isinstance(e, dict) and e.get("op") == "owner_rebind"
                    and all(isinstance(e.get(k), str) and e.get(k).strip()
                            for k in ("agent_id", "plan_id", "incident_id",
                                      "actor", "reason"))):
                self._journal_invalid_lines += 1
                logger.warning("Rebind journal %s line %d invalid; skipped", path, n)
                continue
            seq = e.get("seq")
            if not (isinstance(seq, int) and not isinstance(seq, bool) and seq >= 0
                    and isinstance(e.get("stream_digest"), str)):
                self._mark_unapplied(e, "legacy entry without event-stream "
                                        "position; not replayed (re-issue the "
                                        "rebind if still wanted)")
                continue
            op_id = str(e.get("op_id") or "")
            if op_id and op_id in seen:
                continue                      # duplicate physical line
            seen.add(op_id)
            out.append(e)
        return out

    def _journal_append(self, entry: dict[str, Any]) -> None:
        """Write-ahead append.  OSError = clean refusal (nothing durable);
        _JournalIndeterminate = write failed and rollback failed too."""
        data = (json.dumps(entry, sort_keys=True) + "\n").encode("utf-8")
        fd = os.open(self._journal_path, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            size = os.fstat(fd).st_size
            if size and os.pread(fd, 1, size - 1) != b"\n":
                size = self._set_aside_tail(fd, size)   # F-journal-tail
            if size + len(data) > MAX_HIVE_JOURNAL_BYTES:
                raise OSError(f"rebind journal would exceed {MAX_HIVE_JOURNAL_BYTES} "
                              "bytes; rotate/compact it (admission refused)")
            try:
                n = os.write(fd, data)
                if n != len(data):
                    raise OSError(f"short journal write ({n}/{len(data)} bytes)")
                os.fsync(fd)
            except OSError as exc:
                # F-journal-refused-fsync (Astra 7638): roll the entry back so
                # a refused rebind can never be applied after a restart.
                try:
                    os.ftruncate(fd, size)
                    os.fsync(fd)
                except OSError as exc2:
                    raise _JournalIndeterminate(
                        f"{exc}; rollback failed: {exc2}") from exc2
                raise
        finally:
            os.close(fd)

    def journal_pending(self) -> list[dict[str, Any]]:
        """Journaled rebinds whose event-stream position is not reached yet."""
        return copy.deepcopy(self._journal_pending)

    def journal_status(self) -> dict[str, Any]:
        """Astra 7638: operator view of rebind durability."""
        return copy.deepcopy({
            "path": self._journal_path,
            "durable": bool(self._journal_path),
            "volatile_rebinds_allowed": self._volatile_rebinds,
            "event_seq": self._event_seq,
            "pending": len(self._journal_pending),
            "unapplied": self._journal_unapplied,
            "indeterminate": self._journal_indeterminate,
            "set_aside": self._journal_set_aside,
            "invalid_lines": self._journal_invalid_lines})

    def _mark_unapplied(self, e: dict[str, Any], why: str) -> None:
        self._journal_unapplied.append({
            k: e.get(k) for k in ("op_id", "agent_id", "plan_id", "incident_id",
                                  "actor", "reason", "seq")} | {"why": why})
        del self._journal_unapplied[:-MAX_HIVE_REBIND_RECORDS]
        logger.error("Journaled hive rebind %s:%s -> %s by %s NOT re-applied: %s",
                     e.get("agent_id"), e.get("plan_id"), e.get("incident_id"),
                     e.get("actor"), why)

    def _replay_journal(self) -> None:
        """F-journal-order (Astra 7638): apply an entry exactly at the event
        position where it originally happened, never earlier or later."""
        if not self._journal_pending:
            return
        keep = []
        for e in self._journal_pending:
            if e["seq"] > self._event_seq:
                keep.append(e)
                continue
            if e["seq"] < self._event_seq:
                self._mark_unapplied(e, "original event position already passed")
            elif e["stream_digest"] != self._stream_digest:
                self._mark_unapplied(e, "replayed event stream differs from the "
                                        "one the rebind was made on")
            else:
                ok, why, inc = self._rebind_check(e["agent_id"], e["plan_id"],
                                                  e["incident_id"], True)
                if not ok:
                    self._mark_unapplied(e, f"state at original position: {why}")
                else:
                    self._do_rebind(e["agent_id"], e["plan_id"], e["incident_id"],
                                    inc, actor=e["actor"], reason=e["reason"],
                                    replayed=True)
        self._journal_pending = keep

    def _held_receipts(self, agent_id: str, plan_id: str,
                       incident_id: str) -> list[dict[str, Any]]:
        out = []
        for rid, rp in self._pending_receipts.get(agent_id, {}).items():
            pid = rp.get("plan_id") or ""
            if pid == plan_id or (not pid and (rp.get("incident_id") or "") == incident_id):
                out.append({"id": rid, "plan_id": pid,
                            "incident_id": rp.get("incident_id") or "",
                            "step_index": rp.get("step_index"),
                            "verified": rp.get("verified")})
        return out

    def preview_rebind(self, agent_id: str, plan_id: str, incident_id: str,
                       allow_non_candidate: bool = False) -> dict[str, Any]:
        """Side-effect-free preview of rebind_plan_owner() (simulated on a
        deep copy).  Result is deep-copied; never aliases live state."""
        ok, why, _ = self._rebind_check(agent_id, plan_id, incident_id,
                                        allow_non_candidate)
        key = f"{agent_id}:{plan_id}"
        cands = list(self.owner_candidates.get(key, []))
        would_close: list[str] = []
        foreign: list[int] = []
        if ok:
            sim = copy.deepcopy(self)
            sim._quiet = True            # Astra 7582 (Low): no live-looking logs
            sim._journal_path = None     # a preview never writes the journal
            sim._journal_pending = []
            before = {i["incident_id"] for i in sim._open_agent_incidents(agent_id)}
            _, _, sinc = sim._rebind_check(agent_id, plan_id, incident_id, True)
            foreign = sim._apply_rebind(agent_id, plan_id, incident_id, sinc)
            would_close = sorted(before - {i["incident_id"] for i in
                                           sim._open_agent_incidents(agent_id)})
        return copy.deepcopy({
            "agent_id": agent_id, "plan_id": plan_id,
            "incident_id": incident_id, "allowed": ok, "refusal": why,
            "hold_reason": self.quarantine_reasons().get(key, ""),
            "candidates": cands, "is_candidate": incident_id in cands,
            "held_receipts": self._held_receipts(agent_id, plan_id, incident_id),
            "foreign_steps_discarded": foreign,
            "would_close": would_close})

    def rebind_plan_owner(self, agent_id: str, plan_id: str, incident_id: str,
                          *, actor: str, reason: str,
                          allow_non_candidate: bool = False) -> bool:
        """TRUSTED-OPERATOR owner rebind for a HELD ownerless_linked plan (Ben
        msg 7547 option (a), Astra 7562).  Same contract as the local
        Reducer.rebind_plan_owner(): non-empty actor and reason; target exists,
        is OPEN, not linked to another plan, and is a recorded owner candidate
        unless allow_non_candidate=True.  Appends an audit record to
        owner_rebinds (bounded).  Returns True if applied."""
        if not (isinstance(actor, str) and actor.strip()):
            raise ValueError("rebind_plan_owner requires a non-empty actor")
        if not (isinstance(reason, str) and reason.strip()):
            raise ValueError("rebind_plan_owner requires a non-empty reason")
        ok, why, inc = self._rebind_check(agent_id, plan_id, incident_id,
                                          allow_non_candidate)
        if not ok:
            logger.warning("Refused hive rebind of %s:%s -> %s by %s: %s",
                           agent_id, plan_id, incident_id, actor, why)
            return False
        if not self._journal_path and not self._volatile_rebinds:
            logger.error("Refused hive rebind of %s:%s -> %s: no rebind journal "
                         "configured, so it would be lost on restart (set "
                         "rebind_journal / HIVE_REBIND_JOURNAL, or pass "
                         "volatile_rebinds=True)", agent_id, plan_id, incident_id)
            return False
        if self._journal_path:
            if self._journal_indeterminate is not None:
                logger.error("Refused hive rebind of %s:%s -> %s: rebind journal "
                             "is fenced after an indeterminate write (%s)",
                             agent_id, plan_id, incident_id,
                             self._journal_indeterminate.get("error"))
                return False
            entry = {"v": 2, "op": "owner_rebind", "op_id": uuid.uuid4().hex,
                     "agent_id": agent_id, "plan_id": plan_id,
                     "incident_id": incident_id, "actor": actor,
                     "reason": reason, "ts": time.time(),
                     "seq": self._event_seq,
                     "stream_digest": self._stream_digest,
                     "candidate": incident_id in self.owner_candidates.get(
                         f"{agent_id}:{plan_id}", [])}
            try:
                self._journal_append(entry)   # write-ahead
            except _JournalIndeterminate as exc:
                self._journal_indeterminate = {"op_id": entry["op_id"],
                                               "entry": entry, "error": str(exc)}
                logger.critical("Hive rebind of %s:%s -> %s NOT applied, but its "
                                "journal entry may survive a restart (%s); journal "
                                "fenced: further rebinds refused until an operator "
                                "inspects %s", agent_id, plan_id, incident_id,
                                exc, self._journal_path)
                return False
            except OSError as exc:
                logger.error("Refused hive rebind of %s:%s -> %s: rebind "
                             "journal write failed (rolled back): %s", agent_id,
                             plan_id, incident_id, exc)
                return False
        self._do_rebind(agent_id, plan_id, incident_id, inc, actor=actor,
                        reason=reason)
        return True

    def _do_rebind(self, agent_id: str, plan_id: str, incident_id: str,
                   inc: dict, *, actor: str, reason: str,
                   replayed: bool = False) -> None:
        key = f"{agent_id}:{plan_id}"
        hold = self.quarantine_reasons().get(key, "ownerless_linked")
        is_cand = incident_id in self.owner_candidates.get(key, [])
        held = self._held_receipts(agent_id, plan_id, incident_id)
        before = {i["incident_id"] for i in self._open_agent_incidents(agent_id)}
        foreign = self._apply_rebind(agent_id, plan_id, incident_id, inc)
        closed = sorted(before - {i["incident_id"] for i in
                                  self._open_agent_incidents(agent_id)})
        self.owner_rebinds_total += 1
        self.owner_rebinds.append({
            "agent_id": agent_id, "plan_id": plan_id,
            "incident_id": incident_id, "actor": actor, "reason": reason,
            "candidate": is_cand, "hold_reason": hold,
            "pending_before": len(held),
            "held_receipt_ids": [str(r["id"]) for r in held][:MAX_HIVE_REBIND_IDS],
            "foreign_steps_discarded": foreign[:MAX_HIVE_REBIND_IDS],
            "replayed": replayed,
            "closed": closed})
        del self.owner_rebinds[:-MAX_HIVE_REBIND_RECORDS]
        logger.warning("Operator hive rebind%s by %s (%s): %s owner set to "
                       "incident %s (candidate=%s, held=%d, foreign=%s, "
                       "closed=%s)", " (journal replay)" if replayed else "",
                       actor, reason, key, incident_id, is_cand, len(held),
                       foreign, closed)

    def _open_agent_incidents(self, agent_id: str) -> list[dict[str, Any]]:
        return [i for i in self._agent_incidents.get(agent_id, [])
                if not i.get("resolved")]

    def _recompute_agent_health(self, agent_id: str) -> None:
        summary = self._state.agents.get(agent_id)
        if summary is None:
            return
        open_list = self._open_agent_incidents(agent_id)
        summary.open_incidents = len(open_list)
        if not open_list:
            if summary.health in (AgentHealth.FAILED, AgentHealth.DEGRADED):
                summary.health = AgentHealth.HEALTHY
        elif any(i.get("severity") in ("critical", "error") for i in open_list):
            summary.health = AgentHealth.FAILED
        elif _HEALTH_RANK.get(summary.health, 0) < _HEALTH_RANK[AgentHealth.DEGRADED]:
            summary.health = AgentHealth.DEGRADED

    def register_agent(self, agent_id: str) -> None:
        """Register a new agent in hive state."""
        if agent_id not in self._state.agents:
            self._state.agents[agent_id] = AgentHealthSummary(agent_id=agent_id)
            self._agent_incidents[agent_id] = []
            logger.info("Registered agent %s in reducer", agent_id)

    def unregister_agent(self, agent_id: str) -> None:
        """Remove an agent from hive health state.

        F-unregister-escape (Astra 7638): unregister is a TEMPORARY removal,
        not a fresh start.  Plan identity, progress, step provenance, owners,
        candidates, buffered/deduplicated receipts and the ownerless hold
        latch are all KEPT, so re-registering can never turn a held plan into
        an owned one without the audited rebind_plan_owner()."""
        self._state.agents.pop(agent_id, None)
        self._agent_incidents.pop(agent_id, None)
        logger.info("Unregistered agent %s from reducer", agent_id)

    def update_resources(self, agent_id: str,
                         disk_total: int = 0, disk_used: int = 0,
                         memory_total: int = 0, memory_used: int = 0,
                         cpu_percent: float = 0.0) -> list[str]:
        """Update resource metrics for an agent. Returns any threshold alerts."""
        res = self._state.resources
        res.agent_resources[agent_id] = {
            "disk_total": disk_total,
            "disk_used": disk_used,
            "memory_total": memory_total,
            "memory_used": memory_used,
            "cpu_percent": cpu_percent,
        }

        # Reaggregate totals
        res.total_disk_bytes = sum(
            r.get("disk_total", 0) for r in res.agent_resources.values()
        )
        res.used_disk_bytes = sum(
            r.get("disk_used", 0) for r in res.agent_resources.values()
        )
        res.total_memory_bytes = sum(
            r.get("memory_total", 0) for r in res.agent_resources.values()
        )
        res.used_memory_bytes = sum(
            r.get("memory_used", 0) for r in res.agent_resources.values()
        )
        res.total_cpu_percent = sum(
            r.get("cpu_percent", 0.0) for r in res.agent_resources.values()
        )

        return res.alerts()

    # ── private handlers ──────────────────────────────────

    def _handle_incident(self, agent_id: str, event: Any) -> list[HiveIncident]:
        """Handle an incident event from an agent."""
        new_incidents: list[HiveIncident] = []
        payload = event.payload
        symptom = payload.get("symptom", payload.get("message", "unknown"))

        # Track per-agent incident with cap
        if agent_id not in self._agent_incidents:
            self._agent_incidents[agent_id] = []
        incidents_list = self._agent_incidents[agent_id]
        # H2: incidents are keyed by their identity (deterministic incident
        # id from the payload), not by the carrying event id, so replayed or
        # re-emitted incident events do not inflate open_incidents.
        identity = payload.get("id") or event.id
        existing = next((i for i in incidents_list
                         if i["incident_id"] == identity), None)
        if existing is not None:
            existing["ts"] = max(existing["ts"], event.ts)
            if payload.get("resolved"):
                existing["resolved"] = True
            self._recompute_agent_health(agent_id)
            return new_incidents
        incidents_list.append({
            "incident_id": identity,
            "ts": event.ts,
            "symptom": symptom,
            "severity": payload.get("severity", "warn"),
            "plan_id": payload.get("plan_id", "") or self._unique_owned_plan(agent_id, identity),  # N8 (7146)
            "resolved": bool(payload.get("resolved", False)),
        })
        # Prune old entries beyond cap -- resolved ones first, never open ones
        if len(incidents_list) > MAX_AGENT_INCIDENTS:
            overflow = len(incidents_list) - MAX_AGENT_INCIDENTS
            kept, dropped = [], 0
            for i in incidents_list:
                if dropped < overflow and i.get("resolved"):
                    dropped += 1
                    continue
                kept.append(i)
            # O-retention (Astra 7562): OPEN incidents are never pruned, even
            # past the cap -- each may be an unresolved ownership hold that
            # quarantine_reasons() must keep reporting.  Only resolved history
            # is trimmed; the list may exceed the cap while opens exceed it.
            if dropped < overflow:
                logger.warning(
                    "Agent %s has %d incidents (cap %d); open incidents are "
                    "retained past the cap.", agent_id, len(kept),
                    MAX_AGENT_INCIDENTS)
            self._agent_incidents[agent_id] = kept

        # Update agent health
        self._recompute_agent_health(agent_id)
        # N8 (7146) / H2 (7160): drain pending evidence now eligible via the
        # late incident, then re-check completion of every plan it OWNS.
        pre = f"{agent_id}:"
        owned = {k[len(pre):] for k, o in self._plan_owner.items()
                 if k.startswith(pre) and o == identity}
        self._drain_pending(agent_id, owned)
        # Late-link (Astra 7562): an incident that links to an already
        # complete OWNERLESS plan gets the same WARNING as the in-order case.
        # _maybe_resolve_plan never closes anything for an ownerless plan.
        lpid = incidents_list[-1].get("plan_id") if incidents_list else ""
        if (lpid and f"{agent_id}:{lpid}" in self._plan_steps
                and not self._plan_owner.get(f"{agent_id}:{lpid}")):
            self._maybe_resolve_plan(agent_id, lpid, identity)

        # Attempt cross-agent correlation
        correlated = self._correlate_incidents(symptom, event.ts)
        if correlated:
            new_incidents.append(correlated)

        logger.debug(
            "Handled incident from agent %s: symptom=%s", agent_id, symptom
        )
        return new_incidents

    def _correlate_incidents(self, symptom: str, ts: float) -> HiveIncident | None:
        """Check if this symptom appears across enough agents within the window."""
        cutoff = ts - self._correlation_window
        affected_agents: list[str] = []
        source_ids: list[str] = []

        for agent_id, incidents in self._agent_incidents.items():
            for inc in incidents:
                if (inc["symptom"] == symptom and inc["ts"] >= cutoff):
                    if agent_id not in affected_agents:
                        affected_agents.append(agent_id)
                    source_ids.append(inc["incident_id"])

        if len(affected_agents) >= self._correlation_threshold:
            # Create deterministic hive incident
            hinc = HiveIncident.deterministic(
                symptom=symptom,
                affected_agents=affected_agents,
                source_incidents=source_ids,
                severity=Severity.ERROR,
            )
            if hinc.id not in self._seen_hive_incidents:
                self._seen_hive_incidents.add(hinc.id)
                self._state.incidents.append(hinc)
                # Cap hive incidents list
                if len(self._state.incidents) > MAX_HIVE_INCIDENTS:
                    # Keep only resolved + most recent unresolved
                    resolved = [i for i in self._state.incidents if i.resolved]
                    unresolved = [i for i in self._state.incidents if not i.resolved]
                    self._state.incidents = resolved[-MAX_HIVE_INCIDENTS // 2:] + unresolved[-MAX_HIVE_INCIDENTS // 2:]
                logger.info(
                    "Correlated hive incident %s: symptom=%s, agents=%s",
                    hinc.id, symptom, affected_agents,
                )
                return hinc

        return None

    def _handle_observation(self, agent_id: str, event: Any) -> None:
        """Update agent state from observations."""
        if agent_id in self._state.agents:
            summary = self._state.agents[agent_id]
            payload = event.payload

            # Update services if service observation
            if "service" in payload:
                svc = payload["service"]
                active = payload.get("active", "unknown")
                summary.services[svc] = active

    def _handle_plan(self, agent_id: str, event: Any) -> None:
        """H2: register plan step count, link incident->plan, then replay any
        receipts that arrived before this PLAN (6986: never fail-open)."""
        payload = event.payload or {}
        plan_id = payload.get("id", "")
        steps = payload.get("steps", []) or []
        if not plan_id or not steps:
            return
        key = f"{agent_id}:{plan_id}"
        inc_id = payload.get("incident_id", "") or ""
        if self._reject_conflicting_plan(agent_id, payload):
            return
        if inc_id and (self._ownerless_linked(agent_id, plan_id)
                       or self._held_latched(agent_id, plan_id)):
            # Ben msg 7547 option (a) (Astra 7562): an ordinary PLAN never
            # sets the owner of a HELD plan; it only records a candidate.
            if (key not in self.owner_candidates
                    and len(self.owner_candidates) >= MAX_HIVE_CANDIDATE_KEYS):
                # Astra 7638 (Low): advisory candidates are capped; the HOLD
                # itself is never dropped (rebind with allow_non_candidate).
                self.owner_candidates_dropped += 1
                lst: list[str] = []
            else:
                lst = self.owner_candidates.setdefault(key, [])
            if inc_id not in lst and len(lst) < MAX_HIVE_CANDIDATES:
                lst.append(inc_id)
            logger.warning("PLAN %s -> %s from %s held (ownerless plan linked "
                           "to an open incident): recorded as owner candidate "
                           "only; use preview_rebind() then rebind_plan_owner()",
                           plan_id, inc_id, agent_id)
            return
        if key not in self._plan_steps:
            self._plan_steps[key] = len(steps)
            self._plan_verified_steps[key] = set()
            self._plan_failed[key] = set()
        if inc_id:
            self._plan_owner.setdefault(key, inc_id)   # N6 (7075)
            for inc in self._agent_incidents.get(agent_id, []):
                if inc["incident_id"] == inc_id and not inc.get("plan_id"):
                    inc["plan_id"] = plan_id
        # N3 (7003): apply the WHOLE newly eligible buffer first, then decide
        # completion once -- a buffered failure must not be skipped because
        # an earlier buffered success already closed the incident.
        self._drain_pending(agent_id, {plan_id})

    def _handle_receipt(self, agent_id: str, event: Any, resolve: bool = True) -> Any:
        """Handle repair receipt -- may resolve an agent's incident.

        H2 (6949/6986):
        - untargeted receipts (no incident_id/plan_id) resolve nothing;
        - contradictory identity (incident linked to another plan) is rejected;
        - resolution REQUIRES registered plan metadata: a receipt whose plan
          is unknown (missing or late PLAN) is buffered, not applied, and is
          replayed once the PLAN arrives;
        - completion needs a verified receipt for every distinct int
          step_index (bool/out-of-range rejected) and no currently failed step;
        - replayed receipts (same receipt id) are applied at most once.
        """
        payload = dict(event.payload or {})
        rid = payload.get("id") or getattr(event, "id", "") or ""
        payload["id"] = rid
        key = f"{agent_id}:{rid}"
        if key in self._seen_receipts:
            logger.debug("Ignoring replayed receipt %s from %s", rid, agent_id)
            return
        inc_id = payload.get("incident_id", "") or ""
        plan_id = payload.get("plan_id", "") or ""
        if not inc_id and not plan_id:
            self._seen_receipts.add(key)
            logger.warning("Ignoring untargeted receipt %s from %s", rid, agent_id)
            return
        target = None
        if inc_id:
            # N6 (7075): durable linkage (any lifecycle state) + plan owner
            target = next((i for i in self._agent_incidents.get(agent_id, [])
                           if i["incident_id"] == inc_id), None)
            owner = self._plan_owner.get(f"{agent_id}:{plan_id}", "") if plan_id else ""
            linked = (target or {}).get("plan_id", "")
            # N6 (7133): the immutable owner decides when known
            if plan_id and ((owner and owner != inc_id)
                            or (not owner and linked and linked != plan_id)):
                self._seen_receipts.add(key)
                self._pending_receipts.get(agent_id, {}).pop(rid, None)
                logger.warning("Rejecting contradictory receipt %s (incident %s "
                               "linked to plan %s; plan %s owned by %s)", rid,
                               inc_id, linked, plan_id, owner)
                return
        eff_plan = plan_id or (target.get("plan_id", "") if target else "")
        if not eff_plan and inc_id:
            # N8 (7146): unlinked incident-only receipt -> unique owned plan
            eff_plan = self._unique_owned_plan(agent_id, inc_id)
        pkey = f"{agent_id}:{eff_plan}" if eff_plan else ""
        if not plan_id and pkey:
            # N6 (7133): incident-only receipt must name the inferred plan's owner
            eowner = self._plan_owner.get(pkey, "")
            if eowner and eowner != inc_id:
                self._seen_receipts.add(key)
                self._pending_receipts.get(agent_id, {}).pop(rid, None)
                logger.warning("Rejecting receipt %s: incident %s is not the "
                               "owner (%s) of plan %s", rid, inc_id, eowner, eff_plan)
                return
        if not pkey or pkey not in self._plan_steps:
            self._pending_receipts.setdefault(agent_id, {}).setdefault(rid, payload)
            return
        self._seen_receipts.add(key)
        self._pending_receipts.get(agent_id, {}).pop(rid, None)
        idx = payload.get("step_index")
        if _valid_step_index(idx, self._plan_steps[pkey]):
            # F-foreign-progress (Astra 7582): remember whose evidence it is
            self._plan_step_src.setdefault(pkey, {})[idx] = inc_id
            if payload.get("verified") is True:
                self._plan_verified_steps[pkey].add(idx)
                self._plan_failed[pkey].discard(idx)
            else:
                self._plan_failed[pkey].add(idx)
                self._plan_verified_steps[pkey].discard(idx)
        if resolve:
            self._maybe_resolve_plan(agent_id, eff_plan, inc_id)
        return eff_plan

    def _maybe_resolve_plan(self, agent_id: str, plan_id: str, inc_id: str) -> None:
        pkey = f"{agent_id}:{plan_id}"
        n = self._plan_steps.get(pkey, 0)
        if not n or self._plan_failed.get(pkey):
            return
        if len(self._plan_verified_steps.get(pkey, ())) < n:
            return
        if self._pending_blocks(agent_id, plan_id, self._plan_owner.get(pkey, "")):
            return
        owner = self._plan_owner.get(pkey, "")
        # P3-ownerless (Astra 7519): the immutable owner is the SOLE completion
        # authority; an ownerless plan never closes linked incidents.
        if not owner:
            # Ben msg 7547 option (a) (Astra 7562): HELD, repaired by rebind.
            linked = sorted(i["incident_id"]
                            for i in self._open_agent_incidents(agent_id)
                            if i.get("plan_id") == plan_id)
            if linked:
                (logger.debug if self._quiet else logger.warning)(
                    "Agent %s plan %s is complete but has no proven owner; it "
                    "closes nothing (linked open incidents %s stay open). "
                    "It is HELD in quarantined_plans() (ownerless_linked); "
                    "repair with preview_rebind()/rebind_plan_owner(). A "
                    "re-sent PLAN only records an owner candidate.", agent_id,
                    plan_id, linked)
            return
        changed = False
        for inc in self._open_agent_incidents(agent_id):
            linked = inc.get("plan_id")
            if inc["incident_id"] == owner:
                if not linked:
                    inc["plan_id"] = plan_id
                inc["resolved"] = True
                changed = True
                (logger.debug if self._quiet else logger.info)(
                            "Agent %s incident %s resolved (all %d plan steps "
                            "verified)", agent_id, inc["incident_id"], n)
        if changed:
            self._recompute_agent_health(agent_id)

    def _reject_conflicting_plan(self, agent_id: str, payload: dict) -> bool:
        plan_id = payload.get("id", "") or ""
        inc_id = payload.get("incident_id", "") or ""
        owner = self._plan_owner.get(f"{agent_id}:{plan_id}", "") if plan_id else ""
        if inc_id and owner and owner != inc_id:
            self.rejected_plan_registrations += 1
            logger.warning("Rejecting PLAN %s -> %s from %s: plan is owned by "
                           "incident %s", plan_id, inc_id, agent_id, owner)
            return True
        return False

    def _unique_owned_plan(self, agent_id: str, inc_id: str) -> str:
        pre = f"{agent_id}:"
        owned = [k[len(pre):] for k, o in self._plan_owner.items()
                 if k.startswith(pre) and o == inc_id]
        return owned[0] if len(owned) == 1 else ""

    def _drain_pending(self, agent_id: str, touched: set) -> None:
        touched = set(touched)
        for rid, p in list(self._pending_receipts.get(agent_id, {}).items()):
            got = self._handle_receipt(agent_id, SimpleNamespace(payload=p, id=rid),
                                       resolve=False)
            if got:
                touched.add(got)
        for pid in sorted(touched):
            self._maybe_resolve_plan(agent_id, pid, "")

    def _pending_blocks(self, agent_id: str, plan_id: str, owner: str) -> bool:
        linked = {i["incident_id"] for i in self._agent_incidents.get(agent_id, [])
                  if i.get("plan_id") == plan_id}
        if owner:
            linked.add(owner)
        for p in self._pending_receipts.get(agent_id, {}).values():
            pid = p.get("plan_id") or ""
            if pid == plan_id or (not pid and (p.get("incident_id") or "") in linked):
                return True
        return False

    def resolve_hive_incident(self, incident_id: str) -> bool:
        """Mark a hive-level incident as resolved."""
        for inc in self._state.incidents:
            if inc.id == incident_id and not inc.resolved:
                inc.resolved = True
                inc.resolution_ts = time.time()
                logger.info("Resolved hive incident %s", incident_id)
                return True
        return False

    def detect_drift(self) -> list[dict[str, Any]]:
        """Detect configuration/version drift across agents.

        Returns a list of drift observations (service name -> agents with
        differing statuses).
        """
        # Collect all services and their statuses per agent
        service_agents: dict[str, dict[str, str]] = {}  # service -> {agent: status}
        for agent_id, summary in self._state.agents.items():
            for svc, status in summary.services.items():
                service_agents.setdefault(svc, {})[agent_id] = status

        drifts: list[dict[str, Any]] = []
        for svc, agents in service_agents.items():
            statuses = set(agents.values())
            if len(statuses) > 1:
                drifts.append({
                    "service": svc,
                    "agents": dict(agents),
                    "statuses": list(statuses),
                })
        return drifts
