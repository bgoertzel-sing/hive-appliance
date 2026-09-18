"""Tests for hive.event_bus — HiveEventBus."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
from hive.event_bus import HiveEventBus
from hive.adapter import StubAgentAdapter
from hive.types import HiveEvent
from schemas.types import Event, EventKind


def _make_bus_with_agents(*agent_ids):
    bus = HiveEventBus()
    adapters = {}
    for aid in agent_ids:
        adapter = StubAgentAdapter(aid)
        bus.register_adapter(adapter)
        adapters[aid] = adapter
    return bus, adapters


def test_register_unregister():
    bus = HiveEventBus()
    stub = StubAgentAdapter("a1")
    bus.register_adapter(stub)
    assert "a1" in bus.registered_agents
    bus.unregister_adapter("a1")
    assert "a1" not in bus.registered_agents


def test_poll_empty():
    bus, adapters = _make_bus_with_agents("a1")
    events = bus.poll_all()
    assert events == []
    assert bus.event_count == 0


def test_poll_single_agent():
    bus, adapters = _make_bus_with_agents("a1")
    adapters["a1"].inject_event(Event(kind=EventKind.OBSERVATION, payload={"x": 1}))
    adapters["a1"].inject_event(Event(kind=EventKind.INCIDENT, payload={"x": 2}))

    events = bus.poll_all()
    assert len(events) == 2
    assert all(isinstance(e, HiveEvent) for e in events)
    assert all(e.source_agent == "a1" for e in events)
    assert bus.event_count == 2


def test_poll_multiple_agents():
    bus, adapters = _make_bus_with_agents("a1", "a2")
    adapters["a1"].inject_event(Event(kind=EventKind.OBSERVATION, payload={"from": "a1"}))
    adapters["a2"].inject_event(Event(kind=EventKind.INCIDENT, payload={"from": "a2"}))

    events = bus.poll_all()
    assert len(events) == 2
    agents = {e.source_agent for e in events}
    assert agents == {"a1", "a2"}


def test_poll_cursor_advances():
    bus, adapters = _make_bus_with_agents("a1")
    adapters["a1"].inject_event(Event(kind=EventKind.OBSERVATION, payload={"n": 1}))
    events1 = bus.poll_all()
    assert len(events1) == 1

    # Second poll should return nothing (cursor advanced)
    events2 = bus.poll_all()
    assert len(events2) == 0

    # New event should appear
    adapters["a1"].inject_event(Event(kind=EventKind.OBSERVATION, payload={"n": 2}))
    events3 = bus.poll_all()
    assert len(events3) == 1


def test_subscriber_called():
    bus, adapters = _make_bus_with_agents("a1")
    received = []
    bus.add_subscriber(lambda e: received.append(e))

    adapters["a1"].inject_event(Event(kind=EventKind.OBSERVATION, payload={}))
    bus.poll_all()
    assert len(received) == 1
    assert received[0].source_agent == "a1"


def test_remove_subscriber():
    bus, adapters = _make_bus_with_agents("a1")
    received = []
    cb = lambda e: received.append(e)
    bus.add_subscriber(cb)
    bus.remove_subscriber(cb)

    adapters["a1"].inject_event(Event(kind=EventKind.OBSERVATION, payload={}))
    bus.poll_all()
    assert len(received) == 0


def test_subscriber_exception_isolated():
    bus, adapters = _make_bus_with_agents("a1")
    good_received = []

    def bad_sub(e):
        raise RuntimeError("boom")

    bus.add_subscriber(bad_sub)
    bus.add_subscriber(lambda e: good_received.append(e))

    adapters["a1"].inject_event(Event(kind=EventKind.OBSERVATION, payload={}))
    bus.poll_all()
    # Good subscriber still called despite bad one raising
    assert len(good_received) == 1


def test_events_since():
    bus, adapters = _make_bus_with_agents("a1")
    for i in range(5):
        adapters["a1"].inject_event(Event(kind=EventKind.OBSERVATION, payload={"i": i}))
    bus.poll_all()

    all_events = bus.events_since(0)
    assert len(all_events) == 5

    later = bus.events_since(3)
    assert len(later) == 2


def test_recent_events():
    bus, adapters = _make_bus_with_agents("a1")
    adapters["a1"].inject_event(Event(kind=EventKind.OBSERVATION, payload={}))
    bus.poll_all()

    recent = bus.recent_events(seconds=60.0)
    assert len(recent) == 1

    old = bus.recent_events(seconds=0.0)
    assert len(old) == 0


def test_clear():
    bus, adapters = _make_bus_with_agents("a1")
    adapters["a1"].inject_event(Event(kind=EventKind.OBSERVATION, payload={}))
    bus.poll_all()
    assert bus.event_count == 1
    bus.clear()
    assert bus.event_count == 0


def test_log_trimming():
    bus = HiveEventBus()
    bus._max_log_size = 5
    stub = StubAgentAdapter("a1")
    bus.register_adapter(stub)

    for i in range(10):
        stub.inject_event(Event(kind=EventKind.OBSERVATION, payload={"i": i}))
    bus.poll_all()
    assert bus.event_count == 5
