"""Tests for the SQLite event store."""

import os
import tempfile

import pytest

from schemas.event_store import EventStore
from schemas.types import Event, EventKind, Severity


class TestEventStore:
    def test_append_and_get(self):
        store = EventStore(":memory:")
        e = Event(source="test", subject="cpu", payload={"temp": 70})
        store.append(e)
        retrieved = store.get(e.id)
        assert retrieved is not None
        assert retrieved.source == "test"
        assert retrieved.payload["temp"] == 70
        store.close()

    def test_duplicate_id_raises(self):
        store = EventStore(":memory:")
        e = Event(id="evt_fixed", source="test")
        store.append(e)
        with pytest.raises(ValueError, match="already exists"):
            store.append(e)
        store.close()

    def test_query_by_kind(self):
        store = EventStore(":memory:")
        store.append(Event(kind=EventKind.OBSERVATION, source="a"))
        store.append(Event(kind=EventKind.INCIDENT, source="b"))
        store.append(Event(kind=EventKind.OBSERVATION, source="c"))

        obs = store.query(kind=EventKind.OBSERVATION)
        assert len(obs) == 2

        inc = store.query(kind="incident")
        assert len(inc) == 1
        store.close()

    def test_query_by_source(self):
        store = EventStore(":memory:")
        store.append(Event(source="collector_a", subject="x"))
        store.append(Event(source="collector_b", subject="y"))

        results = store.query(source="collector_a")
        assert len(results) == 1
        assert results[0].source == "collector_a"
        store.close()

    def test_query_by_severity(self):
        store = EventStore(":memory:")
        store.append(Event(severity=Severity.WARN, source="a"))
        store.append(Event(severity=Severity.ERROR, source="b"))
        store.append(Event(severity=Severity.WARN, source="c"))

        warns = store.query(severity="warn")
        assert len(warns) == 2
        store.close()

    def test_count(self):
        store = EventStore(":memory:")
        assert store.count() == 0
        store.append(Event(source="a"))
        store.append(Event(source="b"))
        assert store.count() == 2
        store.close()

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.db")
            store = EventStore(path)
            e = Event(source="persistent", subject="disk")
            store.append(e)
            store.close()

            store2 = EventStore(path)
            retrieved = store2.get(e.id)
            assert retrieved is not None
            assert retrieved.source == "persistent"
            store2.close()

    def test_kv_store(self):
        store = EventStore(":memory:")
        store.set_kv("profile_id", "prof_abc")
        assert store.get_kv("profile_id") == "prof_abc"
        assert store.get_kv("nonexistent", "default") == "default"
        store.close()

    def test_query_limit(self):
        store = EventStore(":memory:")
        for i in range(50):
            store.append(Event(source=f"src_{i}"))
        results = store.query(limit=10)
        assert len(results) == 10
        store.close()
