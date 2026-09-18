"""Tests for hive.types — M5 typed records."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
from hive.types import (
    AgentIdentity, HiveEvent, AgentHealthSummary, AgentHealth,
    HiveIncident, HiveResourceState, HiveState, HiveAction,
    HiveActionKind, HiveActionResult, _uid, _deterministic_id,
)
from schemas.types import Event, EventKind, Severity


# ── AgentIdentity ────────────────────────────────────────

def test_agent_identity_roundtrip():
    ai = AgentIdentity(agent_id="a1", display_name="Agent One", appliance_path="/hive/a1")
    d = ai.to_dict()
    ai2 = AgentIdentity.from_dict(d)
    assert ai2.agent_id == "a1"
    assert ai2.display_name == "Agent One"
    assert ai2.appliance_path == "/hive/a1"


def test_agent_identity_defaults():
    ai = AgentIdentity.from_dict({"agent_id": "x"})
    assert ai.display_name == ""
    assert ai.appliance_path == ""


# ── HiveEvent ────────────────────────────────────────────

def test_hive_event_creation():
    evt = Event(kind=EventKind.OBSERVATION, payload={"key": "val"})
    hevt = HiveEvent(source_agent="a1", original_event=evt)
    assert hevt.source_agent == "a1"
    assert hevt.original_event is evt
    assert hevt.schema_version == "1"
    assert hevt.id.startswith("hevt_")


def test_hive_event_roundtrip():
    evt = Event(kind=EventKind.INCIDENT, payload={"symptom": "disk_full"})
    hevt = HiveEvent(source_agent="a2", original_event=evt)
    d = hevt.to_dict()
    hevt2 = HiveEvent.from_dict(d)
    assert hevt2.source_agent == "a2"
    assert hevt2.original_event.kind == EventKind.INCIDENT


def test_hive_event_no_original():
    hevt = HiveEvent(source_agent="a3")
    d = hevt.to_dict()
    hevt2 = HiveEvent.from_dict(d)
    assert hevt2.original_event is None


# ── AgentHealthSummary ───────────────────────────────────

def test_health_summary_roundtrip():
    hs = AgentHealthSummary(
        agent_id="a1", health=AgentHealth.DEGRADED, open_incidents=2,
        services={"nginx": "active"}, cpu_percent=45.0,
    )
    d = hs.to_dict()
    hs2 = AgentHealthSummary.from_dict(d)
    assert hs2.agent_id == "a1"
    assert hs2.health == AgentHealth.DEGRADED
    assert hs2.open_incidents == 2
    assert hs2.services == {"nginx": "active"}
    assert hs2.cpu_percent == 45.0


def test_health_enum_values():
    assert AgentHealth.HEALTHY.value == "healthy"
    assert AgentHealth.FAILED.value == "failed"
    assert AgentHealth.UNKNOWN.value == "unknown"


# ── HiveIncident ─────────────────────────────────────────

def test_hive_incident_roundtrip():
    inc = HiveIncident(
        symptom="disk_full", severity=Severity.ERROR,
        affected_agents=["a1", "a2"],
    )
    d = inc.to_dict()
    inc2 = HiveIncident.from_dict(d)
    assert inc2.symptom == "disk_full"
    assert inc2.severity == Severity.ERROR
    assert inc2.affected_agents == ["a1", "a2"]
    assert not inc2.resolved


def test_hive_incident_deterministic():
    inc1 = HiveIncident.deterministic("disk_full", ["a1", "a2"])
    inc2 = HiveIncident.deterministic("disk_full", ["a2", "a1"])
    assert inc1.id == inc2.id  # same symptom + sorted agents = same ID


def test_hive_incident_deterministic_different():
    inc1 = HiveIncident.deterministic("disk_full", ["a1"])
    inc2 = HiveIncident.deterministic("cpu_high", ["a1"])
    assert inc1.id != inc2.id


# ── HiveResourceState ───────────────────────────────────

def test_resource_state_ratios():
    rs = HiveResourceState(
        total_disk_bytes=1000, used_disk_bytes=800,
        total_memory_bytes=500, used_memory_bytes=425,
    )
    assert rs.disk_usage_ratio == 0.8
    assert rs.memory_usage_ratio == 0.85


def test_resource_state_zero_total():
    rs = HiveResourceState()
    assert rs.disk_usage_ratio == 0.0
    assert rs.memory_usage_ratio == 0.0


def test_resource_state_alerts():
    rs = HiveResourceState(
        total_disk_bytes=100, used_disk_bytes=96,
    )
    alerts = rs.alerts()
    assert any("CRITICAL" in a for a in alerts)


def test_resource_state_warn():
    rs = HiveResourceState(
        total_disk_bytes=100, used_disk_bytes=85,
    )
    alerts = rs.alerts()
    assert any("WARN" in a and "Disk" in a for a in alerts)


def test_resource_state_no_alerts():
    rs = HiveResourceState(total_disk_bytes=100, used_disk_bytes=50)
    assert rs.alerts() == []


# ── HiveState ────────────────────────────────────────────

def test_hive_state_agent_lists():
    state = HiveState()
    state.agents["a1"] = AgentHealthSummary(agent_id="a1", health=AgentHealth.HEALTHY)
    state.agents["a2"] = AgentHealthSummary(agent_id="a2", health=AgentHealth.DEGRADED)
    state.agents["a3"] = AgentHealthSummary(agent_id="a3", health=AgentHealth.FAILED)

    assert state.healthy_agents == ["a1"]
    assert state.degraded_agents == ["a2"]
    assert state.failed_agents == ["a3"]


def test_hive_state_open_incidents():
    state = HiveState()
    inc1 = HiveIncident(symptom="s1", resolved=False)
    inc2 = HiveIncident(symptom="s2", resolved=True)
    state.incidents = [inc1, inc2]
    assert len(state.open_incidents) == 1
    assert state.open_incidents[0].symptom == "s1"


def test_hive_state_to_dict():
    state = HiveState()
    state.agents["a1"] = AgentHealthSummary(agent_id="a1")
    d = state.to_dict()
    assert "agents" in d
    assert "a1" in d["agents"]


# ── HiveAction / HiveActionResult ────────────────────────

def test_hive_action():
    a = HiveAction(
        kind=HiveActionKind.RESTART_AGENT,
        target_agents=["a1"],
        parameters={"reason": "test"},
    )
    d = a.to_dict()
    assert d["kind"] == "restart_agent"
    assert d["target_agents"] == ["a1"]


def test_hive_action_result():
    r = HiveActionResult(action_id="act_1", success=True)
    d = r.to_dict()
    assert d["success"] is True


# ── Helpers ──────────────────────────────────────────────

def test_uid_prefix():
    u = _uid("test_")
    assert u.startswith("test_")
    assert len(u) == 5 + 16  # prefix + 16 hex chars


def test_deterministic_id():
    id1 = _deterministic_id("x_", "a", "b")
    id2 = _deterministic_id("x_", "a", "b")
    id3 = _deterministic_id("x_", "a", "c")
    assert id1 == id2
    assert id1 != id3
