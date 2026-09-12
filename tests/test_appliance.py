"""Tests for the appliance controller."""

from controller.appliance import Appliance
from schemas.types import Event, EventKind, Severity, IncidentReport


class TestAppliance:
    def test_observe_with_no_collectors(self):
        app = Appliance(":memory:")
        events = app.observe()
        assert events == []
        assert app.event_count() == 0
        app.close()

    def test_observe_creates_events(self):
        from collectors.file_collector import FileCollector
        app = Appliance(":memory:")
        app.add_collector(FileCollector(["/etc/hostname"]))
        events = app.observe()
        assert len(events) >= 1
        assert app.event_count() >= 1
        app.close()

    def test_record_incident(self):
        app = Appliance(":memory:")
        inc = IncidentReport(component="disk", symptom="full")
        app.record_incident(inc)
        assert app.event_count() == 1
        app.close()

    def test_state_snapshot(self):
        app = Appliance(":memory:")
        snap = app.state_snapshot()
        assert "state" in snap
        app.close()
