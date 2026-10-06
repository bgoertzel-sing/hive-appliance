"""Astra 7160: H2 late INCIDENT after all successes, N9 rebind trust boundary,
N10 bounded migration diagnostics; local/hive agreement now also compares step
sets, failed sets and hive health after every event.
"""
import json

import pytest

from controller.reducer import Reducer, MAX_DIAG_ENTRIES
from hive.reducer import HiveReducer
from hive.types import AgentHealth, HiveEvent
from schemas.types import Event, EventKind, IncidentReport


def ev(kind, payload):
    return Event(kind=kind, source="t", subject="svc", payload=payload)


def INC(i):
    return ev(EventKind.INCIDENT, IncidentReport(id=i, component="svc", symptom="down").to_dict())


def PLAN(pid, iid, n):
    return ev(EventKind.PLAN, {"id": pid, "incident_id": iid, "steps": [{"verb": "v"}] * n})


def RC(rid, plan_id="", idx=0, ok=True, incident_id=""):
    p = {"id": rid, "step_index": idx, "verified": ok}
    if plan_id:
        p["plan_id"] = plan_id
    if incident_id:
        p["incident_id"] = incident_id
    return ev(EventKind.RECEIPT, p)


def lo(r):
    return sorted(i.id for i in r.open_incidents())


def ho(h):
    return sorted(i["incident_id"] for i in h._open_agent_incidents("a1"))


_SEV_FAILED = ("critical", "error")


def expected_health(loc, prev):
    """Independent health oracle (Astra 7195 follow-up 2), derived from the
    LOCAL reducer's incidents and severities, never from hive state:
      - UNKNOWN until the first open incident;
      - FAILED while any open incident is error/critical;
      - otherwise DEGRADED while any incident is open (H1 contract: an earlier
        FAILED is not de-escalated while incidents remain open);
      - HEALTHY once every incident is closed after a DEGRADED/FAILED period
        (including an incident opened and closed by the same event).
    """
    opened = [i for i in loc.incidents if not i.resolved]
    sev = [getattr(i.severity, "value", i.severity) for i in opened]
    if any(s in _SEV_FAILED for s in sev):
        return AgentHealth.FAILED
    if opened:
        return AgentHealth.FAILED if prev == AgentHealth.FAILED else AgentHealth.DEGRADED
    # An incident reported and closed within the SAME event (late INCIDENT
    # after all successes, H2) still had an open period: hive marks it
    # DEGRADED on append, then HEALTHY on resolution.
    if prev in (AgentHealth.DEGRADED, AgentHealth.FAILED) or loc.incidents:
        return AgentHealth.HEALTHY
    return prev


def agree(loc, hive, plans, prev=AgentHealth.UNKNOWN):
    """Assert local/hive agreement on open IDs/counts, verified and failed step
    sets, AND hive health against the independent oracle.  Returns the
    expected health (thread it into the next call as prev)."""
    assert lo(loc) == ho(hive)
    assert hive.state.agents["a1"].open_incidents == len(lo(loc))
    for p in plans:
        assert set(loc._plan_verified.get(p, set())) == set(hive._plan_verified_steps.get("a1:" + p, set())), p
        assert set(loc._plan_failed_steps.get(p, set())) == set(hive._plan_failed.get("a1:" + p, set())), p
    exp = expected_health(loc, prev)
    got = hive.state.agents["a1"].health
    assert got == exp, f"health mismatch: hive={got} expected={exp}"
    return exp


def both(stream, plans=("p",)):
    loc, hive = Reducer(), HiveReducer()
    hive.register_agent("a1")
    health = agree(loc, hive, plans)          # UNKNOWN before any event
    for e in stream:
        loc.reduce(e)
        hive.reduce(HiveEvent(source_agent="a1", original_event=e))
        health = agree(loc, hive, plans, health)
    return loc, hive


def test_h2_late_incident_after_all_successes_closes_immediately():
    loc, hive = both([PLAN("p", "i", 2), RC("a", "p", 0), RC("b", "p", 1), INC("i")])
    assert lo(loc) == [] and ho(hive) == []
    assert hive.state.agents["a1"].open_incidents == 0


def test_h2_late_incident_every_snapshot_boundary():
    stream = [PLAN("p", "i", 2), RC("a", "p", 0), RC("b", "p", 1), INC("i")]
    for cut in range(len(stream) + 1):
        r = Reducer()
        for e in stream[:cut]:
            r.reduce(e)
        for _ in range(2):
            r2 = Reducer()
            r2.restore_snapshot(json.loads(json.dumps(r.snapshot())))
            r = r2
        for e in stream[cut:]:
            r.reduce(e)
        assert lo(r) == [], cut


def test_h2_late_incident_with_failure_stays_open():
    loc, hive = both([PLAN("p", "i", 2), RC("a", "p", 0), RC("f", "p", 0, ok=False),
                      RC("b", "p", 1), INC("i")])
    assert lo(loc) == ["i"] and ho(hive) == ["i"]


def test_h2_unrelated_late_incident_not_closed():
    loc, hive = both([PLAN("p", "i", 1), RC("a", "p", 0), INC("i"), INC("j")])
    assert lo(loc) == ["j"] and ho(hive) == ["j"]


def _lost_owner_snapshot(resolve_other=False):
    r = Reducer()
    for e in (PLAN("p", "i", 2), INC("i"), INC("other")):
        r.reduce(e)
    snap = json.loads(json.dumps(r.snapshot()))
    for k in ("plan_owner", "owner_unproven", "migration_diagnostics"):
        snap.pop(k, None)
    for inc in snap["incidents"]:
        inc["plan_id"] = ""
        if resolve_other and inc["id"] == "other":
            inc["resolved"] = True
    r = Reducer()
    r.restore_snapshot(snap)
    return r


def test_n9_rebind_requires_actor_and_reason():
    r = _lost_owner_snapshot()
    with pytest.raises(TypeError):
        r.rebind_plan_owner("p", "i")
    with pytest.raises(ValueError):
        r.rebind_plan_owner("p", "i", actor="", reason="x", allow_non_candidate=True)
    with pytest.raises(ValueError):
        r.rebind_plan_owner("p", "i", actor="op", reason="  ", allow_non_candidate=True)
    assert "p" in r._owner_unproven


def test_n9_rebind_refuses_resolved_target():
    r = _lost_owner_snapshot(resolve_other=True)
    assert not r.rebind_plan_owner("p", "other", actor="op", reason="x", allow_non_candidate=True)
    pv = r.preview_rebind("p", "other", allow_non_candidate=True)
    assert not pv["allowed"] and "resolved" in pv["refusal"]
    assert "p" in r._owner_unproven


def test_n9_rebind_refuses_non_candidate_without_override():
    r = _lost_owner_snapshot()
    r.reduce(PLAN("p", "other", 2))                    # proposes candidate "other"
    assert r.migration_diagnostics["owner_candidates"]["p"] == ["other"]
    assert not r.rebind_plan_owner("p", "i", actor="op", reason="x")
    assert "p" in r._owner_unproven
    assert r.rebind_plan_owner("p", "other", actor="op", reason="verified in logs")
    rec = r.migration_diagnostics["owner_rebinds"][-1]
    assert rec["actor"] == "op" and rec["reason"] == "verified in logs" and rec["candidate"] is True
    assert r._plan_owner["p"] == "other"


def test_n9_override_is_recorded_as_non_candidate():
    r = _lost_owner_snapshot()
    assert r.rebind_plan_owner("p", "i", actor="op", reason="x", allow_non_candidate=True)
    assert r.migration_diagnostics["owner_rebinds"][-1]["candidate"] is False


def test_n9_preview_is_side_effect_free_and_reports_evidence():
    r = _lost_owner_snapshot()
    r.reduce(RC("a", "p", 0))
    r.reduce(RC("b", "p", 1))
    before = json.dumps(r.snapshot(), sort_keys=True, default=str)
    pv = r.preview_rebind("p", "i", allow_non_candidate=True)
    assert json.dumps(r.snapshot(), sort_keys=True, default=str) == before
    assert pv["allowed"] and sorted(h["id"] for h in pv["held_receipts"]) == ["a", "b"]
    assert pv["would_close"] == ["i"]
    assert lo(r) == ["i", "other"]
    assert r.rebind_plan_owner("p", "i", actor="op", reason="x", allow_non_candidate=True)
    assert lo(r) == ["other"]
    assert r.migration_diagnostics["owner_rebinds"][-1]["closed"] == ["i"]


def test_n10_ownerless_and_candidate_histories_bounded():
    n = MAX_DIAG_ENTRIES + 44
    r = Reducer()
    for k in range(n):
        r.reduce(PLAN(f"p{k}", f"i{k}", 1))
    snap = json.loads(json.dumps(r.snapshot()))
    for k in ("plan_owner", "owner_unproven", "migration_diagnostics"):
        snap.pop(k, None)
    r = Reducer()
    r.restore_snapshot(snap)
    d = r.migration_diagnostics
    assert len(r._owner_unproven) == n
    assert len(d["legacy_ownerless_plans"]) == MAX_DIAG_ENTRIES
    assert d["legacy_ownerless_total"] == n
    for k in range(n):
        r.reduce(PLAN(f"p{k}", f"x{k}", 1))
    assert len(d["owner_candidates"]) == MAX_DIAG_ENTRIES
    assert d["owner_candidates_dropped"] == 44
    r2 = Reducer()
    r2.restore_snapshot(json.loads(json.dumps(r.snapshot())))
    assert len(r2._owner_unproven) == n
    assert len(r2.migration_diagnostics["legacy_ownerless_plans"]) == MAX_DIAG_ENTRIES


def test_n10_stale_warning_text_removed():
    import controller.reducer as m
    src = open(m.__file__).read()
    assert "a PLAN re-establishes the owner" not in src
    assert "until a PLAN re-establishes" not in src
