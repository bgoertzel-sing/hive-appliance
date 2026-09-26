"""Tests for Astra re-review 6882 findings H1, H2 (hive reducer)."""
from __future__ import annotations

from hive.reducer import HiveReducer
from hive.types import AgentHealth, AgentHealthSummary, HiveEvent
from schemas.types import Event, EventKind


def _inc(agent, inc_id, severity="warn", plan_id=""):
    return HiveEvent(source_agent=agent, original_event=Event(
        kind=EventKind.INCIDENT, source="t", subject="svc",
        payload={"id": inc_id, "symptom": "svc_down", "severity": severity,
                 "plan_id": plan_id}))


def _rcpt(agent, rid, incident_id="", plan_id="", verified=True):
    return HiveEvent(source_agent=agent, original_event=Event(
        kind=EventKind.RECEIPT, source="t", subject="svc",
        payload={"id": rid, "verified": verified, "incident_id": incident_id,
                 "plan_id": plan_id}))


def _r():
    r = HiveReducer()
    r.register_agent("a1")
    return r


# ---------------------------------------------------------------- H2
def test_h2_replayed_incident_counted_once():
    r = _r()
    for _ in range(3):
        r.reduce(_inc("a1", "inc_1"))
    assert r.state.agents["a1"].open_incidents == 1
    assert r.state.agents["a1"].health == AgentHealth.DEGRADED


def test_h2_replayed_receipt_does_not_resolve_other_incident():
    r = _r()
    r.reduce(_inc("a1", "inc_1", plan_id="p1"))
    r.reduce(_inc("a1", "inc_2", plan_id="p2"))
    rc = _rcpt("a1", "rcpt_1", incident_id="inc_1")
    r.reduce(rc)
    r.reduce(rc)  # replay
    r.reduce(_rcpt("a1", "rcpt_1", incident_id="inc_1"))  # same identity, new event
    s = r.state.agents["a1"]
    assert s.open_incidents == 1
    assert s.health == AgentHealth.DEGRADED
    open_ids = [i["incident_id"] for i in r._open_agent_incidents("a1")]
    assert open_ids == ["inc_2"]


def test_h2_receipt_matched_by_plan_id():
    r = _r()
    r.reduce(_inc("a1", "inc_1", plan_id="p1"))
    r.reduce(_inc("a1", "inc_2", plan_id="p2"))
    r.reduce(_rcpt("a1", "rc", plan_id="p2"))
    assert [i["incident_id"] for i in r._open_agent_incidents("a1")] == ["inc_1"]


def test_h2_receipt_for_unknown_incident_is_noop():
    r = _r()
    r.reduce(_inc("a1", "inc_1"))
    r.reduce(_rcpt("a1", "rc", incident_id="nope"))
    assert r.state.agents["a1"].open_incidents == 1


def test_h2_unverified_receipt_ignored_and_all_resolved_is_healthy():
    r = _r()
    r.reduce(_inc("a1", "inc_1", severity="critical"))
    assert r.state.agents["a1"].health == AgentHealth.FAILED
    r.reduce(_rcpt("a1", "rc0", incident_id="inc_1", verified=False))
    assert r.state.agents["a1"].open_incidents == 1
    r.reduce(_rcpt("a1", "rc1", incident_id="inc_1"))
    assert r.state.agents["a1"].open_incidents == 0
    assert r.state.agents["a1"].health == AgentHealth.HEALTHY


# ---------------------------------------------------------------- H1
def test_h1_degraded_poll_keeps_incident_count_and_failed():
    r = _r()
    r.reduce(_inc("a1", "inc_1", severity="error"))
    r.reduce(_inc("a1", "inc_2"))
    r.update_agent_health("a1", AgentHealthSummary(
        agent_id="a1", health=AgentHealth.DEGRADED, open_incidents=0))
    s = r.state.agents["a1"]
    assert s.health == AgentHealth.FAILED
    assert s.open_incidents == 2


def test_h1_unknown_poll_does_not_mask_incidents():
    r = _r()
    r.reduce(_inc("a1", "inc_1"))
    r.update_agent_health("a1", AgentHealthSummary(
        agent_id="a1", health=AgentHealth.UNKNOWN, open_incidents=0))
    assert r.state.agents["a1"].health == AgentHealth.DEGRADED
    assert r.state.agents["a1"].open_incidents == 1


def test_h1_failed_poll_not_downgraded():
    r = _r()
    r.reduce(_inc("a1", "inc_1"))
    r.update_agent_health("a1", AgentHealthSummary(
        agent_id="a1", health=AgentHealth.FAILED, open_incidents=5))
    s = r.state.agents["a1"]
    assert s.health == AgentHealth.FAILED and s.open_incidents == 5


def test_h1_resolved_incidents_do_not_force_degraded():
    r = _r()
    r.reduce(_inc("a1", "inc_1"))
    r.reduce(_rcpt("a1", "rc", incident_id="inc_1"))
    r.update_agent_health("a1", AgentHealthSummary(
        agent_id="a1", health=AgentHealth.HEALTHY, open_incidents=0))
    assert r.state.agents["a1"].health == AgentHealth.HEALTHY
    assert r.state.agents["a1"].open_incidents == 0
