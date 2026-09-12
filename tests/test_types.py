"""Tests for core typed records."""

from schemas.types import (
    Event, EventKind, Severity, Resource, ResourceKind,
    Plan, Receipt, IncidentReport, HiveProfile, ProfileTier,
)


class TestEvent:
    def test_create_default(self):
        e = Event()
        assert e.id.startswith("evt_")
        assert e.kind == EventKind.OBSERVATION
        assert e.severity == Severity.INFO

    def test_to_dict_from_dict_roundtrip(self):
        e = Event(
            kind=EventKind.INCIDENT,
            source="test_collector",
            subject="cpu",
            payload={"temp": 80},
            severity=Severity.WARN,
        )
        d = e.to_dict()
        assert d["kind"] == "incident"
        assert d["severity"] == "warn"
        assert d["payload"]["temp"] == 80

        e2 = Event.from_dict(d)
        assert e2.kind == EventKind.INCIDENT
        assert e2.severity == Severity.WARN
        assert e2.source == "test_collector"
        assert e2.payload["temp"] == 80

    def test_unique_ids(self):
        e1 = Event()
        e2 = Event()
        assert e1.id != e2.id


class TestResource:
    def test_create_and_serialize(self):
        r = Resource(kind=ResourceKind.SERVICE, name="nginx",
                     attributes={"port": 80})
        d = r.to_dict()
        assert d["kind"] == "service"
        assert d["name"] == "nginx"
        assert d["attributes"]["port"] == 80

        r2 = Resource.from_dict(d)
        assert r2.kind == ResourceKind.SERVICE
        assert r2.name == "nginx"


class TestPlan:
    def test_create_with_steps(self):
        p = Plan(
            incident_id="inc_123",
            steps=[{"verb": "restart", "command": "systemctl restart nginx"}],
        )
        assert p.status == "proposed"
        assert len(p.steps) == 1
        assert p.id.startswith("plan_")

    def test_roundtrip(self):
        p = Plan(incident_id="inc_abc", steps=[{"verb": "test"}])
        d = p.to_dict()
        p2 = Plan.from_dict(d)
        assert p2.incident_id == "inc_abc"
        assert p2.steps == [{"verb": "test"}]


class TestReceipt:
    def test_default_receipt(self):
        r = Receipt()
        assert r.id.startswith("rcpt_")
        assert r.verified is False
        assert r.exit_code == 0

    def test_roundtrip(self):
        r = Receipt(verb="restart", target="nginx", exit_code=0,
                    stdout="ok", verified=True)
        d = r.to_dict()
        r2 = Receipt.from_dict(d)
        assert r2.verb == "restart"
        assert r2.verified is True


class TestIncidentReport:
    def test_create(self):
        inc = IncidentReport(
            severity=Severity.ERROR,
            component="disk",
            symptom="full",
            evidence=[{"key": "val"}],
        )
        assert inc.id.startswith("inc_")
        assert inc.resolved is False
        d = inc.to_dict()
        assert d["severity"] == "error"

    def test_roundtrip(self):
        inc = IncidentReport(component="mem", symptom="oom")
        d = inc.to_dict()
        inc2 = IncidentReport.from_dict(d)
        assert inc2.component == "mem"
        assert inc2.symptom == "oom"


class TestHiveProfile:
    def test_create_with_resources(self):
        r = Resource(kind=ResourceKind.NETWORK, name="eth0")
        p = HiveProfile(
            hostname="test-host",
            os="Linux 6.1",
            tier=ProfileTier.OBSERVED,
            resources=[r],
            tags=["m0"],
        )
        d = p.to_dict()
        assert d["tier"] == "observed"
        assert d["hostname"] == "test-host"
        assert len(d["resources"]) == 1

        p2 = HiveProfile.from_dict(d)
        assert p2.tier == ProfileTier.OBSERVED
        assert p2.hostname == "test-host"
        assert len(p2.resources) == 1
        assert p2.resources[0].kind == ResourceKind.NETWORK
