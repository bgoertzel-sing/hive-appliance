"""Tests for hive.planner — HivePlanner."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
from hive.planner import HivePlanner
from hive.types import (
    HiveState, HiveAction, HiveActionKind, HiveIncident,
    AgentHealthSummary, AgentHealth, HiveResourceState,
)
from schemas.types import Severity


def _state_with_agents(*agents, health=AgentHealth.HEALTHY):
    state = HiveState()
    for a in agents:
        state.agents[a] = AgentHealthSummary(
            agent_id=a, health=health, last_event_ts=time.time(),
        )
    return state


# ── Correlated incident rule ────────────────────────────

def test_plan_correlated_incident():
    planner = HivePlanner()
    state = _state_with_agents("a1", "a2")
    inc = HiveIncident(
        symptom="disk_full", severity=Severity.ERROR,
        affected_agents=["a1", "a2"], resolved=False,
    )
    state.incidents.append(inc)

    actions = planner.plan(state)
    delegate_actions = [a for a in actions if a.kind == HiveActionKind.DELEGATE_REPAIR]
    assert len(delegate_actions) >= 1
    assert set(delegate_actions[0].target_agents) == {"a1", "a2"}


def test_plan_no_actions_when_healthy():
    planner = HivePlanner()
    state = _state_with_agents("a1", "a2")
    actions = planner.plan(state)
    # No failed agents, no incidents, no stale agents (fresh timestamps)
    delegate = [a for a in actions if a.kind == HiveActionKind.DELEGATE_REPAIR]
    assert len(delegate) == 0


def test_plan_resolved_incident_ignored():
    planner = HivePlanner()
    state = _state_with_agents("a1", "a2")
    inc = HiveIncident(
        symptom="disk_full", severity=Severity.ERROR,
        affected_agents=["a1", "a2"], resolved=True,
    )
    state.incidents.append(inc)
    actions = planner.plan(state)
    delegate = [a for a in actions if a.kind == HiveActionKind.DELEGATE_REPAIR]
    assert len(delegate) == 0


# ── Resource threshold rule ──────────────────────────────

def test_plan_disk_critical():
    planner = HivePlanner(disk_critical=0.95)
    state = _state_with_agents("a1", "a2")
    state.resources = HiveResourceState(
        total_disk_bytes=100, used_disk_bytes=96,
    )
    actions = planner.plan(state)
    coord = [a for a in actions if a.kind == HiveActionKind.COORDINATE
             and a.parameters.get("reason") == "disk_critical"]
    assert len(coord) >= 1


def test_plan_disk_ok():
    planner = HivePlanner()
    state = _state_with_agents("a1")
    state.resources = HiveResourceState(
        total_disk_bytes=100, used_disk_bytes=50,
    )
    actions = planner.plan(state)
    coord = [a for a in actions if a.parameters.get("reason") == "disk_critical"]
    assert len(coord) == 0


# ── Failed agent rule ────────────────────────────────────

def test_plan_failed_agent_checkpoint():
    planner = HivePlanner()
    state = HiveState()
    state.agents["a1"] = AgentHealthSummary(
        agent_id="a1", health=AgentHealth.FAILED, last_event_ts=time.time(),
    )
    state.agents["a2"] = AgentHealthSummary(
        agent_id="a2", health=AgentHealth.HEALTHY, last_event_ts=time.time(),
    )
    actions = planner.plan(state)
    ckpt = [a for a in actions if a.kind == HiveActionKind.CHECKPOINT_ALL]
    assert len(ckpt) >= 1
    assert "a2" in ckpt[0].target_agents
    assert "a1" not in ckpt[0].target_agents  # failed agent not checkpointed


def test_plan_all_failed_no_checkpoint():
    planner = HivePlanner()
    state = _state_with_agents("a1", "a2", health=AgentHealth.FAILED)
    actions = planner.plan(state)
    ckpt = [a for a in actions if a.kind == HiveActionKind.CHECKPOINT_ALL]
    assert len(ckpt) == 0  # no healthy agents to checkpoint


# ── Stale agent rule ────────────────────────────────────

def test_plan_stale_agent():
    planner = HivePlanner(agent_stale_seconds=60.0)
    state = HiveState()
    state.agents["a1"] = AgentHealthSummary(
        agent_id="a1", health=AgentHealth.HEALTHY,
        last_event_ts=time.time() - 120,  # 120s ago = stale
    )
    actions = planner.plan(state)
    stale = [a for a in actions if a.parameters.get("reason") == "stale_agent"]
    assert len(stale) >= 1


def test_plan_fresh_agent_not_stale():
    planner = HivePlanner(agent_stale_seconds=600.0)
    state = _state_with_agents("a1")
    actions = planner.plan(state)
    stale = [a for a in actions if a.parameters.get("reason") == "stale_agent"]
    assert len(stale) == 0


# ── Custom rules ─────────────────────────────────────────

def test_custom_rule():
    planner = HivePlanner()

    def my_rule(state):
        return [HiveAction(kind=HiveActionKind.COORDINATE,
                           target_agents=["custom"], parameters={"custom": True})]

    planner.add_rule(my_rule)
    state = _state_with_agents("a1")
    actions = planner.plan(state)
    custom = [a for a in actions if a.parameters.get("custom")]
    assert len(custom) == 1


def test_broken_custom_rule_isolated():
    planner = HivePlanner()

    def bad_rule(state):
        raise RuntimeError("boom")

    planner.add_rule(bad_rule)
    state = _state_with_agents("a1")
    # Should not raise
    actions = planner.plan(state)
    assert isinstance(actions, list)


# ── Action log ───────────────────────────────────────────

def test_action_log():
    planner = HivePlanner()
    state = HiveState()
    state.agents["a1"] = AgentHealthSummary(
        agent_id="a1", health=AgentHealth.FAILED, last_event_ts=time.time(),
    )
    state.agents["a2"] = AgentHealthSummary(
        agent_id="a2", health=AgentHealth.HEALTHY, last_event_ts=time.time(),
    )
    actions = planner.plan(state)
    assert len(planner.action_log) == len(actions)
