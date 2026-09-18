"""Tests for hive.adapter — AgentApplianceAdapter implementations."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
from hive.adapter import StubAgentAdapter, AgentApplianceAdapter
from hive.types import AgentHealth, HiveAction, HiveActionKind
from schemas.types import Event, EventKind


# ── StubAgentAdapter ─────────────────────────────────────

def test_stub_identity():
    stub = StubAgentAdapter("a1", "Agent One")
    assert stub.identity.agent_id == "a1"
    assert stub.identity.display_name == "Agent One"


def test_stub_protocol():
    stub = StubAgentAdapter("a1")
    assert isinstance(stub, AgentApplianceAdapter)


def test_stub_events_empty():
    stub = StubAgentAdapter("a1")
    events, cursor = stub.events_since(None)
    assert events == []
    assert cursor == "0"


def test_stub_inject_events():
    stub = StubAgentAdapter("a1")
    e1 = Event(kind=EventKind.OBSERVATION, payload={"key": "v1"})
    e2 = Event(kind=EventKind.INCIDENT, payload={"key": "v2"})
    stub.inject_event(e1)
    stub.inject_event(e2)

    events, cursor = stub.events_since(None)
    assert len(events) == 2
    assert cursor == "2"

    # Cursor-based pagination
    events2, cursor2 = stub.events_since("1")
    assert len(events2) == 1
    assert cursor2 == "2"


def test_stub_health_default():
    stub = StubAgentAdapter("a1")
    h = stub.health_summary()
    assert h.health == AgentHealth.HEALTHY
    assert h.open_incidents == 0


def test_stub_set_health():
    stub = StubAgentAdapter("a1")
    stub.set_health(AgentHealth.DEGRADED, open_incidents=3)
    h = stub.health_summary()
    assert h.health == AgentHealth.DEGRADED
    assert h.open_incidents == 3


def test_stub_execute():
    stub = StubAgentAdapter("a1")
    action = HiveAction(kind=HiveActionKind.RESTART_AGENT, target_agents=["a1"])
    result = stub.execute(action)
    assert result.success is True
    assert "a1" in result.agent_results


def test_stub_checkpoint_restore():
    stub = StubAgentAdapter("a1")
    ckpt = stub.checkpoint("test_label")
    assert ckpt.label == "test_label"
    assert stub.restore(ckpt.id) is True
    assert stub.restore("nonexistent") is False


def test_stub_state_snapshot():
    stub = StubAgentAdapter("a1")
    snap = stub.state_snapshot()
    assert isinstance(snap, dict)
