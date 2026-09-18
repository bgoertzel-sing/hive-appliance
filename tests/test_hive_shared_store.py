"""Tests for hive.shared_store — SharedStoreAdapter."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
from hive.shared_store import SharedStoreAdapter
from hive.adapter import StubAgentAdapter
from hive.types import HiveEvent
from schemas.types import Event, EventKind, Severity


def _make_hive_event(agent_id, kind=EventKind.OBSERVATION, payload=None):
    evt = Event(kind=kind, payload=payload or {})
    return HiveEvent(source_agent=agent_id, original_event=evt)


# ── Basic operations ────────────────────────────────────

def test_ingest_and_count():
    store = SharedStoreAdapter()
    assert store.total_events == 0
    store.ingest(_make_hive_event("a1"))
    store.ingest(_make_hive_event("a2"))
    assert store.total_events == 2


def test_query_all():
    store = SharedStoreAdapter()
    store.ingest(_make_hive_event("a1", payload={"x": 1}))
    store.ingest(_make_hive_event("a2", payload={"x": 2}))
    results = store.query()
    assert len(results) == 2


def test_query_by_agent():
    store = SharedStoreAdapter()
    store.ingest(_make_hive_event("a1"))
    store.ingest(_make_hive_event("a2"))
    store.ingest(_make_hive_event("a1"))
    results = store.query(agent_id="a1")
    assert len(results) == 2


def test_query_by_kind():
    store = SharedStoreAdapter()
    store.ingest(_make_hive_event("a1", kind=EventKind.OBSERVATION))
    store.ingest(_make_hive_event("a1", kind=EventKind.INCIDENT))
    results = store.query(kind=EventKind.INCIDENT)
    assert len(results) == 1


def test_query_limit():
    store = SharedStoreAdapter()
    for i in range(10):
        store.ingest(_make_hive_event("a1", payload={"i": i}))
    results = store.query(limit=3)
    assert len(results) == 3


def test_query_since():
    store = SharedStoreAdapter()
    e1 = _make_hive_event("a1")
    e1.hive_received_at = 1000.0
    e2 = _make_hive_event("a1")
    e2.hive_received_at = 2000.0
    store.ingest(e1)
    store.ingest(e2)
    results = store.query(since=1500.0)
    assert len(results) == 1


# ── Cross-agent incidents ────────────────────────────────

def test_cross_agent_incidents():
    store = SharedStoreAdapter()
    store.ingest(_make_hive_event("a1", kind=EventKind.INCIDENT,
                                   payload={"symptom": "disk_full"}))
    store.ingest(_make_hive_event("a2", kind=EventKind.INCIDENT,
                                   payload={"symptom": "disk_full"}))
    store.ingest(_make_hive_event("a1", kind=EventKind.INCIDENT,
                                   payload={"symptom": "cpu_high"}))

    result = store.cross_agent_incidents("disk_full", window_seconds=600)
    assert "a1" in result
    assert "a2" in result
    assert len(result["a1"]) == 1
    assert len(result["a2"]) == 1


def test_cross_agent_incidents_no_match():
    store = SharedStoreAdapter()
    store.ingest(_make_hive_event("a1", kind=EventKind.INCIDENT,
                                   payload={"symptom": "cpu_high"}))
    result = store.cross_agent_incidents("disk_full")
    assert len(result) == 0


# ── Agent event queries ─────────────────────────────────

def test_query_agent_direct():
    store = SharedStoreAdapter()
    stub = StubAgentAdapter("a1")
    stub.inject_event(Event(kind=EventKind.OBSERVATION, payload={"n": 1}))
    stub.inject_event(Event(kind=EventKind.OBSERVATION, payload={"n": 2}))
    store.register_adapter(stub)

    events = store.query_agent("a1")
    assert len(events) == 2


def test_query_agent_not_registered():
    store = SharedStoreAdapter()
    events = store.query_agent("nonexistent")
    assert events == []


# ── Bookkeeping ──────────────────────────────────────────

def test_agents_with_events():
    store = SharedStoreAdapter()
    store.ingest(_make_hive_event("a1"))
    store.ingest(_make_hive_event("a2"))
    agents = store.agents_with_events()
    assert set(agents) == {"a1", "a2"}


def test_event_count_per_agent():
    store = SharedStoreAdapter()
    store.ingest(_make_hive_event("a1"))
    store.ingest(_make_hive_event("a1"))
    store.ingest(_make_hive_event("a2"))
    assert store.event_count("a1") == 2
    assert store.event_count("a2") == 1
    assert store.event_count() == 3


def test_summary():
    store = SharedStoreAdapter()
    store.ingest(_make_hive_event("a1"))
    store.ingest(_make_hive_event("a2"))
    s = store.summary()
    assert s["total_events"] == 2
    assert "a1" in s["agents"]
    assert "a2" in s["agents"]


def test_clear():
    store = SharedStoreAdapter()
    store.ingest(_make_hive_event("a1"))
    store.clear()
    assert store.total_events == 0


def test_max_events_trimming():
    store = SharedStoreAdapter(max_events=5)
    for i in range(10):
        store.ingest(_make_hive_event("a1", payload={"i": i}))
    assert store.total_events == 5


# ── Adapter registration ────────────────────────────────

def test_register_unregister():
    store = SharedStoreAdapter()
    stub = StubAgentAdapter("a1")
    store.register_adapter(stub)
    assert store.query_agent("a1") == []  # empty but registered
    store.unregister_adapter("a1")
    assert store.query_agent("a1") == []  # unregistered
