"""Tests for the controller reducer.

P0 fix: F7 - Individual receipts no longer resolve incidents.
         Only composite (all steps verified) resolves.
         F10: Deterministic incident IDs for stable replay.
"""
from controller.reducer import Reducer
from schemas.types import Event, EventKind, Severity, IncidentReport


class TestReducer:
    def test_state_update_on_observation(self):
        r = Reducer()
        e = Event(kind=EventKind.OBSERVATION, source="host",
                  subject="cpu", payload={"cores": 4})
        incidents = r.reduce(e)
        assert len(incidents) == 0
        assert r.state["cpu"]["cores"] == 4

    def test_missing_file_incident(self):
        r = Reducer()
        e = Event(kind=EventKind.OBSERVATION, source="file_collector",
                  subject="/etc/missing", payload={"exists": False})
        incidents = r.reduce(e)
        assert len(incidents) == 1
        assert incidents[0].symptom == "file_missing"
        assert incidents[0].component == "/etc/missing"
        assert incidents[0].severity == Severity.WARN

    def test_error_payload_incident(self):
        r = Reducer()
        e = Event(kind=EventKind.OBSERVATION, source="host",
                  subject="/proc/x", payload={"error": "permission denied"})
        incidents = r.reduce(e)
        assert len(incidents) == 1
        assert incidents[0].symptom == "collection_error"
        assert incidents[0].severity == Severity.ERROR

    def test_open_incidents(self):
        r = Reducer()
        e = Event(kind=EventKind.OBSERVATION, source="file_collector",
                  subject="/missing", payload={"exists": False})
        r.reduce(e)
        assert len(r.open_incidents()) == 1

    def test_receipt_does_not_resolve_incident(self):
        """F7: Individual receipts should NOT resolve incidents.
        Only the appliance's composite success check resolves.
        """
        r = Reducer()
        inc = IncidentReport(component="/etc/test", symptom="file_missing",
                             plan_id="plan_123")
        r.incidents.append(inc)
        assert len(r.open_incidents()) == 1

        # Simulate a single verified receipt - should NOT resolve
        e = Event(kind=EventKind.RECEIPT, source="verifier",
                  subject="/etc/test", payload={"plan_id": "plan_123", "verified": True})
        r.reduce(e)
        assert len(r.open_incidents()) == 1  # F7: still open

    def test_resolve_incident_explicit(self):
        """F7: Explicit resolution via resolve_incident works."""
        r = Reducer()
        inc = IncidentReport(component="/etc/test", symptom="file_missing",
                             plan_id="plan_123")
        r.incidents.append(inc)
        r.resolve_incident(inc.id, "plan_123")
        assert len(r.open_incidents()) == 0

    def test_snapshot(self):
        r = Reducer()
        r.reduce(Event(kind=EventKind.OBSERVATION, source="h",
                       subject="cpu", payload={"cores": 2}))
        snap = r.snapshot()
        assert "state" in snap
        assert snap["incidents_total"] == 0
        assert snap["incidents_open"] == 0
