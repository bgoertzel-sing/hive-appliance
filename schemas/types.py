"""
Core typed records for the Omega Hive Appliance.

All records are dataclasses that serialise to / from JSON-compatible dicts.
Every record carries a versioned schema tag so the event store can evolve.
"""
from __future__ import annotations

import uuid
import time
import dataclasses
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


# ── helpers ──────────────────────────────────────────────

def _now() -> float:
    """UTC epoch seconds."""
    return time.time()


def _uid(prefix: str = "") -> str:
    return prefix + uuid.uuid4().hex[:16]


# ── enums ────────────────────────────────────────────────

class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"


class EventKind(str, Enum):
    OBSERVATION = "observation"
    INCIDENT = "incident"
    ACTION = "action"
    RECEIPT = "receipt"
    RECOVERY = "recovery"
    PLAN = "plan"


class ResourceKind(str, Enum):
    SERVICE = "service"
    FILE = "file"
    PACKAGE = "package"
    PROCESS = "process"
    NETWORK = "network"
    VOLUME = "volume"
    CONFIG = "config"


class ProfileTier(str, Enum):
    """Maturity tier of a hive profile."""
    UNKNOWN = "unknown"
    OBSERVED = "observed"        # M0 — we can see it
    MANAGED = "managed"          # M1 — we can act on it
    PACKAGED = "packaged"        # M2 — reproducible
    RECOVERABLE = "recoverable"  # M3 — state recovery
    NIXOS = "nixos"              # M4 — NixOS VM


# ── records ──────────────────────────────────────────────

@dataclass
class Resource:
    """A discoverable resource on the hive."""
    kind: ResourceKind
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    schema_version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Resource":
        return cls(
            kind=ResourceKind(d["kind"]),
            name=d["name"],
            attributes=d.get("attributes", {}),
            schema_version=d.get("schema_version", "1"),
        )


@dataclass
class Event:
    """An immutable event in the appliance event store."""
    id: str = field(default_factory=lambda: _uid("evt_"))
    kind: EventKind = EventKind.OBSERVATION
    ts: float = field(default_factory=_now)
    source: str = ""
    subject: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    severity: Severity = Severity.INFO
    schema_version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["severity"] = self.severity.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Event":
        return cls(
            id=d.get("id", _uid("evt_")),
            kind=EventKind(d.get("kind", "observation")),
            ts=d.get("ts", _now()),
            source=d.get("source", ""),
            subject=d.get("subject", ""),
            payload=d.get("payload", {}),
            severity=Severity(d.get("severity", "info")),
            schema_version=d.get("schema_version", "1"),
        )


@dataclass
class Plan:
    """A repair plan produced by the Planner."""
    id: str = field(default_factory=lambda: _uid("plan_"))
    ts: float = field(default_factory=_now)
    incident_id: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    status: str = "proposed"
    schema_version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Plan":
        return cls(
            id=d.get("id", _uid("plan_")),
            ts=d.get("ts", _now()),
            incident_id=d.get("incident_id", ""),
            steps=d.get("steps", []),
            status=d.get("status", "proposed"),
            schema_version=d.get("schema_version", "1"),
        )


@dataclass
class Receipt:
    """Authenticated evidence that an action was executed."""
    id: str = field(default_factory=lambda: _uid("rcpt_"))
    ts: float = field(default_factory=_now)
    plan_id: str = ""
    step_index: int = 0
    verb: str = ""
    target: str = ""
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0
    verified: bool = False
    schema_version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Receipt":
        return cls(
            id=d.get("id", _uid("rcpt_")),
            ts=d.get("ts", _now()),
            plan_id=d.get("plan_id", ""),
            step_index=d.get("step_index", 0),
            verb=d.get("verb", ""),
            target=d.get("target", ""),
            exit_code=d.get("exit_code", 0),
            stdout=d.get("stdout", ""),
            stderr=d.get("stderr", ""),
            duration_ms=d.get("duration_ms", 0.0),
            verified=d.get("verified", False),
            schema_version=d.get("schema_version", "1"),
        )


@dataclass
class IncidentReport:
    """An incident raised when observation detects an anomaly."""
    id: str = field(default_factory=lambda: _uid("inc_"))
    ts: float = field(default_factory=_now)
    severity: Severity = Severity.WARN
    component: str = ""
    symptom: str = ""
    evidence: list[dict[str, Any]] = field(default_factory=list)
    plan_id: Optional[str] = None
    resolved: bool = False
    schema_version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "IncidentReport":
        return cls(
            id=d.get("id", _uid("inc_")),
            ts=d.get("ts", _now()),
            severity=Severity(d.get("severity", "warn")),
            component=d.get("component", ""),
            symptom=d.get("symptom", ""),
            evidence=d.get("evidence", []),
            plan_id=d.get("plan_id"),
            resolved=d.get("resolved", False),
            schema_version=d.get("schema_version", "1"),
        )


@dataclass
class HiveProfile:
    """A versioned description of a discovered hive."""
    id: str = field(default_factory=lambda: _uid("prof_"))
    ts: float = field(default_factory=_now)
    hostname: str = ""
    os: str = ""
    kernel: str = ""
    tier: ProfileTier = ProfileTier.UNKNOWN
    resources: list[Resource] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    schema_version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["tier"] = self.tier.value
        d["resources"] = [r.to_dict() if isinstance(r, Resource) else r for r in self.resources]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "HiveProfile":
        resources = [Resource.from_dict(r) if isinstance(r, dict) else r for r in d.get("resources", [])]
        return cls(
            id=d.get("id", _uid("prof_")),
            ts=d.get("ts", _now()),
            hostname=d.get("hostname", ""),
            os=d.get("os", ""),
            kernel=d.get("kernel", ""),
            tier=ProfileTier(d.get("tier", "unknown")),
            resources=resources,
            tags=d.get("tags", []),
            schema_version=d.get("schema_version", "1"),
        )
