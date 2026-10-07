"""Astra 7519 findings:
P3-ownerless (Medium): a plan with no proven owner (e.g. PLAN with an empty
  incident_id) must never close an incident, not even incidents that link to
  it via plan_id -- in both the local and hive reducers, before and after
  snapshot/restore.  Owned-plan closure is unchanged.
H-oracle-resolved (Low): the health oracle must not treat an incident that
  ARRIVES already resolved as a past open period (hive stays UNKNOWN).
"""
import json

from controller.reducer import Reducer
from hive.reducer import HiveReducer
from hive.types import AgentHealth, HiveEvent
from schemas.types import Event, EventKind, IncidentReport
from tests.test_astra7160 import PLAN, RC, both, ho, lo


def ev(kind, payload):
    return Event(kind=kind, source="t", subject="svc", payload=payload)


def INCL(i, plan_id="", resolved=False):
    d = IncidentReport(id=i, component="svc", symptom="down").to_dict()
    d["plan_id"] = plan_id
    d["resolved"] = resolved
    return ev(EventKind.INCIDENT, d)


def rt(r):
    r2 = Reducer()
    r2.restore_snapshot(json.loads(json.dumps(r.snapshot())))
    return r2


WITNESS = [INCL("i", "p"), INCL("j", "p"), PLAN("p", "", 1), RC("x", "p", 0)]


# ------------------------------------------------------------ P3-ownerless
def test_ownerless_linked_plan_closes_nothing_both_reducers():
    loc, hive = both(WITNESS)
    assert lo(loc) == ["i", "j"] and ho(hive) == ["i", "j"]
    assert loc._plan_owner.get("p", "") == ""
    assert hive._plan_owner.get("a1:p", "") == ""


def test_ownerless_witness_survives_restore_after_every_event():
    r = Reducer()
    for e in WITNESS:
        r.reduce(e)
        r = rt(r)
    assert lo(r) == ["i", "j"]
    for _ in range(3):
        r = rt(r)
        assert lo(r) == ["i", "j"]


def test_ownerless_plan_receipt_first_then_links():
    loc, hive = both([PLAN("p", "", 1), RC("x", "p", 0), INCL("i", "p"), INCL("j", "p")])
    assert lo(loc) == ["i", "j"] and ho(hive) == ["i", "j"]


def test_single_linked_ownerless_plan_does_not_close():
    loc, hive = both([INCL("i", "p"), PLAN("p", "", 2), RC("a", "p", 0), RC("b", "p", 1)])
    assert lo(loc) == ["i"] and ho(hive) == ["i"]


def test_owned_plan_still_closes_its_owner_only():
    loc, hive = both([INCL("i", "p"), PLAN("p", "i", 1), RC("x", "p", 0)])
    assert lo(loc) == [] and ho(hive) == []
    r = Reducer()
    for e in [INCL("i", "p"), PLAN("p", "i", 1), RC("x", "p", 0)]:
        r.reduce(e)
        r = rt(r)
    assert lo(r) == []


def test_owned_plan_does_not_close_foreign_linked_incident():
    loc, hive = both([INCL("i"), INCL("j", "p"), PLAN("p", "i", 1), RC("x", "p", 0)])
    assert "j" in lo(loc) and "j" in ho(hive)
    assert "i" not in lo(loc) and "i" not in ho(hive)


# ------------------------------------------------------- H-oracle-resolved
def test_already_resolved_first_incident_keeps_unknown():
    loc, hive = both([INCL("i", resolved=True)])
    assert hive.state.agents["a1"].health == AgentHealth.UNKNOWN


def test_same_event_open_and_close_still_healthy():
    loc, hive = both([PLAN("p", "i", 1), RC("a", "p", 0), INCL("i")])
    assert lo(loc) == []
    assert hive.state.agents["a1"].health == AgentHealth.HEALTHY


def test_resolved_arrival_after_open_period():
    loc, hive = both([INCL("i"), INCL("k", resolved=True)])
    assert hive.state.agents["a1"].health == AgentHealth.DEGRADED
