"""
Core typed records for the Omega Hive Appliance.

P0 fixes: F2(strict plan schema), F6(receipt attempt_id), F8(attempt_id), 
F10(deterministic incident IDs).
"""
from __future__ import annotations

import hashlib
import json
import uuid
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


def _now() -> float:
    return time.time()

def _uid(prefix: str = "") -> str:
    return prefix + uuid.uuid4().hex[:16]

def _deterministic_id(prefix: str, *parts: str) -> str:
    raw = "|".join(str(p) for p in parts)
    h = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return prefix + h


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
    SIMULATED = "simulated"

class ResourceKind(str, Enum):
    SERVICE = "service"
    FILE = "file"
    PACKAGE = "package"
    PROCESS = "process"
    NETWORK = "network"
    VOLUME = "volume"
    CONFIG = "config"

class ProfileTier(str, Enum):
    UNKNOWN = "unknown"
    OBSERVED = "observed"
    MANAGED = "managed"
    PACKAGED = "packaged"
    RECOVERABLE = "recoverable"
    NIXOS = "nixos"

ALLOWED_VERBS = frozenset({"touch", "verify", "inspect", "restart", "noop"})

_PLAN_KNOWN_FIELDS = frozenset({
    "id", "ts", "incident_id", "steps", "status",
    "principal", "grant", "expiry", "digest",
    "attempt_id", "schema_version",
})
_PLAN_STEP_KNOWN_FIELDS = frozenset({
    "verb", "command", "expected", "timeout", "target",
})


@dataclass
class Resource:
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
        return cls(kind=ResourceKind(d["kind"]), name=d["name"],
                   attributes=d.get("attributes", {}),
                   schema_version=d.get("schema_version", "1"))


@dataclass
class Event:
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
        return cls(id=d.get("id", _uid("evt_")),
                   kind=EventKind(d.get("kind", "observation")),
                   ts=d.get("ts", _now()), source=d.get("source", ""),
                   subject=d.get("subject", ""), payload=d.get("payload", {}),
                   severity=Severity(d.get("severity", "info")),
                   schema_version=d.get("schema_version", "1"))


@dataclass
class Plan:
    """F2: strict schema; F8: attempt_id for dedup."""
    id: str = field(default_factory=lambda: _uid("plan_"))
    ts: float = field(default_factory=_now)
    incident_id: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    status: str = "proposed"
    principal: str = ""
    grant: str = ""
    expiry: float = 0.0
    digest: str = ""
    attempt_id: str = ""
    schema_version: str = "2"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Plan":
        unknown = set(d.keys()) - _PLAN_KNOWN_FIELDS
        if unknown:
            raise ValueError(f"Unknown plan fields: {unknown}")
        return cls(id=d.get("id", _uid("plan_")), ts=d.get("ts", _now()),
                   incident_id=d.get("incident_id", ""),
                   steps=d.get("steps", []), status=d.get("status", "proposed"),
                   principal=d.get("principal", ""), grant=d.get("grant", ""),
                   expiry=d.get("expiry", 0.0), digest=d.get("digest", ""),
                   attempt_id=d.get("attempt_id", ""),
                   schema_version=d.get("schema_version", "2"))

    def compute_digest(self) -> str:
        content = json.dumps({"incident_id": self.incident_id,
                              "steps": self.steps, "principal": self.principal,
                              "grant": self.grant}, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def validate(self) -> list[str]:
        errors: list[str] = []
        for i, step in enumerate(self.steps):
            if not isinstance(step, dict):
                errors.append(f"Step {i}: not a dict")
                continue
            verb = step.get("verb", "")
            if verb not in ALLOWED_VERBS:
                errors.append(f"Step {i}: verb not allowed: {verb}")
            unknown_step = set(step.keys()) - _PLAN_STEP_KNOWN_FIELDS
            if unknown_step:
                errors.append(f"Step {i}: unknown fields {unknown_step}")
        return errors


@dataclass
class Receipt:
    """F6: verified set by verifier not executor; F8: attempt_id."""
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
    simulated: bool = False
    attempt_id: str = ""
    schema_version: str = "2"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Receipt":
        return cls(id=d.get("id", _uid("rcpt_")), ts=d.get("ts", _now()),
                   plan_id=d.get("plan_id", ""),
                   step_index=d.get("step_index", 0),
                   verb=d.get("verb", ""), target=d.get("target", ""),
                   exit_code=d.get("exit_code", 0),
                   stdout=d.get("stdout", ""), stderr=d.get("stderr", ""),
                   duration_ms=d.get("duration_ms", 0.0),
                   verified=d.get("verified", False),
                   simulated=d.get("simulated", False),
                   attempt_id=d.get("attempt_id", ""),
                   schema_version=d.get("schema_version", "2"))


@dataclass
class IncidentReport:
    """F10: deterministic ID for stable replay."""
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
        return cls(id=d.get("id", _uid("inc_")), ts=d.get("ts", _now()),
                   severity=Severity(d.get("severity", "warn")),
                   component=d.get("component", ""),
                   symptom=d.get("symptom", ""),
                   evidence=d.get("evidence", []),
                   plan_id=d.get("plan_id"),
                   resolved=d.get("resolved", False),
                   schema_version=d.get("schema_version", "1"))

    @classmethod
    def deterministic(cls, component: str, symptom: str,
                      severity: Severity = Severity.WARN,
                      evidence: list | None = None) -> "IncidentReport":
        inc_id = _deterministic_id("inc_", component, symptom)
        return cls(id=inc_id, severity=severity, component=component,
                   symptom=symptom, evidence=evidence or [])


@dataclass
class HiveProfile:
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
        d["resources"] = [r.to_dict() if isinstance(r, Resource) else r
                          for r in self.resources]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "HiveProfile":
        resources = [Resource.from_dict(r) if isinstance(r, dict) else r
                     for r in d.get("resources", [])]
        return cls(id=d.get("id", _uid("prof_")), ts=d.get("ts", _now()),
                   hostname=d.get("hostname", ""), os=d.get("os", ""),
                   kernel=d.get("kernel", ""),
                   tier=ProfileTier(d.get("tier", "unknown")),
                   resources=resources, tags=d.get("tags", []),
                   schema_version=d.get("schema_version", "1"))
