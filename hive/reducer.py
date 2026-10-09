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
MAX_HIVE_PLANS = 10000             # Astra 7656 (Low): overall tracked-plan admission cap
MAX_HIVE_UNAPPLIED_RECORDS = 10000  # Astra 7656 (Low): retained unapplied dispositions
JOURNAL_VERSION = 5                # Astra 7694: journal_header + identity anchor


class _JournalIndeterminate(Exception):
    """Astra 7638 F-journal-refused-fsync: a journal append failed AND its
    rollback failed, so whether the record survives a restart is unknown."""


class _JournalChanged(Exception):
    """Astra 7678/7694: the journal file (or its identity anchor) is no longer
    byte-for-byte what this process last wrote or verified."""


class RebindResult:
    """Astra 7694 F-applied-without-durable-commit: structured outcome of
    HiveReducer.rebind_plan_owner().

    status   "applied"   -- applied in memory AND (with a journal) its commit
                            record is durable, so a restart replays it.
             "refused"   -- not applied; nothing that could replay it is durable.
             "uncertain" -- applied in memory, but whether its commit record
                            is durable is UNKNOWN (commit write and rollback
                            both failed).  After a restart it may be replayed
                            or the plan may be held again.  The journal is
                            fenced.  NOT a durable authorization.
    applied  bool: applied in this process's memory.
    durable  True / False / None (unknown).
    bool(result) is True ONLY for status "applied", so code that treats a
    truthy result as durable authorization never accepts "uncertain"."""
    __slots__ = ("status", "applied", "durable", "op_id", "detail")

    def __init__(self, status: str, *, applied: bool, durable: bool | None,
                 op_id: str = "", detail: str = "") -> None:
        self.status, self.applied, self.durable = status, applied, durable
        self.op_id, self.detail = op_id, detail

    def __bool__(self) -> bool:
        return self.status == "applied"

    def as_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__slots__}

    def __repr__(self) -> str:
        return (f"RebindResult({self.status!r}, applied={self.applied}, "
                f"durable={self.durable}, op_id={self.op_id!r})")

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
        self._journal_unapplied_total = 0   # Astra 7656: cumulative
        # Astra 7678: commit-record journal.  _journal_fence != None means the
        # journal is UNHEALTHY: every rebind is refused until an operator
        # calls clear_journal_fence().  It is never written to disk: a damaged
        # journal is never trimmed or repaired, so it re-fences on restart.
        self._journal_fence: dict[str, Any] | None = None
        self._journal_corrupt: list[dict[str, Any]] = []
        self._journal_size = 0          # bytes this process expects on disk
        self._journal_tip = ""          # rec_hash of the last record
        self._journal_last = b""        # last record line as written
        self._journal_records = 0
        self._journal_sha = hashlib.sha256(b"").hexdigest()  # of bytes on disk
        self._journal_id = ""           # Astra 7694: journal_header identity
        self._rebind_op_id = ""
        self.last_rebind_result: RebindResult | None = None
        # committed rebinds this process holds APPLIED (live or replayed)
        self._journal_applied: list[dict[str, Any]] = []
        self.journal_fence_clearances: list[dict[str, Any]] = []
        self.plans_refused_cap = 0
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
        """Hash chain over the reduced event stream.  Astra 7656
        F-journal-content: covers the event's canonical CONTENT (id, kind, ts,
        source, subject, payload, severity, schema version), not just ids, so
        an edited event with reused ids no longer matches a journal entry."""
        def val(x: Any) -> str:
            return str(getattr(x, "value", x))
        canon = {"id": str(getattr(event, "id", "")),
                 "kind": val(getattr(event, "kind", "")),
                 "ts": getattr(event, "ts", None),
                 "source": getattr(event, "source", ""),
                 "subject": getattr(event, "subject", ""),
                 "payload": getattr(event, "payload", None),
                 "severity": val(getattr(event, "severity", "")),
                 "schema_version": getattr(event, "schema_version", "")}
        try:
            blob = json.dumps([self._stream_digest, agent_id, canon],
                              sort_keys=True, default=str, separators=(",", ":"))
        except (TypeError, ValueError):   # e.g. mixed-type payload keys
            blob = repr([self._stream_digest, agent_id, canon])
        self._event_seq += 1
        self._stream_digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()

    @staticmethod
    def _fsync_dir(path: str) -> None:
        dfd = os.open(os.path.dirname(os.path.abspath(path)), os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)

    # ── Astra 7678: commit-record rebind journal (format v4) ──
    # Each rebind is journaled as a "rebind_pending" record followed, once
    # durable, by a "rebind_commit" record naming it.  Every record carries
    # "prev" (rec_hash of the record before it; "" for the first) and its own
    # "rec_hash", so a reordered, removed, inserted or edited record breaks
    # the chain.  Only rebinds with a valid commit are replayed.  Any record
    # that cannot be verified fences the WHOLE journal.
    @staticmethod
    def _rec_hash(r: dict[str, Any]) -> str:
        """SHA-256 of a record's content (every field but rec_hash, including
        the chain link "prev").  Detects accidental and naive edits; it is
        NOT a keyed MAC."""
        return hashlib.sha256(json.dumps(
            {k: v for k, v in r.items() if k != "rec_hash"},
            sort_keys=True, default=str).encode("utf-8")).hexdigest()

    @staticmethod
    def _write_all(fd: int, data: bytes) -> None:
        off = 0
        while off < len(data):
            n = os.write(fd, data[off:])
            if n <= 0:
                raise OSError("write made no progress")
            off += n

    def _write_file_durably(self, path: str, data: bytes) -> None:
        """New file, fully written, fsync'd, size-checked, directory fsync'd.
        On failure the file is removed and OSError raised."""
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            try:
                self._write_all(fd, data)
                os.fsync(fd)
                if os.fstat(fd).st_size != len(data):
                    raise OSError(f"{path}: incomplete write")
            finally:
                os.close(fd)
            self._fsync_dir(path)
        except OSError:
            try:
                os.unlink(path)
            except OSError:
                pass
            raise

    def _legacy_fence_path(self, path: str | None = None) -> str:
        return f"{path or self._journal_path}.fence"

    def _set_fence(self, kind: str, error: str, **extra: Any) -> None:
        self._journal_fence = {"kind": kind, "error": error,
                               "found_at_startup": False, "ts": time.time(),
                               **extra}
        logger.critical("Rebind journal %s is FENCED (%s): %s -- journal "
                        "unhealthy, rebinds refused until an operator inspects "
                        "it and calls clear_journal_fence()",
                        self._journal_path, kind, error)

    # ── Astra 7694: journal identity ──
    # The first record is a hashed "journal_header" carrying a random
    # journal_id; the chain starts from it.  The current journal_id is also
    # stored, fsync'd, in a separate identity anchor file <journal>.id.  A
    # journal whose header does not match the anchor (an older or archived
    # journal swapped back in) fences the whole journal.  Astra 7701: the
    # anchor is always written BEFORE its journal, so a journal without a
    # matching anchor (even header-only) always fences; and any pre-v5
    # artifact fences before anything is created or adopted.
    LEGACY_MARKER_SUFFIXES = (".fence", ".fence.tmp")
    @staticmethod
    def _id_path(path: str) -> str:
        return f"{path}.id"

    @staticmethod
    def _header_record(jid: str) -> dict[str, Any]:
        h = {"v": JOURNAL_VERSION, "op": "journal_header", "journal_id": jid,
             "ts": time.time(), "prev": ""}
        h["rec_hash"] = HiveReducer._rec_hash(h)
        return h

    def _read_anchor(self, path: str) -> str | None:
        """journal_id named by the identity anchor; None if it does not exist;
        ValueError if it exists but is unreadable or malformed."""
        try:
            with open(self._id_path(path), "rb") as f:
                raw = f.read()
        except FileNotFoundError:
            return None
        try:
            a = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValueError(f"identity anchor unreadable ({exc})") from exc
        if not (isinstance(a, dict) and a.get("v") == JOURNAL_VERSION
                and isinstance(a.get("journal_id"), str) and a["journal_id"]):
            raise ValueError("identity anchor malformed or legacy format")
        return a["journal_id"]

    def _replace_durably(self, path: str, data: bytes) -> None:
        """Write a temp file durably, rename it over path, fsync the dir."""
        tmp = f"{path}.new-{time.time_ns()}"
        self._write_file_durably(tmp, data)
        try:
            os.replace(tmp, path)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        self._fsync_dir(path)

    def _write_anchor(self, path: str, jid: str) -> None:
        self._replace_durably(self._id_path(path), (json.dumps(
            {"v": JOURNAL_VERSION, "journal_id": jid}, sort_keys=True)
            + "\n").encode("utf-8"))

    def _set_journal_state(self, data: bytes, tip: str, last: bytes,
                           records: int, jid: str) -> None:
        self._journal_size, self._journal_tip = len(data), tip
        self._journal_last, self._journal_records = last, records
        self._journal_sha = hashlib.sha256(data).hexdigest()
        self._journal_id = jid

    def _create_journal(self, path: str) -> None:
        """New journal (Astra 7701): the identity anchor is written and fsync'd
        (file, rename, directory) FIRST; only then is the journal header
        renamed into place.  A crash between the two leaves an anchor without
        a journal, which fences at the next start.  There is never a journal
        without its anchor, so a journal without one is never adopted."""
        jid = uuid.uuid4().hex
        hdr = self._header_record(jid)
        data = (json.dumps(hdr, sort_keys=True) + "\n").encode("utf-8")
        self._write_anchor(path, jid)
        self._replace_durably(path, data)
        self._set_journal_state(data, hdr["rec_hash"], data, 1, jid)

    def _fence_identity(self, out: list[dict[str, Any]], why: str) -> list:
        for e in out:
            self._mark_unapplied(e, f"journal fenced: {why}; not replayed")
        self._set_fence("identity", why + "; no journaled rebind is replayed",
                        found_at_startup=True)
        return []

    def _legacy_artifacts(self, path: str, data: bytes
                          ) -> "tuple[list[str], dict[str, Any] | None]":
        """Astra 7701 F-legacy-marker-startup-bypass: every pre-v5 artifact --
        old fence marker files (<journal>.fence, <journal>.fence.tmp) and a
        journal holding any v1-v4 record (incl. cancelled/abort records)."""
        found = [path + sfx for sfx in self.LEGACY_MARKER_SUFFIXES
                 if os.path.lexists(path + sfx)]
        first = None
        for n, raw in enumerate(data.split(b"\n"), 1):
            if not raw.strip():
                continue
            try:
                r = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                continue
            if not isinstance(r, dict):
                continue
            v, op = r.get("v"), r.get("op")
            if (isinstance(v, int) and not isinstance(v, bool)
                    and 1 <= v < JOURNAL_VERSION) or op in ("owner_rebind",
                                                           "abort_rebind"):
                first = {"line": n, "why": f"legacy journal format v{v} "
                                           f"(op {op!r})"}
                found.append(f"{path} (pre-v5 journal: line {n} is format v{v}, "
                             f"op {op!r})")
                break
        return found, first

    def _fence_legacy(self, found: list[str], first: dict[str, Any] | None) -> list:
        if first is not None:
            self._journal_corrupt = [first]
        self._set_fence(
            "legacy", "pre-v5 rebind journal artifact(s) present: "
            + "; ".join(found) + ". MIGRATION: nothing in them is replayed and "
            "new rebinds are refused. Inspect them, then call "
            "clear_journal_fence(actor=..., reason=...) -- it archives the old "
            "journal byte-for-byte, moves old fence files aside and starts a new "
            "v5 journal -- and re-issue each rebind still wanted with "
            "rebind_plan_owner()", found_at_startup=True, artifacts=list(found))
        return []

    def _open_journal(self, path: str) -> list[dict[str, Any]]:
        """Startup.  Read-only apart from creating a brand-new journal: a
        damaged journal is never trimmed or repaired, so whatever fenced it
        fences it again after every restart until clear_journal_fence().
        Order (Astra 7701): (1) any pre-v5 artifact fences before anything is
        created or adopted; (2) a journal is created only when neither the
        journal nor its anchor exists (anchor first); (3) a journal without a
        matching anchor ALWAYS fences, whatever it contains."""
        idp = self._id_path(path)
        try:
            exists = os.path.lexists(path)
            data = b""
            if exists:
                with open(path, "rb") as f:
                    data = f.read()
            legacy, first = self._legacy_artifacts(path, data)
            if legacy:
                return self._fence_legacy(legacy, first)
            anchor = self._read_anchor(path)
            if not exists and anchor is None:
                self._create_journal(path)
                return []
        except OSError as exc:
            self._set_fence("unwritable", f"rebind journal cannot be created or "
                            f"read ({exc}); no journaled rebind is replayed",
                            found_at_startup=True)
            return []
        except ValueError as exc:
            self._set_fence("identity", f"{idp}: {exc}; no journaled rebind is "
                            "replayed", found_at_startup=True)
            return []
        if not exists:
            return self._fence_identity([], (
                f"journal is missing but the identity anchor {idp} names journal "
                f"{anchor}: the journal was removed, or its creation was "
                "interrupted after the anchor was written"))
        if not data:
            return self._fence_identity([], (
                "journal is an empty file (" + ("no identity anchor" if anchor
                is None else f"identity anchor {idp} names journal {anchor}")
                + "): this version never leaves an empty journal"))
        out = self._parse_journal(path, data)
        if self._journal_fence is not None:
            return []
        if anchor is None:
            return self._fence_identity(out, (
                f"identity anchor {idp} is missing for journal "
                f"{self._journal_id} ({self._journal_records} record(s)): the "
                "anchor is always written before its journal, so it was removed "
                "or this journal does not belong here"))
        if anchor != self._journal_id:
            return self._fence_identity(out, (
                f"journal header id {self._journal_id} does not match the "
                f"identity anchor {anchor} ({idp}): an older or archived "
                "journal was put in place of the current one"))
        return out

    def _check_record(self, r: Any, n: int, tip: str,
                      pend: dict[str, dict[str, Any]], done: set[str]) -> str:
        """'' if record r (line n) is verifiable at this point, else why not."""
        if not isinstance(r, dict):
            return "not a JSON object"
        if r.get("v") != JOURNAL_VERSION:
            return (f"legacy or unknown record format v{r.get('v')} "
                    f"(op {r.get('op')!r})")
        if r.get("rec_hash") != self._rec_hash(r):
            return "record hash mismatch (edited or corrupted)"
        if r.get("prev") != tip:
            return ("hash chain broken (a record was reordered, removed or "
                    "inserted)")
        op, op_id = r.get("op"), r.get("op_id")
        if op == "journal_header":
            if n == 1 and isinstance(r.get("journal_id"), str) and r["journal_id"]:
                return ""
            return "journal_header record that is not a valid first record"
        if n == 1:
            return "first record is not a journal_header"
        if op == "journal_reset":
            if n == 2 and all(isinstance(r.get(k), str) and r[k].strip()
                              for k in ("actor", "reason")):
                return ""
            return "journal_reset record that does not directly follow the header"
        if not (isinstance(op_id, str) and op_id):
            return "record without op_id"
        if op == "rebind_pending":
            if op_id in pend:
                return "duplicate rebind op_id"
            seq = r.get("seq")
            if not (all(isinstance(r.get(k), str) and r[k].strip()
                        for k in ("agent_id", "plan_id", "incident_id",
                                  "actor", "reason"))
                    and isinstance(seq, int) and not isinstance(seq, bool)
                    and seq >= 0 and isinstance(r.get("stream_digest"), str)):
                return "rebind_pending record with missing or invalid fields"
            return ""
        if op == "rebind_commit":
            p = pend.get(op_id)
            if p is None:
                return "commit record names no earlier pending rebind"
            if op_id in done:
                return "duplicate commit record"
            if r.get("pending_hash") != p.get("rec_hash"):
                return "commit record does not match its pending rebind"
            return ""
        return f"unknown record op {op!r}"

    def _parse_journal(self, path: str, data: bytes) -> list[dict[str, Any]]:
        """Committed rebind entries in journal order, or [] with the WHOLE
        journal fenced if any record cannot be verified: an unreadable line,
        a hash mismatch, a broken chain (reorder/removal/insertion), a
        legacy-format record, a commit naming no earlier pending rebind, or
        an unterminated (torn) last line."""
        pend: dict[str, dict[str, Any]] = {}
        done: set[str] = set()
        tip, last, problem, jid = "", b"", None, ""
        lines = data.split(b"\n")
        torn = bool(data) and not data.endswith(b"\n")
        lines = lines[:-1]                      # after the final newline / torn
        for n, raw in enumerate(lines, 1):
            try:
                r = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                problem = (n, "unreadable line")
                break
            why = self._check_record(r, n, tip, pend, done)
            if why:
                problem = (n, why)
                break
            if r["op"] == "rebind_pending":
                pend[r["op_id"]] = r
            elif r["op"] == "rebind_commit":
                done.add(r["op_id"])
            elif r["op"] == "journal_header":
                jid = r["journal_id"]
            tip, last = r["rec_hash"], raw + b"\n"
        if problem is None and torn:
            problem = (len(lines) + 1, "unterminated (torn) last line")
        if problem is not None:
            n, why = problem
            self._journal_corrupt = [{"line": n, "why": why}]
            logger.critical("Rebind journal %s line %d: %s", path, n, why)
            for e in pend.values():
                self._mark_unapplied(e, f"journal fenced (line {n}: {why}); not "
                                        "replayed -- inspect, clear_journal_fence(), "
                                        "re-issue if still wanted")
            self._set_fence("corrupt", f"line {n}: {why}; no journaled rebind "
                            "is replayed", found_at_startup=True, line=n)
            return []
        self._set_journal_state(data, tip, last, len(lines), jid)
        out = []
        for op_id, e in pend.items():
            if op_id in done:
                out.append(e)
            else:
                self._mark_unapplied(e, "no commit record: the rebind was refused "
                                        "or its write did not complete; not replayed")
        return out

    def _verify_on_disk(self, fd: int) -> "tuple[int, Any]":
        """Astra 7694 F-runtime-integrity-overclaim: the identity anchor must
        still name this journal, and the journal must be byte-for-byte what
        this process last wrote or verified (size AND SHA-256 of the whole
        file, re-read).  Returns (size, sha256 object of the verified bytes);
        raises _JournalChanged."""
        try:
            anchor = self._read_anchor(self._journal_path)
        except (OSError, ValueError) as exc:
            raise _JournalChanged(f"identity anchor unreadable ({exc})") from exc
        if anchor != self._journal_id:
            raise _JournalChanged(f"identity anchor names journal {anchor}, not "
                                  f"{self._journal_id}: the journal was replaced")
        size = os.fstat(fd).st_size
        h, off = hashlib.sha256(), 0
        while off < size:
            b = os.pread(fd, min(1 << 20, size - off), off)
            if not b:
                break
            h.update(b)
            off += len(b)
        if size != self._journal_size or off != size or (
                h.hexdigest() != self._journal_sha):
            raise _JournalChanged(
                f"journal is {size} bytes, expected {self._journal_size}, or its "
                "content differs from what this process wrote: it was changed "
                "outside this process")
        return size, h

    def verify_journal(self) -> bool:
        """Astra 7694: re-verify the journal on disk now (anchor + full-file
        digest).  Fences it and returns False on any difference; True if
        healthy (or no journal is configured)."""
        if not self._journal_path:
            return True
        if self._journal_fence is not None:
            return False
        try:
            fd = os.open(self._journal_path, os.O_RDONLY)
        except OSError as exc:
            self._set_fence("changed", f"journal cannot be opened ({exc})")
            return False
        try:
            self._verify_on_disk(fd)
        except (_JournalChanged, OSError) as exc:
            self._set_fence("changed", f"verify_journal: {exc}")
            return False
        finally:
            os.close(fd)
        return True

    def _journal_write(self, rec: dict[str, Any]) -> None:
        """Append one chained record.  Returns only once it is durable.
        OSError: nothing of it is on disk (any partial write was rolled back
        and the rollback fsync'd).  _JournalIndeterminate: the rollback failed,
        so it may or may not survive (possibly torn).  _JournalChanged: the
        file is not what this process last wrote; nothing was written."""
        rec["prev"] = self._journal_tip
        rec["rec_hash"] = self._rec_hash(rec)
        data = (json.dumps(rec, sort_keys=True) + "\n").encode("utf-8")
        try:
            fd = os.open(self._journal_path, os.O_RDWR | os.O_APPEND)
        except FileNotFoundError as exc:
            raise _JournalChanged(f"journal file is missing ({exc})") from exc
        try:
            size, sha = self._verify_on_disk(fd)
            if size + len(data) > MAX_HIVE_JOURNAL_BYTES:
                raise OSError(f"rebind journal would exceed {MAX_HIVE_JOURNAL_BYTES} "
                              "bytes; rotate/compact it (admission refused)")
            try:
                self._write_all(fd, data)
                os.fsync(fd)
            except OSError as exc:
                try:
                    os.ftruncate(fd, size)
                    os.fsync(fd)
                except OSError as exc2:
                    raise _JournalIndeterminate(
                        f"{exc}; rollback failed: {exc2}") from exc2
                raise
        finally:
            try:
                os.close(fd)
            except OSError as exc:
                logger.warning("Rebind journal %s close error: %s",
                               self._journal_path, exc)
        self._journal_size += len(data)
        sha.update(data)
        self._journal_sha = sha.hexdigest()
        self._journal_tip = rec["rec_hash"]
        self._journal_last = data
        self._journal_records += 1

    def journal_pending(self) -> list[dict[str, Any]]:
        """Journaled rebinds whose event-stream position is not reached yet."""
        return copy.deepcopy(self._journal_pending)

    def journal_status(self) -> dict[str, Any]:
        """Astra 7638/7678: operator view of rebind durability.  healthy is
        False while the journal is fenced (fence says why)."""
        return copy.deepcopy({
            "path": self._journal_path,
            "durable": bool(self._journal_path),
            "journal_id": self._journal_id,
            "volatile_rebinds_allowed": self._volatile_rebinds,
            "healthy": self._journal_fence is None,
            "fence": self._journal_fence,
            "event_seq": self._event_seq,
            "pending": len(self._journal_pending),
            "unapplied": self._journal_unapplied[-MAX_HIVE_REBIND_RECORDS:],
            # Astra 7656: never silently truncated -- total and omitted count;
            # journal_unapplied() returns every retained disposition.
            "unapplied_total": self._journal_unapplied_total,
            "unapplied_omitted": self._journal_unapplied_total
            - min(len(self._journal_unapplied), MAX_HIVE_REBIND_RECORDS),
            "records": self._journal_records,
            "bytes": self._journal_size,
            "corrupt_records": self._journal_corrupt,
            "fence_clearances": self.journal_fence_clearances,
            "plans_refused_cap": self.plans_refused_cap})

    def journal_unapplied(self) -> list[dict[str, Any]]:
        """Astra 7656: every retained unapplied disposition (up to
        MAX_HIVE_UNAPPLIED_RECORDS; journal_status() lists the newest
        MAX_HIVE_REBIND_RECORDS and reports unapplied_total/omitted)."""
        return copy.deepcopy(self._journal_unapplied)

    def clear_journal_fence(self, actor: str, reason: str) -> bool:
        """Astra 7678: operator clearance of a fenced (unhealthy) journal.
        The old journal is preserved byte-for-byte as <journal>.fenced-<ns>
        (fsync'd), then atomically replaced by a new journal that starts with
        a journal_reset record and re-journals (pending + commit) exactly the
        rebinds this process holds applied or still awaiting their event
        position, so the state after a restart equals the running state.
        Rebinds in the old journal that this process did not apply are NOT
        carried over: re-issue them if still wanted.  Returns False if not
        fenced; raises OSError (journal stays fenced) on any failure."""
        if not (isinstance(actor, str) and actor.strip()):
            raise ValueError("clear_journal_fence requires a non-empty actor")
        if not (isinstance(reason, str) and reason.strip()):
            raise ValueError("clear_journal_fence requires a non-empty reason")
        fence = self._journal_fence
        if fence is None or not self._journal_path:
            return False
        path = self._journal_path
        stamp = time.time_ns()
        try:
            with open(path, "rb") as f:
                old: bytes | None = f.read()
        except FileNotFoundError:
            old = None
        archive = f"{path}.fenced-{stamp}" if old is not None else ""
        if old is not None:
            self._write_file_durably(archive, old)
        now = time.time()
        jid = uuid.uuid4().hex                 # Astra 7694: new identity
        hdr = self._header_record(jid)
        reset = {"v": JOURNAL_VERSION, "op": "journal_reset", "actor": actor,
                 "reason": reason, "ts": now, "fence_error": str(fence.get("error")),
                 "archived": archive, "archived_journal_id": self._journal_id,
                 "prev": hdr["rec_hash"]}
        reset["rec_hash"] = self._rec_hash(reset)
        recs, tip = [hdr, reset], reset["rec_hash"]
        for e in list(self._journal_applied) + list(self._journal_pending):
            pr = {k: v for k, v in e.items() if k not in ("prev", "rec_hash")}
            pr["prev"] = tip
            pr["rec_hash"] = tip = self._rec_hash(pr)
            cr = {"v": JOURNAL_VERSION, "op": "rebind_commit", "op_id": pr["op_id"],
                  "pending_hash": pr["rec_hash"], "ts": now, "prev": tip}
            cr["rec_hash"] = tip = self._rec_hash(cr)
            recs += [pr, cr]
        lines = [(json.dumps(r, sort_keys=True) + "\n").encode("utf-8") for r in recs]
        data = b"".join(lines)
        # A failure raises and the journal stays fenced.  A crash between the
        # journal rename and the anchor rename leaves a journal/anchor id
        # mismatch, which fences again at the next start (safe).
        self._replace_durably(path, data)
        self._write_anchor(path, jid)
        # Astra 7701: old fence files are moved aside (kept as evidence) only
        # after the new journal and anchor are durable; a crash before this
        # leaves them in place, which fences again at the next start (safe).
        for sfx in self.LEGACY_MARKER_SUFFIXES:
            lp = path + sfx
            if os.path.lexists(lp):
                os.replace(lp, f"{lp}.cleared-{stamp}")
                self._fsync_dir(lp)
        self._set_journal_state(data, tip, lines[-1], len(recs), jid)
        self._journal_corrupt = []
        self._journal_fence = None
        self.journal_fence_clearances.append(
            {"actor": actor, "reason": reason, "ts": now, "archived": archive,
             "fence_kind": fence.get("kind"), "fence_error": str(fence.get("error")),
             "journal_id": jid, "rebinds_rejournaled": (len(recs) - 2) // 2})
        del self.journal_fence_clearances[:-MAX_HIVE_REBIND_RECORDS]
        logger.warning("Rebind journal fence cleared by %s (%s): old journal "
                       "archived to %s, %d applied rebind(s) re-journaled",
                       actor, reason, archive or "<missing>", (len(recs) - 2) // 2)
        return True

    def _mark_unapplied(self, e: dict[str, Any], why: str) -> None:
        self._journal_unapplied_total += 1
        self._journal_unapplied.append({
            k: e.get(k) for k in ("op_id", "agent_id", "plan_id", "incident_id",
                                  "actor", "reason", "seq")} | {"why": why})
        del self._journal_unapplied[:-MAX_HIVE_UNAPPLIED_RECORDS]
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
                    self._journal_applied.append(e)
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
                          allow_non_candidate: bool = False) -> RebindResult:
        """Operator owner rebind; see _rebind_plan_owner() for the contract.
        Astra 7694: returns a RebindResult -- "applied" (truthy; durable when
        a journal is configured), "refused" (falsy) or "uncertain" (falsy:
        applied in memory, commit durability unknown, journal fenced)."""
        self._rebind_op_id = ""
        r = self._rebind_plan_owner(agent_id, plan_id, incident_id, actor=actor,
                                    reason=reason,
                                    allow_non_candidate=allow_non_candidate)
        if not isinstance(r, RebindResult):
            if r:
                r = RebindResult(
                    "applied", applied=True, durable=bool(self._journal_path),
                    op_id=self._rebind_op_id,
                    detail="pending and commit records fsync'd" if self._journal_path
                    else "volatile_rebinds: not journaled, lost on restart")
            else:
                r = RebindResult("refused", applied=False, durable=False,
                                 op_id=self._rebind_op_id,
                                 detail="refused; see log and journal_status()")
        self.last_rebind_result = r
        return r

    def _rebind_plan_owner(self, agent_id: str, plan_id: str, incident_id: str,
                           *, actor: str, reason: str,
                           allow_non_candidate: bool = False
                           ) -> "bool | RebindResult":
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
            if self._journal_fence is not None:
                logger.error("Refused hive rebind of %s:%s -> %s: rebind journal "
                             "is fenced (%s); inspect it, then clear_journal_fence()",
                             agent_id, plan_id, incident_id,
                             self._journal_fence.get("error"))
                return False
            # Astra 7678: pending record, then commit record.  Only a rebind
            # with a durable commit can replay after a restart.
            entry = {"v": JOURNAL_VERSION, "op": "rebind_pending",
                     "op_id": uuid.uuid4().hex,
                     "agent_id": agent_id, "plan_id": plan_id,
                     "incident_id": incident_id, "actor": actor,
                     "reason": reason, "ts": time.time(),
                     "seq": self._event_seq,
                     "stream_digest": self._stream_digest,
                     "candidate": incident_id in self.owner_candidates.get(
                         f"{agent_id}:{plan_id}", [])}
            what = f"{agent_id}:{plan_id} -> {incident_id}"
            self._rebind_op_id = entry["op_id"]
            for step in ("pending", "commit"):
                rec = entry if step == "pending" else {
                    "v": JOURNAL_VERSION, "op": "rebind_commit",
                    "op_id": entry["op_id"], "pending_hash": entry["rec_hash"],
                    "ts": time.time()}
                try:
                    self._journal_write(rec)
                except _JournalChanged as exc:
                    self._set_fence("changed", f"{exc}; rebind {what} refused "
                                    "(nothing written)", op_id=entry["op_id"],
                                    applied=False)
                    return False
                except _JournalIndeterminate as exc:
                    if step == "pending":
                        # No commit exists, so it can never replay: the refusal
                        # is truthful.  The tail may be torn -> fenced.
                        self._set_fence(
                            "write_failure", f"pending record write failed and "
                            f"its rollback failed ({exc}); rebind {what} refused "
                            "(it has no commit record, so it never replays); the "
                            "journal tail may be torn", op_id=entry["op_id"],
                            applied=False)
                        return False
                    # The commit MAY be durable, so a restart may replay it.
                    # Never report a refusal a restart could contradict, nor a
                    # durable success it may not honour (Astra 7694): apply it
                    # in memory, fence, and return an explicit UNCERTAIN.
                    self._do_rebind(agent_id, plan_id, incident_id, inc,
                                    actor=actor, reason=reason)
                    self._journal_applied.append(entry)
                    self._set_fence(
                        "commit_uncertain", f"rebind {what} APPLIED but its commit "
                        f"record may not be durable ({exc}): after a restart it "
                        "is either replayed or the plan is held again",
                        op_id=entry["op_id"], applied=True, durable=None)
                    return RebindResult(
                        "uncertain", applied=True, durable=None,
                        op_id=entry["op_id"],
                        detail=f"applied in memory; commit record durability "
                        f"unknown ({exc}); journal fenced; after a restart it "
                        "is replayed or the plan is held again")
                except OSError as exc:
                    logger.error("Refused hive rebind of %s: %s record write "
                                 "failed and was rolled back durably (%s)%s", what,
                                 step, exc, "; the pending record has no commit "
                                 "and is never replayed" if step == "commit" else "")
                    return False
            self._journal_applied.append(entry)
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
        if key not in self._plan_steps and len(self._plan_steps) >= MAX_HIVE_PLANS:
            # Astra 7656 (Low): overall admission cap on tracked plans.  The
            # PLAN is refused (fail-closed: its incident stays OPEN; nothing
            # already tracked or held is dropped).
            self.plans_refused_cap += 1
            logger.error("PLAN %s from %s refused: hive tracks MAX_HIVE_PLANS=%d "
                         "plans; its incident stays open", plan_id, agent_id,
                         MAX_HIVE_PLANS)
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
