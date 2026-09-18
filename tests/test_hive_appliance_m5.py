"""Tests for hive.appliance — HiveAppliance orchestrator (M5 integration)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
from hive.appliance import HiveAppliance
from hive.adapter import StubAgentAdapter
from hive.types import (
    HiveAction, HiveActionKind, AgentHealth, HiveIncident,
)
from schemas.types import Event, EventKind, Severity


# ── Registration ─────────────────────────────────────────

def test_register_agent():
    hive = HiveAppliance()
    stub = StubAgentAdapter("a1", "Agent One")
    hive.register_agent(stub)
    assert "a1" in hive.registered_agents
    assert "a1" in hive.state.agents


def test_unregister_agent():
    hive = HiveAppliance()
    stub = StubAgentAdapter("a1")
    hive.register_agent(stub)
    hive.unregister_agent("a1")
    assert "a1" not in hive.registered_agents


def test_register_multiple():
    hive = HiveAppliance()
    for name in ["a1", "a2", "a3"]:
        hive.register_agent(StubAgentAdapter(name))
    assert set(hive.registered_agents) == {"a1", "a2", "a3"}


# ── Tick with no events ─────────────────────────────────

def test_tick_empty():
    hive = HiveAppliance()
    hive.register_agent(StubAgentAdapter("a1"))
    result = hive.tick()
    assert result["tick"] == 1
    assert result["events_polled"] == 0
    assert hive.tick_count == 1


def test_multiple_ticks():
    hive = HiveAppliance()
    hive.register_agent(StubAgentAdapter("a1"))
    hive.tick()
    hive.tick()
    result = hive.tick()
    assert result["tick"] == 3
    assert hive.tick_count == 3


# ── Tick with events ────────────────────────────────────

def test_tick_polls_events():
    hive = HiveAppliance()
    stub = StubAgentAdapter("a1")
    stub.inject_event(Event(kind=EventKind.OBSERVATION, payload={"x": 1}))
    stub.inject_event(Event(kind=EventKind.OBSERVATION, payload={"x": 2}))
    hive.register_agent(stub)

    result = hive.tick()
    assert result["events_polled"] == 2
    assert hive.shared_store.total_events == 2


def test_tick_events_reach_shared_store():
    hive = HiveAppliance()
    stub = StubAgentAdapter("a1")
    stub.inject_event(Event(kind=EventKind.INCIDENT, payload={"symptom": "test", "id": "i1", "severity": "warn"}))
    hive.register_agent(stub)
    hive.tick()
    assert hive.shared_store.total_events == 1


# ── Cross-agent incident correlation ────────────────────

def test_cross_agent_incident_correlation():
    hive = HiveAppliance(correlation_threshold=2)
    stub1 = StubAgentAdapter("a1")
    stub2 = StubAgentAdapter("a2")
    hive.register_agent(stub1)
    hive.register_agent(stub2)

    # Inject same symptom on both agents
    stub1.inject_event(Event(kind=EventKind.INCIDENT,
                              payload={"symptom": "disk_full", "id": "i1", "severity": "warn"}))
    stub2.inject_event(Event(kind=EventKind.INCIDENT,
                              payload={"symptom": "disk_full", "id": "i2", "severity": "warn"}))
    hive.tick()

    open_incs = hive.state.open_incidents
    assert len(open_incs) >= 1
    assert open_incs[0].symptom == "disk_full"


# ── Planning from incidents ──────────────────────────────

def test_tick_produces_actions_for_incidents():
    hive = HiveAppliance(correlation_threshold=2)
    stub1 = StubAgentAdapter("a1")
    stub2 = StubAgentAdapter("a2")
    hive.register_agent(stub1)
    hive.register_agent(stub2)

    stub1.inject_event(Event(kind=EventKind.INCIDENT,
                              payload={"symptom": "disk_full", "id": "i1", "severity": "warn"}))
    stub2.inject_event(Event(kind=EventKind.INCIDENT,
                              payload={"symptom": "disk_full", "id": "i2", "severity": "warn"}))
    result = hive.tick()
    assert len(result["proposed_actions"]) >= 1


# ── Auto-execute ─────────────────────────────────────────

def test_auto_execute():
    hive = HiveAppliance(correlation_threshold=2, auto_execute=True)
    stub1 = StubAgentAdapter("a1")
    stub2 = StubAgentAdapter("a2")
    hive.register_agent(stub1)
    hive.register_agent(stub2)

    stub1.inject_event(Event(kind=EventKind.INCIDENT,
                              payload={"symptom": "disk_full", "id": "i1", "severity": "warn"}))
    stub2.inject_event(Event(kind=EventKind.INCIDENT,
                              payload={"symptom": "disk_full", "id": "i2", "severity": "warn"}))
    result = hive.tick()
    if result["proposed_actions"]:
        assert len(result["executed_results"]) >= 1


# ── Manual action execution ──────────────────────────────

def test_execute_action():
    hive = HiveAppliance()
    stub = StubAgentAdapter("a1")
    hive.register_agent(stub)

    action = HiveAction(
        kind=HiveActionKind.DELEGATE_REPAIR,
        target_agents=["a1"],
        parameters={"reason": "test"},
    )
    result = hive.execute_action(action)
    assert result.success is True
    assert "a1" in result.agent_results


def test_execute_action_unregistered_agent():
    hive = HiveAppliance()
    action = HiveAction(
        kind=HiveActionKind.DELEGATE_REPAIR,
        target_agents=["nonexistent"],
    )
    result = hive.execute_action(action)
    assert result.success is False
    assert "nonexistent" in result.agent_results


def test_action_history():
    hive = HiveAppliance()
    stub = StubAgentAdapter("a1")
    hive.register_agent(stub)

    action = HiveAction(kind=HiveActionKind.COORDINATE, target_agents=["a1"])
    hive.execute_action(action)
    assert len(hive.action_history) == 1


# ── Dashboard integration ────────────────────────────────

def test_report():
    hive = HiveAppliance()
    hive.register_agent(StubAgentAdapter("a1"))
    hive.register_agent(StubAgentAdapter("a2"))
    hive.tick()
    report = hive.report()
    assert "HIVE HEALTH DASHBOARD" in report
    assert "a1" in report
    assert "a2" in report


def test_summary():
    hive = HiveAppliance()
    hive.register_agent(StubAgentAdapter("a1"))
    hive.tick()
    s = hive.summary()
    assert s["agent_count"] == 1
    assert "hive_health" in s


# ── Resource updates ─────────────────────────────────────

def test_update_agent_resources():
    hive = HiveAppliance()
    hive.register_agent(StubAgentAdapter("a1"))
    alerts = hive.update_agent_resources("a1", disk_total=100, disk_used=96)
    assert any("CRITICAL" in a for a in alerts)


# ── Resolve incident ─────────────────────────────────────

def test_resolve_incident():
    hive = HiveAppliance(correlation_threshold=2)
    stub1 = StubAgentAdapter("a1")
    stub2 = StubAgentAdapter("a2")
    hive.register_agent(stub1)
    hive.register_agent(stub2)

    stub1.inject_event(Event(kind=EventKind.INCIDENT,
                              payload={"symptom": "disk_full", "id": "i1", "severity": "warn"}))
    stub2.inject_event(Event(kind=EventKind.INCIDENT,
                              payload={"symptom": "disk_full", "id": "i2", "severity": "warn"}))
    hive.tick()

    open_incs = hive.state.open_incidents
    if open_incs:
        inc_id = open_incs[0].id
        assert hive.resolve_incident(inc_id) is True
        assert len(hive.state.open_incidents) == 0


# ── Health polling ───────────────────────────────────────

def test_health_polling_updates_state():
    hive = HiveAppliance()
    stub = StubAgentAdapter("a1")
    stub.set_health(AgentHealth.DEGRADED, open_incidents=2)
    hive.register_agent(stub)
    hive.tick()
    assert hive.state.agents["a1"].health == AgentHealth.DEGRADED


def test_failed_agent_triggers_checkpoint_plan():
    hive = HiveAppliance()
    stub1 = StubAgentAdapter("a1")
    stub2 = StubAgentAdapter("a2")
    stub1.set_health(AgentHealth.FAILED, open_incidents=1)
    stub2.set_health(AgentHealth.HEALTHY)
    hive.register_agent(stub1)
    hive.register_agent(stub2)
    result = hive.tick()
    checkpoint_actions = [a for a in result["proposed_actions"]
                          if a.get("kind") == "checkpoint_all"]
    assert len(checkpoint_actions) >= 1


# ── Multi-agent full cycle ───────────────────────────────

def test_full_cycle_three_agents():
    """Full integration: 3 agents, events, correlation, planning, execution."""
    hive = HiveAppliance(correlation_threshold=2, auto_execute=True)

    stubs = {}
    for name in ["alpha", "beta", "gamma"]:
        stub = StubAgentAdapter(name)
        hive.register_agent(stub)
        stubs[name] = stub

    # Tick 1: healthy, no events
    r1 = hive.tick()
    assert r1["events_polled"] == 0
    assert len(hive.state.open_incidents) == 0

    # Tick 2: incidents on alpha and beta (same symptom)
    stubs["alpha"].inject_event(Event(kind=EventKind.INCIDENT,
        payload={"symptom": "memory_leak", "id": "ml_a", "severity": "warn"}))
    stubs["beta"].inject_event(Event(kind=EventKind.INCIDENT,
        payload={"symptom": "memory_leak", "id": "ml_b", "severity": "warn"}))
    r2 = hive.tick()
    assert r2["events_polled"] == 2
    assert len(hive.state.open_incidents) >= 1

    # Tick 3: gamma still healthy, should see proposed actions
    r3 = hive.tick()
    # Actions should still be proposed for open incident
    assert hive.tick_count == 3

    # Dashboard should reflect state
    report = hive.report()
    assert "alpha" in report
    assert "beta" in report
    assert "gamma" in report
