"""Tests for hive.reducer — HiveReducer."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hive.reducer import HiveReducer
from hive.types import (
    AgentHealth,
    AgentHealthSummary,
    HiveEvent,
)
from schemas.types import Event, EventKind


def _make_incident_event(symptom, severity="warn", incident_id="inc_1"):
    return Event(
        kind=EventKind.INCIDENT,
        payload={"symptom": symptom, "severity": severity, "id": incident_id},
    )


def _make_observation_event(service, active="active"):
    return Event(
        kind=EventKind.OBSERVATION,
        payload={"service": service, "active": active},
    )


def _make_receipt_event(verified=True):
    return Event(
        kind=EventKind.RECEIPT,
        payload={"verified": verified},
    )


# ── Registration ─────────────────────────────────────────

def test_register_agent():
    r = HiveReducer()
    r.register_agent("a1")
    assert "a1" in r.state.agents
    assert r.state.agents["a1"].health == AgentHealth.UNKNOWN


def test_unregister_agent():
    r = HiveReducer()
    r.register_agent("a1")
    r.unregister_agent("a1")
    assert "a1" not in r.state.agents


# ── Incident handling ────────────────────────────────────

def test_reduce_incident_updates_agent_health():
    r = HiveReducer()
    r.register_agent("a1")
    evt = _make_incident_event("disk_full", severity="warn")
    hevt = HiveEvent(source_agent="a1", original_event=evt)
    r.reduce(hevt)
    assert r.state.agents["a1"].health == AgentHealth.DEGRADED
    assert r.state.agents["a1"].open_incidents == 1


def test_reduce_critical_incident_marks_failed():
    r = HiveReducer()
    r.register_agent("a1")
    evt = _make_incident_event("disk_full", severity="critical")
    hevt = HiveEvent(source_agent="a1", original_event=evt)
    r.reduce(hevt)
    assert r.state.agents["a1"].health == AgentHealth.FAILED


def test_cross_agent_correlation():
    r = HiveReducer(correlation_window=300.0, correlation_threshold=2)
    r.register_agent("a1")
    r.register_agent("a2")

    evt1 = _make_incident_event("disk_full", incident_id="inc_a1")
    hevt1 = HiveEvent(source_agent="a1", original_event=evt1)
    incidents1 = r.reduce(hevt1)
    assert len(incidents1) == 0  # only 1 agent so far

    evt2 = _make_incident_event("disk_full", incident_id="inc_a2")
    hevt2 = HiveEvent(source_agent="a2", original_event=evt2)
    incidents2 = r.reduce(hevt2)
    assert len(incidents2) == 1  # 2 agents = correlated
    assert incidents2[0].symptom == "disk_full"
    assert set(incidents2[0].affected_agents) == {"a1", "a2"}


def test_correlation_dedup():
    """Same correlated incident should not be created twice."""
    r = HiveReducer(correlation_threshold=2)
    r.register_agent("a1")
    r.register_agent("a2")

    for agent in ["a1", "a2"]:
        evt = _make_incident_event("disk_full", incident_id=f"inc_{agent}")
        r.reduce(HiveEvent(source_agent=agent, original_event=evt))

    # Third incident from a1 should not create a new hive incident
    evt3 = _make_incident_event("disk_full", incident_id="inc_a1_2")
    incidents3 = r.reduce(HiveEvent(source_agent="a1", original_event=evt3))
    assert len(incidents3) == 0
    assert len(r.state.incidents) == 1  # still just one


def test_no_correlation_different_symptoms():
    r = HiveReducer(correlation_threshold=2)
    r.register_agent("a1")
    r.register_agent("a2")

    r.reduce(HiveEvent(source_agent="a1",
                        original_event=_make_incident_event("disk_full")))
    incidents = r.reduce(HiveEvent(source_agent="a2",
                                    original_event=_make_incident_event("cpu_high")))
    assert len(incidents) == 0  # different symptoms


# ── Observation handling ─────────────────────────────────

def test_reduce_observation_updates_services():
    r = HiveReducer()
    r.register_agent("a1")
    evt = _make_observation_event("nginx", "active")
    r.reduce(HiveEvent(source_agent="a1", original_event=evt))
    assert r.state.agents["a1"].services.get("nginx") == "active"


# ── Receipt handling ─────────────────────────────────────

def test_reduce_receipt_resolves_incident():
    r = HiveReducer()
    r.register_agent("a1")

    # Create an incident
    r.reduce(HiveEvent(source_agent="a1",
                        original_event=_make_incident_event("disk_full")))
    assert r.state.agents["a1"].open_incidents == 1
    assert r.state.agents["a1"].health == AgentHealth.DEGRADED

    # Resolve via receipt
    r.reduce(HiveEvent(source_agent="a1",
                        original_event=_make_receipt_event(verified=True)))
    assert r.state.agents["a1"].open_incidents == 0
    assert r.state.agents["a1"].health == AgentHealth.HEALTHY


def test_reduce_unverified_receipt_no_change():
    r = HiveReducer()
    r.register_agent("a1")
    r.reduce(HiveEvent(source_agent="a1",
                        original_event=_make_incident_event("x")))
    r.reduce(HiveEvent(source_agent="a1",
                        original_event=_make_receipt_event(verified=False)))
    assert r.state.agents["a1"].open_incidents == 1


# ── Resource updates ─────────────────────────────────────

def test_update_resources():
    r = HiveReducer()
    r.register_agent("a1")
    r.register_agent("a2")
    r.update_resources("a1", disk_total=1000, disk_used=800)
    r.update_resources("a2", disk_total=1000, disk_used=700)
    assert r.state.resources.total_disk_bytes == 2000
    assert r.state.resources.used_disk_bytes == 1500


def test_update_resources_alerts():
    r = HiveReducer()
    r.register_agent("a1")
    alerts = r.update_resources("a1", disk_total=100, disk_used=96)
    assert any("CRITICAL" in a for a in alerts)


# ── Resolve hive incident ───────────────────────────────

def test_resolve_hive_incident():
    r = HiveReducer(correlation_threshold=2)
    r.register_agent("a1")
    r.register_agent("a2")
    r.reduce(HiveEvent(source_agent="a1",
                        original_event=_make_incident_event("disk_full")))
    incidents = r.reduce(HiveEvent(source_agent="a2",
                                    original_event=_make_incident_event("disk_full")))
    assert len(incidents) == 1
    inc_id = incidents[0].id

    assert r.resolve_hive_incident(inc_id) is True
    assert len(r.state.open_incidents) == 0
    # Can't resolve again
    assert r.resolve_hive_incident(inc_id) is False


# ── Drift detection ──────────────────────────────────────

def test_detect_drift():
    r = HiveReducer()
    r.register_agent("a1")
    r.register_agent("a2")
    r.state.agents["a1"].services = {"nginx": "active"}
    r.state.agents["a2"].services = {"nginx": "inactive"}
    drifts = r.detect_drift()
    assert len(drifts) == 1
    assert drifts[0]["service"] == "nginx"


def test_no_drift():
    r = HiveReducer()
    r.register_agent("a1")
    r.register_agent("a2")
    r.state.agents["a1"].services = {"nginx": "active"}
    r.state.agents["a2"].services = {"nginx": "active"}
    drifts = r.detect_drift()
    assert len(drifts) == 0


# ── Null event ───────────────────────────────────────────

def test_reduce_null_event():
    r = HiveReducer()
    hevt = HiveEvent(source_agent="a1", original_event=None)
    incidents = r.reduce(hevt)
    assert incidents == []


# ── Health update ────────────────────────────────────────

def test_update_agent_health_directly():
    r = HiveReducer()
    r.register_agent("a1")
    summary = AgentHealthSummary(agent_id="a1", health=AgentHealth.FAILED, open_incidents=5)
    r.update_agent_health("a1", summary)
    assert r.state.agents["a1"].health == AgentHealth.FAILED
    assert r.state.agents["a1"].open_incidents == 5
