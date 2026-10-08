"""Astra 7195 follow-ups:
1. recovery guidance names owner_unproven as the authoritative current
   quarantine (legacy_ownerless_plans = capped historical sample), correct
   before and after rebinding with more than MAX_DIAG_ENTRIES held plans;
2. agree()/both() really assert hive health (incl. UNKNOWN before the first
   incident) and catch a health-only regression;
3. multi-plan policy (Ben, 2026-10-06): ANY complete owned plan closes the
   incident, even if a sibling plan for the same incident failed.
"""
import json

import pytest

from controller.reducer import Reducer, MAX_DIAG_ENTRIES
from hive.reducer import HiveReducer
from hive.types import AgentHealth
from schemas.types import Event, EventKind, IncidentReport, Severity
from tests.test_astra7160 import INC, PLAN, RC, both, ho, lo


def ev(kind, payload):
    return Event(kind=kind, source="t", subject="svc", payload=payload)


def INCs(i, sev):
    return ev(EventKind.INCIDENT,
              IncidentReport(id=i, component="svc", symptom="down", severity=sev).to_dict())


def rt(r):
    r2 = Reducer()
    r2.restore_snapshot(json.loads(json.dumps(r.snapshot())))
    return r2


# ------------------------------------------------------------ follow-up 1
def _many_quarantined(n):
    r = Reducer()
    for k in range(n):
        r.reduce(PLAN(f"p{k}", f"i{k}", 1))
        r.reduce(INC(f"i{k}"))
    snap = json.loads(json.dumps(r.snapshot()))
    for k in ("plan_owner", "owner_unproven", "migration_diagnostics"):
        snap.pop(k, None)
    for inc in snap["incidents"]:
        inc["plan_id"] = ""
    r = Reducer()
    r.restore_snapshot(snap)
    return r


def _guidance_ok(rec):
    assert "authoritative CURRENT quarantine is owner_unproven" in rec
    assert "quarantined_plans()" in rec
    assert "HISTORICAL SAMPLE" in rec
    assert "legacy_ownerless_plans stay quarantined" not in rec
    assert "Plans in legacy_ownerless_plans" not in rec


def test_recovery_guidance_names_owner_unproven_before_and_after_rebind():
    n = MAX_DIAG_ENTRIES + 44
    r = _many_quarantined(n)
    d = r.migration_diagnostics
    _guidance_ok(d["recovery"])
    assert len(r.quarantined_plans()) == n                # all 300 held
    assert len(d["legacy_ownerless_plans"]) == MAX_DIAG_ENTRIES
    r = rt(r)
    _guidance_ok(r.migration_diagnostics["recovery"])
    assert len(r.quarantined_plans()) == n
    for k in range(n):
        assert r.rebind_plan_owner(f"p{k}", f"i{k}", actor="op", reason="x",
                                   allow_non_candidate=True)
    assert r.quarantined_plans() == []
    for _ in range(3):
        r = rt(r)
        d = r.migration_diagnostics
        _guidance_ok(d["recovery"])
        assert r.quarantined_plans() == []
        # the sample is historical: it still lists 256 though nothing is held
        assert len(d["legacy_ownerless_plans"]) == MAX_DIAG_ENTRIES
        assert d["legacy_ownerless_total"] == n


def test_old_persisted_recovery_text_is_replaced_on_restore():
    r = _many_quarantined(3)
    snap = json.loads(json.dumps(r.snapshot()))
    snap["migration_diagnostics"]["recovery"] = (
        "Plans in legacy_ownerless_plans stay quarantined until an operator ...")
    r2 = Reducer()
    r2.restore_snapshot(snap)
    _guidance_ok(r2.migration_diagnostics["recovery"])
    assert r2.quarantined_plans() == ["p0", "p1", "p2"]


# ------------------------------------------------------------ follow-up 2
def _hive_health(stream):
    loc, hive = Reducer(), HiveReducer()
    hive.register_agent("a1")
    out = [hive.state.agents["a1"].health]
    for e in stream:
        loc.reduce(e)
        from hive.types import HiveEvent
        hive.reduce(HiveEvent(source_agent="a1", original_event=e))
        out.append(hive.state.agents["a1"].health)
    return out


def test_health_lifecycle_explicit_sequence():
    H, U, D, F = (AgentHealth.HEALTHY, AgentHealth.UNKNOWN,
                  AgentHealth.DEGRADED, AgentHealth.FAILED)
    stream = [PLAN("pw", "w", 1), INCs("w", Severity.WARN), INCs("e", Severity.ERROR),
              PLAN("pe", "e", 1), RC("x", "pe", 0), RC("y", "pw", 0),
              INCs("w2", Severity.WARN)]
    assert _hive_health(stream) == [U, U, D, F, F, F, H, D]
    both(stream, plans=("pw", "pe"))                    # oracle agrees each step


def test_unknown_before_first_incident():
    loc, hive = both([PLAN("p", "i", 1), RC("a", "p", 0)])
    assert hive.state.agents["a1"].health == AgentHealth.UNKNOWN


def test_agree_catches_health_only_regression(monkeypatch):
    def broken(self, agent_id):          # keeps counts right, never sets health
        s = self._state.agents.get(agent_id)
        if s is not None:
            s.open_incidents = len(self._open_agent_incidents(agent_id))
    monkeypatch.setattr(HiveReducer, "_recompute_agent_health", broken)
    with pytest.raises(AssertionError, match="health"):
        both([INC("i")])


# ------------------------------------------------------------ policy 3
def test_policy_any_complete_owned_plan_closes_despite_sibling_failure():
    loc, hive = both([INC("i"), PLAN("p", "i", 2), PLAN("q", "i", 2),
                      RC("q0", "q", 0), RC("qf", "q", 1, ok=False),
                      RC("p0", "p", 0), RC("p1", "p", 1)], plans=("p", "q"))
    assert lo(loc) == [] and ho(hive) == []
    assert loc._plan_failed_steps["q"] == {1}


def test_policy_late_incident_variant():
    loc, hive = both([PLAN("p", "i", 2), PLAN("q", "i", 1), RC("qf", "q", 0, ok=False),
                      RC("p0", "p", 0), RC("p1", "p", 1), INC("i")], plans=("p", "q"))
    assert lo(loc) == [] and ho(hive) == []


def test_policy_sibling_failure_after_closure_does_not_reopen():
    loc, hive = both([INC("i"), PLAN("p", "i", 1), PLAN("q", "i", 1),
                      RC("p0", "p", 0), RC("qf", "q", 0, ok=False)], plans=("p", "q"))
    assert lo(loc) == [] and ho(hive) == []


def test_policy_incomplete_plan_does_not_close():
    loc, hive = both([INC("i"), PLAN("p", "i", 2), PLAN("q", "i", 1),
                      RC("qf", "q", 0, ok=False), RC("p0", "p", 0)], plans=("p", "q"))
    assert lo(loc) == ["i"] and ho(hive) == ["i"]


def test_policy_only_owned_plans_close():
    loc, hive = both([INC("i"), INC("j"), PLAN("p", "i", 1), PLAN("r", "j", 1),
                      RC("r0", "r", 0)], plans=("p", "r"))
    assert lo(loc) == ["i"] and ho(hive) == ["i"]
