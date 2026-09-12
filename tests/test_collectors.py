"""Tests for collectors."""

from collectors.host_collector import HostCollector
from collectors.file_collector import FileCollector
from schemas.types import EventKind


class TestHostCollector:
    def test_collect_returns_events(self):
        c = HostCollector()
        events = c.collect()
        assert len(events) >= 1
        assert all(e.source == "host_collector" for e in events)

    def test_discover_profile(self):
        c = HostCollector()
        profile = c.discover_profile()
        assert profile.hostname != ""
        assert profile.tier.value == "observed"
        assert len(profile.resources) >= 1


class TestFileCollector:
    def test_collect_existing_file(self):
        c = FileCollector(["/etc/hostname"])
        events = c.collect()
        assert len(events) == 1
        assert events[0].payload["exists"] is True

    def test_collect_missing_file(self):
        c = FileCollector(["/nonexistent/path/xyz"])
        events = c.collect()
        assert len(events) == 1
        assert events[0].payload["exists"] is False

    def test_custom_paths(self):
        c = FileCollector(["/etc/os-release", "/etc/passwd"])
        events = c.collect()
        assert len(events) == 2
