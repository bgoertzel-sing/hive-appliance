"""Astra 7173: N9 preview/audit account for EVERY drained receipt, preview
output is detached, N10 caps enforced on restore of upgraded diagnostics."""
import copy
import json

from controller.reducer import Reducer, MAX_DIAG_ENTRIES
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


def rt(r):
    r2 = Reducer()
    r2.restore_snapshot(json.loads(json.dumps(r.snapshot())))
    return r2


def _legacy(link):
    r = Reducer()
    for e in (PLAN("p", "i", 2), INC("i"), INC("other")):
        r.reduce(e)
    snap = json.loads(json.dumps(r.snapshot()))
    for k in ("plan_owner", "owner_unproven", "migration_diagnostics"):
        snap.pop(k, None)
    for inc in snap["incidents"]:
        inc["plan_id"] = link
    r = Reducer()
    r.restore_snapshot(snap)
    assert "p" in r._owner_unproven
    return r


W = ["valid", "invalid_index", "contradictory", "other_link_failure"]


def _astra_witness():
    r = _legacy("p")                       # ambiguous: i AND other linked to p
    for e in (RC("valid", "p", 0), RC("invalid_index", "p", 99),
              RC("contradictory", "p", 1, incident_id="other"),
              RC("other_link_failure", idx=0, ok=False, incident_id="other")):
        r.reduce(e)
    assert sorted(r._pending_receipts) == sorted(W)
    return r


def ids(effects):
    return {k: sorted(x["id"] for x in v) for k, v in effects.items()}


def test_n9_preview_accounts_for_every_drained_receipt():
    r = _astra_witness()
    before = json.dumps(r.snapshot(), sort_keys=True, default=str)
    pv = r.preview_rebind("p", "i", allow_non_candidate=True)
    assert json.dumps(r.snapshot(), sort_keys=True, default=str) == before
    assert pv["allowed"]
    e = ids(pv["effects"])
    assert e["credited"] == ["valid"]
    assert e["consumed_no_effect"] == ["contradictory", "invalid_index", "other_link_failure"]
    assert e["failure_recorded"] == [] and e["still_held"] == []
    assert sum(pv["effect_counts"].values()) == 4
    assert pv["would_close"] == []


def test_n9_audit_matches_actual_drain_and_preview():
    r = _astra_witness()
    pv = r.preview_rebind("p", "i", allow_non_candidate=True)
    assert r.rebind_plan_owner("p", "i", actor="op", reason="x", allow_non_candidate=True)
    rec = r.migration_diagnostics["owner_rebinds"][-1]
    assert "held_receipts" not in rec
    assert rec["pending_before"] == 4
    assert rec["effect_counts"] == pv["effect_counts"]
    assert {k: sorted(v) for k, v in rec["effect_ids"].items()} == ids(pv["effects"])
    assert r._pending_receipts == {}
    assert r._plan_verified["p"] == {0}
    assert lo(r) == ["i", "other"] and rec["closed"] == []
    rec2 = rt(r).migration_diagnostics["owner_rebinds"][-1]
    assert rec2["effect_counts"] == rec["effect_counts"]


def test_n9_failure_and_still_held_are_distinguished():
    r = _legacy("")
    r.reduce(RC("a", "p", 0))
    r.reduce(RC("f", idx=1, ok=False, incident_id="i"))
    r.reduce(RC("q", "unknown_plan", 0))
    pv = r.preview_rebind("p", "i", allow_non_candidate=True)
    e = ids(pv["effects"])
    assert e["credited"] == ["a"] and e["failure_recorded"] == ["f"]
    assert e["still_held"] == ["q"] and e["consumed_no_effect"] == []
    assert r.rebind_plan_owner("p", "i", actor="op", reason="x", allow_non_candidate=True)
    rec = r.migration_diagnostics["owner_rebinds"][-1]
    assert rec["effect_counts"] == pv["effect_counts"]
    assert list(r._pending_receipts) == ["q"]
    assert lo(r) == ["i", "other"]


def test_n9_preview_output_is_detached():
    r = _legacy("")
    r.reduce(ev(EventKind.RECEIPT, {"id": "m", "plan_id": "p",
                                    "step_index": {"x": [1]}, "verified": {"v": [1]}}))
    assert "m" in r._pending_receipts
    before = copy.deepcopy(r._pending_receipts)
    pv = r.preview_rebind("p", "i", allow_non_candidate=True)
    rows = list(pv["held_receipts"]) + [x for v in pv["effects"].values() for x in v]
    assert rows
    for h in rows:
        if isinstance(h["step_index"], dict):
            h["step_index"]["x"].append(2)
            h["step_index"]["y"] = 1
        if isinstance(h["verified"], dict):
            h["verified"]["v"].append(9)
    pv["candidates"].append("zzz")
    assert r._pending_receipts == before
    assert "zzz" not in (r.migration_diagnostics.get("owner_candidates") or {}).get("p", [])


def _upgraded_snapshot(n):
    r = Reducer()
    r.reduce(INC("i"))
    snap = json.loads(json.dumps(r.snapshot()))
    assert "plan_owner" in snap                    # current (ef18db3) format
    snap["owner_unproven"] = [f"p{k}" for k in range(n)]
    cands = {f"p{k}": ["i"] for k in range(n)}
    cands.update({f"z{k}": ["i"] for k in range(10)})
    snap["migration_diagnostics"] = {
        "legacy_ownerless_plans": [f"p{k}" for k in range(n)],
        "owner_candidates": cands,
        "owner_rebinds": [{"plan_id": f"r{k}", "incident_id": "i", "actor": "op",
                           "reason": "x"} for k in range(n)],
    }
    return snap


def test_n10_upgraded_diagnostics_capped_on_restore_and_stable():
    n = MAX_DIAG_ENTRIES + 44
    r = Reducer()
    r.restore_snapshot(_upgraded_snapshot(n))
    for _ in range(21):
        d = r.migration_diagnostics
        assert len(r._owner_unproven) == n             # never capped
        assert len(d["legacy_ownerless_plans"]) == MAX_DIAG_ENTRIES
        assert d["legacy_ownerless_total"] == n
        assert len(d["owner_rebinds"]) == MAX_DIAG_ENTRIES
        assert d["owner_rebinds"][-1]["plan_id"] == f"r{n - 1}"   # newest kept
        assert d["owner_rebinds_total"] == n
        assert len(d["owner_candidates"]) == MAX_DIAG_ENTRIES
        assert all(k in r._owner_unproven for k in d["owner_candidates"])  # quarantined first
        assert d["owner_candidates_dropped"] == n + 10 - MAX_DIAG_ENTRIES
        r = rt(r)


def test_n10_rebind_total_continues_after_upgrade():
    n = MAX_DIAG_ENTRIES + 44
    snap = _upgraded_snapshot(n)
    r = Reducer()
    r.restore_snapshot(snap)
    r._plan_step_counts["p0"] = 1
    r._plan_verified.setdefault("p0", set())
    r._plan_failed_steps.setdefault("p0", set())
    assert r.rebind_plan_owner("p0", "i", actor="op", reason="x")
    d = r.migration_diagnostics
    assert d["owner_rebinds_total"] == n + 1
    assert len(d["owner_rebinds"]) == MAX_DIAG_ENTRIES
