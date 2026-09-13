"""Tests for the appliance controller (P0-fixed)."""
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
        """F10: Appliance can record incidents directly."""
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

    def test_replay_on_startup(self):
        """F10: Appliance replays events from store on startup."""
        from schemas.event_store import EventStore
        s = EventStore()
        s.append(Event(kind=EventKind.OBSERVATION, source="file_collector",
                       subject="/etc/missing",
                       payload={"exists": False, "path": "/etc/missing"}))
        from controller.appliance import Appliance as App
        import controller.appliance as appmod
        with __import__('unittest.mock').mock.patch.object(appmod, 'EventStore', return_value=s):
            app = App(":memory:")
        # F10: Should have replayed the event and found the incident
        assert len(app.open_incidents()) == 1
        app.close()
