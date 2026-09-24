"""
Hive-level typed records for the M5 Hive Appliance.

Extends the per-agent schemas/types.py with cross-agent concepts:
HiveEvent, AgentIdentity, AgentHealthSummary, HiveIncident, HiveState,
HiveResourceState, HiveAction, HiveActionResult.
"""
from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional

# Re-export base types used by hive layer
from schemas.types import Event, Severity

# ── helpers ──────────────────────────────────────────────

def _now() -> float:
    return time.time()


def _uid(prefix: str = "") -> str:
    return prefix + uuid.uuid4().hex[:16]


def _deterministic_id(prefix: str, *parts: str) -> str:
    raw = "|".join(str(p) for p in parts)
    h = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return prefix + h


# ── enums ────────────────────────────────────────────────

class AgentHealth(str, Enum):
    """AgentHealth class."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNKNOWN = "unknown"


class HiveActionKind(str, Enum):
    """HiveActionKind class."""
    RESTART_AGENT = "restart_agent"
    CHECKPOINT_ALL = "checkpoint_all"
    ROLLING_UPGRADE = "rolling_upgrade"
    REBALANCE = "rebalance"
    DELEGATE_REPAIR = "delegate_repair"
    COORDINATE = "coordinate"


# ── records ──────────────────────────────────────────────

@dataclass
class AgentIdentity:
    """Identity of a registered agent in the hive."""
    agent_id: str              # e.g. "protomega2"
    display_name: str = ""     # e.g. "ProtoMegaBot2"
    appliance_path: str = ""   # e.g. "/hive/protomega2/work/hive-appliance"

    def to_dict(self) -> dict[str, Any]:
        """Execute to dict operation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AgentIdentity:
        """Execute from dict operation."""
        return cls(
            agent_id=d["agent_id"],
            display_name=d.get("display_name", ""),
            appliance_path=d.get("appliance_path", ""),
        )


@dataclass
class HiveEvent:
    """An event tagged with its source agent for the hive event bus."""
    id: str = field(default_factory=lambda: _uid("hevt_"))
    source_agent: str = ""
    original_event: Optional[Event] = None
    hive_received_at: float = field(default_factory=_now)
    schema_version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        """Execute to dict operation."""
        d = asdict(self)
        if self.original_event:
            d["original_event"] = self.original_event.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> HiveEvent:
        """Execute from dict operation."""
        orig = None
        if d.get("original_event"):
            orig = Event.from_dict(d["original_event"])
        return cls(
            id=d.get("id", _uid("hevt_")),
            source_agent=d.get("source_agent", ""),
            original_event=orig,
            hive_received_at=d.get("hive_received_at", _now()),
            schema_version=d.get("schema_version", "1"),
        )


@dataclass
class AgentHealthSummary:
    """Health summary for a single agent."""
    agent_id: str
    health: AgentHealth = AgentHealth.UNKNOWN
    open_incidents: int = 0
    last_event_ts: float = 0.0
    services: dict[str, str] = field(default_factory=dict)  # service -> status
    disk_usage_bytes: int = 0
    cpu_percent: float = 0.0
    memory_bytes: int = 0
    last_updated: float = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        """Execute to dict operation."""
        d = asdict(self)
        d["health"] = self.health.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AgentHealthSummary:
        """Execute from dict operation."""
        return cls(
            agent_id=d["agent_id"],
            health=AgentHealth(d.get("health", "unknown")),
            open_incidents=d.get("open_incidents", 0),
            last_event_ts=d.get("last_event_ts", 0.0),
            services=d.get("services", {}),
            disk_usage_bytes=d.get("disk_usage_bytes", 0),
            cpu_percent=d.get("cpu_percent", 0.0),
            memory_bytes=d.get("memory_bytes", 0),
            last_updated=d.get("last_updated", _now()),
        )


@dataclass
class HiveIncident:
    """A cross-agent correlated incident."""
    id: str = field(default_factory=lambda: _uid("hinc_"))
    symptom: str = ""
    severity: Severity = Severity.WARN
    affected_agents: list[str] = field(default_factory=list)
    source_incidents: list[str] = field(default_factory=list)  # per-agent incident IDs
    correlated_at: float = field(default_factory=_now)
    resolved: bool = False
    resolution_ts: float = 0.0
    evidence: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Execute to dict operation."""
        d = asdict(self)
        d["severity"] = self.severity.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> HiveIncident:
        """Execute from dict operation."""
        return cls(
            id=d.get("id", _uid("hinc_")),
            symptom=d.get("symptom", ""),
            severity=Severity(d.get("severity", "warn")),
            affected_agents=d.get("affected_agents", []),
            source_incidents=d.get("source_incidents", []),
            correlated_at=d.get("correlated_at", _now()),
            resolved=d.get("resolved", False),
            resolution_ts=d.get("resolution_ts", 0.0),
            evidence=d.get("evidence", []),
        )

    @classmethod
    def deterministic(cls, symptom: str, affected_agents: list[str],
                      **kwargs) -> HiveIncident:
        """Create with deterministic ID from symptom + sorted agents."""
        agents_key = ",".join(sorted(affected_agents))
        inc_id = _deterministic_id("hinc_", symptom, agents_key)
        return cls(id=inc_id, symptom=symptom,
                   affected_agents=list(affected_agents), **kwargs)


@dataclass
class HiveResourceState:
    """Aggregated resource usage across the hive."""
    total_disk_bytes: int = 0
    used_disk_bytes: int = 0
    total_memory_bytes: int = 0
    used_memory_bytes: int = 0
    total_cpu_percent: float = 0.0
    agent_resources: dict[str, dict[str, Any]] = field(default_factory=dict)
    thresholds: dict[str, float] = field(default_factory=lambda: {
        "disk_warn": 0.80,
        "disk_critical": 0.95,
        "cpu_warn": 0.80,
        "memory_warn": 0.85,
    })

    @property
    def disk_usage_ratio(self) -> float:
        """Return disk usage ratio."""
        if self.total_disk_bytes == 0:
            return 0.0
        return self.used_disk_bytes / self.total_disk_bytes

    @property
    def memory_usage_ratio(self) -> float:
        """Return memory usage ratio."""
        if self.total_memory_bytes == 0:
            return 0.0
        return self.used_memory_bytes / self.total_memory_bytes

    def alerts(self) -> list[str]:
        """Return list of threshold-breach alert strings."""
        alerts = []
        if self.disk_usage_ratio >= self.thresholds.get("disk_critical", 0.95):
            alerts.append(f"CRITICAL: Disk usage {self.disk_usage_ratio:.1%}")
        elif self.disk_usage_ratio >= self.thresholds.get("disk_warn", 0.80):
            alerts.append(f"WARN: Disk usage {self.disk_usage_ratio:.1%}")
        if self.total_cpu_percent >= self.thresholds.get("cpu_warn", 0.80) * 100:
            alerts.append(f"WARN: CPU usage {self.total_cpu_percent:.1f}%")
        if self.memory_usage_ratio >= self.thresholds.get("memory_warn", 0.85):
            alerts.append(f"WARN: Memory usage {self.memory_usage_ratio:.1%}")
        return alerts

    def to_dict(self) -> dict[str, Any]:
        """Execute to dict operation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> HiveResourceState:
        """Execute from dict operation."""
        return cls(**{k: d[k] for k in d if k in cls.__dataclass_fields__})


@dataclass
class HiveState:
    """Complete hive-level state snapshot."""
    agents: dict[str, AgentHealthSummary] = field(default_factory=dict)
    incidents: list[HiveIncident] = field(default_factory=list)
    resources: HiveResourceState = field(default_factory=HiveResourceState)
    last_updated: float = field(default_factory=_now)
    schema_version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        """Execute to dict operation."""
        return {
            "agents": {k: v.to_dict() for k, v in self.agents.items()},
            "incidents": [i.to_dict() for i in self.incidents],
            "resources": self.resources.to_dict(),
            "last_updated": self.last_updated,
            "schema_version": self.schema_version,
        }

    @property
    def healthy_agents(self) -> list[str]:
        """Return healthy agents."""
        return [k for k, v in self.agents.items() if v.health == AgentHealth.HEALTHY]

    @property
    def degraded_agents(self) -> list[str]:
        """Return degraded agents."""
        return [k for k, v in self.agents.items() if v.health == AgentHealth.DEGRADED]

    @property
    def failed_agents(self) -> list[str]:
        """Return failed agents."""
        return [k for k, v in self.agents.items() if v.health == AgentHealth.FAILED]

    @property
    def open_incidents(self) -> list[HiveIncident]:
        """Return open incidents."""
        return [i for i in self.incidents if not i.resolved]


@dataclass
class HiveAction:
    """An action the HivePlanner wants to execute across agents."""
    id: str = field(default_factory=lambda: _uid("hact_"))
    kind: HiveActionKind = HiveActionKind.DELEGATE_REPAIR
    target_agents: list[str] = field(default_factory=list)
    reason: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    incident_id: str = ""
    status: str = "proposed"

    @property
    def target_agent(self) -> str:
        return self.target_agents[0] if self.target_agents else ""

    @property
    def params(self) -> dict[str, Any]:
        return self.parameters

    def to_dict(self) -> dict[str, Any]:
        """Execute to dict operation."""
        d = asdict(self)
        d["kind"] = self.kind.value
        return d


@dataclass
class HiveActionResult:
    """Result of executing a HiveAction."""
    action_id: str = ""
    success: bool = False
    output: str = ""
    agent_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Execute to dict operation."""
        return asdict(self)
