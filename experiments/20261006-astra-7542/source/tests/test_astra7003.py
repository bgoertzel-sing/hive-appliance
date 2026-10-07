"""Tests for Astra re-review 7003 at 44aaef8: N3 (buffered failure vs hive
completion) and N4 (contradictory incident identity). Every stream is run
through BOTH reducers with agreement asserted after every event."""
from __future__ import annotations

from controller.reducer import Reducer
from hive.reducer import HiveReducer
from hive.types import AgentHealth, HiveEvent
from schemas.types import Event, EventKind, IncidentReport


def _ev(kind, payload):
    return Event(kind=kind, source="t", subject="svc", payload=payload)


def _inc(iid):
    return _ev(EventKind.INCIDENT, IncidentReport(id=iid, component="svc",
                                                  symptom="down").to_dict())


def _plan(pid, iid, n):
    return _ev(EventKind.PLAN, {"id": pid, "incident_id": iid,
                                "steps": [{"verb": "v"}] * n})


def _rc(rid, plan_id="", idx=0, ok=True, incident_id=""):
    p = {"id": rid, "step_index": idx, "verified": ok}
    if plan_id:
        p["plan_id"] = plan_id
    if incident_id:
        p["incident_id"] = incident_id
    return _ev(EventKind.RECEIPT, p)


def _run(stream, loc=None, hive=None):
    loc = loc or Reducer()
    if hive is None:
        hive = HiveReducer()
        hive.register_agent("a1")
    counts = []
    for n, e in enumerate(stream):
        loc.reduce(e)
        hive.reduce(HiveEvent(source_agent="a1", original_event=e))
        lo = len(loc.open_incidents())
        hi = len(hive._open_agent_incidents("a1"))
        assert lo == hi, f"disagree after event {n}: local={lo} hive={hi}"
        assert hive.state.agents["a1"].open_incidents == hi
        counts.append(lo)
    return loc, hive, counts


# ------------------------------------------------------------------ N3
def test_n3_buffered_failure_after_successes_keeps_both_open():
    loc, hive, counts = _run([
        _inc("i"), _rc("r0", "p", 0), _rc("r1", "p", 1), _rc("rf", "p", 0, ok=False),
        _plan("p", "i", 2)])
    assert counts == [1, 1, 1, 1, 1]
    assert hive.state.agents["a1"].health != AgentHealth.HEALTHY
    # a fresh verified retry of step 0 closes both, exactly once
    _, _, c2 = _run([_rc("r0b", "p", 0)], loc, hive)
    assert c2 == [0]
    assert hive.state.agents["a1"].health == AgentHealth.HEALTHY


def test_n3_failure_then_success_buffer_latest_wins():
    _, _, counts = _run([
        _inc("i"), _rc("rf", "p", 0, ok=False), _rc("r0", "p", 0), _rc("r1", "p", 1),
        _plan("p", "i", 2)])
    assert counts == [1, 1, 1, 1, 0]


def test_n3_replayed_buffered_failure_ignored_after_retry():
    loc, hive, counts = _run([
        _inc("i"), _rc("rf", "p", 0, ok=False), _plan("p", "i", 2),
        _rc("r1", "p", 1), _rc("r0", "p", 0), _rc("rf", "p", 0, ok=False)])
    assert counts == [1, 1, 1, 1, 0, 0]


# ------------------------------------------------------------------ N4
def _two_plans():
    return [_inc("i"), _inc("other"), _plan("p", "i", 2), _plan("q", "other", 1)]


def test_n4_contradictory_identity_rejected_in_both():
    loc, hive, counts = _run(_two_plans() + [
        _rc("a", "p", 0), _rc("x", "p", 1, incident_id="other")])
    assert counts[-1] == 2
    # the contradictory receipt did not count; a clean step-1 receipt does
    _, _, c2 = _run([_rc("b", "p", 1)], loc, hive)
    assert c2 == [1]
    assert [i.id for i in loc.open_incidents()] == ["other"]


def test_n4_contradiction_buffered_before_plan_rejected_in_both():
    _, _, counts = _run([
        _inc("i"), _inc("other"), _plan("q", "other", 1),
        _rc("a", "p", 0), _rc("x", "p", 1, incident_id="other"),
        _plan("p", "i", 2)])
    assert counts[-1] == 2


def test_n4_consistent_incident_id_counts_in_both():
    _, _, counts = _run(_two_plans() + [
        _rc("a", "p", 0, incident_id="i"), _rc("b", "p", 1, incident_id="i")])
    assert counts[-1] == 1


def test_n4_incident_only_receipt_linked_and_buffered_agree():
    # linked incident: plan derived from the incident
    _, _, c1 = _run([_inc("i"), _plan("p", "i", 1), _rc("a", idx=0, incident_id="i")])
    assert c1[-1] == 0
    # unlinked incident: buffered until its PLAN links it, then applied
    _, _, c2 = _run([_inc("i"), _rc("a", idx=0, incident_id="i"), _plan("p", "i", 1)])
    assert c2 == [1, 1, 0]


def test_n4_local_snapshot_keeps_incident_only_buffer():
    loc = Reducer()
    for e in [_inc("i"), _rc("a", idx=0, incident_id="i")]:
        loc.reduce(e)
    r2 = Reducer()
    r2.restore_snapshot(loc.snapshot())
    r2.reduce(_plan("p", "i", 1))
    assert r2.open_incidents() == []
