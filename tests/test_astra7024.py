"""Tests for Astra re-review 7024 at e6afe16: N5 (local buffer loses arrival
order across plan-/incident-addressed receipts) and N4 residual (rejection
timing depended on unrelated incident lifecycle). Every stream runs through
BOTH reducers; open-incident identities and step sets are compared after
every event."""
from __future__ import annotations

import itertools
import json

import pytest

from controller.reducer import Reducer
from hive.reducer import HiveReducer
from hive.types import HiveEvent
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


def _new():
    h = HiveReducer()
    h.register_agent("a1")
    return Reducer(), h


def _open_ids(loc, hive):
    lo = sorted(i.id for i in loc.open_incidents())
    hi = sorted(i["incident_id"] for i in hive._open_agent_incidents("a1"))
    return lo, hi


def _steps(loc, hive, pid):
    return ((sorted(loc._plan_verified.get(pid, ())),
             sorted(loc._plan_failed_steps.get(pid, ()))),
            (sorted(hive._plan_verified_steps.get("a1:" + pid, ())),
             sorted(hive._plan_failed.get("a1:" + pid, ()))))


def _run(stream, loc=None, hive=None, plans=("p",), snapshot_at=None):
    if loc is None:
        loc, hive = _new()
    trace = []
    for n, e in enumerate(stream):
        if snapshot_at is not None and n == snapshot_at:
            r2 = Reducer()
            r2.restore_snapshot(json.loads(json.dumps(loc.snapshot())))
            loc = r2
        loc.reduce(e)
        hive.reduce(HiveEvent(source_agent="a1", original_event=e))
        lo, hi = _open_ids(loc, hive)
        assert lo == hi, f"open disagree after event {n}: local={lo} hive={hi}"
        assert hive.state.agents["a1"].open_incidents == len(hi)
        for pid in plans:
            ls, hs = _steps(loc, hive, pid)
            assert ls == hs, f"steps disagree for {pid} after event {n}: {ls} vs {hs}"
        trace.append(lo)
    return loc, hive, trace


# ------------------------------------------------------------------ N5
@pytest.mark.parametrize("snap", [None, 4])
def test_n5_early_incident_success_late_plan_failure_stays_open(snap):
    loc, hive, tr = _run([
        _inc("i"), _rc("is", idx=0, incident_id="i"), _rc("pf", "p", 0, ok=False),
        _rc("r1", "p", 1), _plan("p", "i", 2)], snapshot_at=snap)
    assert tr[-1] == ["i"]
    assert _steps(loc, hive, "p")[0] == ([1], [0])
    _, _, tr2 = _run([_rc("r0b", "p", 0)], loc, hive)
    assert tr2 == [[]]


def test_n5_early_incident_failure_late_plan_success_resolves():
    _, _, tr = _run([
        _inc("i"), _rc("if", idx=0, ok=False, incident_id="i"), _rc("ps", "p", 0),
        _rc("r1", "p", 1), _plan("p", "i", 2)])
    assert tr[-1] == []


def _systematic_cases():
    base = [(0, True), (0, False), (1, True), (1, False)]
    for order in itertools.permutations(range(4)):
        for addr in itertools.product((0, 1), repeat=4):
            yield order, addr, base


def test_n5_systematic_mixed_address_orderings_agree_with_latest_wins():
    n_cases = 0
    for order, addr, base in _systematic_cases():
        stream = [_inc("i")]
        latest = {}
        for k, j in enumerate(order):
            idx, ok = base[j]
            if addr[j]:
                stream.append(_rc(f"r{j}", idx=idx, ok=ok, incident_id="i"))
            else:
                stream.append(_rc(f"r{j}", "p", idx, ok=ok))
            latest[idx] = ok
        stream.append(_plan("p", "i", 2))
        loc, hive, tr = _run(stream)
        expect_open = [] if all(latest.values()) else ["i"]
        assert tr[-1] == expect_open, (order, addr)
        ver = sorted(i for i, ok in latest.items() if ok)
        fail = sorted(i for i, ok in latest.items() if not ok)
        assert _steps(loc, hive, "p")[0] == (ver, fail), (order, addr)
        n_cases += 1
    assert n_cases == 384


# ------------------------------------------------------------------ N4 residual
def _n4_residual():
    return [_inc("i"), _inc("other"),
            _rc("bad", "p", 0, incident_id="other"), _rc("good", "p", 1),
            _plan("q", "other", 1), _rc("q0", "q", 0), _plan("p", "i", 2)]


@pytest.mark.parametrize("snap", [None, 6])
def test_n4_buffered_contradiction_rejected_even_after_other_resolves(snap):
    loc, hive, tr = _run(_n4_residual(), plans=("p", "q"), snapshot_at=snap)
    assert tr[-1] == ["i"]
    assert _steps(loc, hive, "p")[0] == ([1], [])
    _, _, tr2 = _run([_rc("p0", "p", 0)], loc, hive, plans=("p", "q"))
    assert tr2 == [[]]


def test_n4_contradiction_arriving_after_plan_q_rejected_control():
    _, _, tr = _run([_inc("i"), _inc("other"), _plan("q", "other", 1),
                     _rc("bad", "p", 0, incident_id="other"), _rc("good", "p", 1),
                     _rc("q0", "q", 0), _plan("p", "i", 2)], plans=("p", "q"))
    assert tr[-1] == ["i"]


def test_legacy_bucketed_pending_snapshot_restores():
    loc = Reducer()
    loc.reduce(_inc("i"))
    snap = json.loads(json.dumps(loc.snapshot()))
    snap["pending_receipts"] = {
        "p": {"r0": {"id": "r0", "plan_id": "p", "step_index": 0, "verified": True}},
        "@inc:i": {"r1": {"id": "r1", "incident_id": "i", "step_index": 1,
                          "verified": True}}}
    r2 = Reducer()
    r2.restore_snapshot(snap)
    r2.reduce(_plan("p", "i", 2))
    assert r2.open_incidents() == []
