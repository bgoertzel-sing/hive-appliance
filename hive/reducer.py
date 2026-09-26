"""
HiveReducer — consumes HiveEventBus stream and derives hive-level state.

M5 component: performs cross-agent incident correlation, agent health
rollup, resource aggregation, and drift detection.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from hive.types import (
    AgentHealth,
    AgentHealthSummary,
    HiveEvent,
    HiveIncident,
    HiveState,
)
from schemas.types import EventKind, Severity

logger = logging.getLogger(__name__)

# ── Correlation config ───────────────────────────────────

DEFAULT_CORRELATION_WINDOW = 300.0  # seconds
DEFAULT_CORRELATION_THRESHOLD = 2   # min agents for cross-agent incident
MAX_AGENT_INCIDENTS = 500           # per-agent incident history cap
MAX_HIVE_INCIDENTS = 1000           # total hive-level incident cap

# H1: severity ordering used when merging polled health with reducer state
_HEALTH_RANK = {
    AgentHealth.UNKNOWN: 0,
    AgentHealth.HEALTHY: 1,
    AgentHealth.DEGRADED: 2,
    AgentHealth.FAILED: 3,
}


class HiveReducer:
    """Processes HiveEvents and maintains HiveState.

    Key reduction rules:
    - Agent health rollup from latest state snapshots
    - Incident correlation: same symptom across N agents within time window
    - Resource aggregation across agents
    - Drift detection (config/version divergence)
    """

    def __init__(
        self,
        correlation_window: float = DEFAULT_CORRELATION_WINDOW,
        correlation_threshold: int = DEFAULT_CORRELATION_THRESHOLD,
    ):
        self._state = HiveState()
        self._correlation_window = correlation_window
        self._correlation_threshold = correlation_threshold
        # Track per-agent incident events for correlation
        self._agent_incidents: dict[str, list[dict[str, Any]]] = {}
        # Track seen hive incident IDs for dedup
        self._seen_hive_incidents: set[str] = set()
        # H2: receipt identities already applied (replay dedupe)
        self._seen_receipts: set[str] = set()

    @property
    def state(self) -> HiveState:
        """Return state."""
        return self._state

    def reduce(self, hive_event: HiveEvent) -> list[HiveIncident]:
        """Process a HiveEvent and return any new HiveIncidents."""
        new_incidents: list[HiveIncident] = []
        agent_id = hive_event.source_agent
        event = hive_event.original_event

        if event is None:
            return new_incidents

        # Update agent last-event timestamp
        if agent_id in self._state.agents:
            self._state.agents[agent_id].last_event_ts = event.ts
            self._state.agents[agent_id].last_updated = time.time()

        # Handle by event kind
        if event.kind == EventKind.INCIDENT:
            new_incidents.extend(self._handle_incident(agent_id, event))
        elif event.kind == EventKind.OBSERVATION:
            self._handle_observation(agent_id, event)
        elif event.kind == EventKind.RECEIPT:
            self._handle_receipt(agent_id, event)

        self._state.last_updated = time.time()
        return new_incidents

    def update_agent_health(self, agent_id: str, summary: AgentHealthSummary) -> None:
        """Update an agent's health summary directly (from polling).

        If the reducer has unresolved incidents for this agent, polled
        health is overridden to at least DEGRADED (or FAILED for
        critical/error incidents) so that a healthy poll cannot mask
        active incident state.
        """
        # H1: merge for every poll, not only HEALTHY ones.  A non-healthy
        # poll (e.g. DEGRADED with open_incidents=0) must not erase the
        # reducer's open-incident count or downgrade FAILED to DEGRADED.
        open_list = self._open_agent_incidents(agent_id)
        if open_list:
            has_critical = any(
                i.get("severity") in ("critical", "error") for i in open_list
            )
            floor = AgentHealth.FAILED if has_critical else AgentHealth.DEGRADED
            if _HEALTH_RANK.get(summary.health, 0) < _HEALTH_RANK[floor]:
                summary.health = floor
            summary.open_incidents = max(summary.open_incidents, len(open_list))
        self._state.agents[agent_id] = summary
        self._state.last_updated = time.time()

    def _open_agent_incidents(self, agent_id: str) -> list[dict[str, Any]]:
        return [i for i in self._agent_incidents.get(agent_id, [])
                if not i.get("resolved")]

    def _recompute_agent_health(self, agent_id: str) -> None:
        summary = self._state.agents.get(agent_id)
        if summary is None:
            return
        open_list = self._open_agent_incidents(agent_id)
        summary.open_incidents = len(open_list)
        if not open_list:
            if summary.health in (AgentHealth.FAILED, AgentHealth.DEGRADED):
                summary.health = AgentHealth.HEALTHY
        elif any(i.get("severity") in ("critical", "error") for i in open_list):
            summary.health = AgentHealth.FAILED
        elif _HEALTH_RANK.get(summary.health, 0) < _HEALTH_RANK[AgentHealth.DEGRADED]:
            summary.health = AgentHealth.DEGRADED

    def register_agent(self, agent_id: str) -> None:
        """Register a new agent in hive state."""
        if agent_id not in self._state.agents:
            self._state.agents[agent_id] = AgentHealthSummary(agent_id=agent_id)
            self._agent_incidents[agent_id] = []
            logger.info("Registered agent %s in reducer", agent_id)

    def unregister_agent(self, agent_id: str) -> None:
        """Remove an agent from hive state."""
        self._state.agents.pop(agent_id, None)
        self._agent_incidents.pop(agent_id, None)
        logger.info("Unregistered agent %s from reducer", agent_id)

    def update_resources(self, agent_id: str,
                         disk_total: int = 0, disk_used: int = 0,
                         memory_total: int = 0, memory_used: int = 0,
                         cpu_percent: float = 0.0) -> list[str]:
        """Update resource metrics for an agent. Returns any threshold alerts."""
        res = self._state.resources
        res.agent_resources[agent_id] = {
            "disk_total": disk_total,
            "disk_used": disk_used,
            "memory_total": memory_total,
            "memory_used": memory_used,
            "cpu_percent": cpu_percent,
        }

        # Reaggregate totals
        res.total_disk_bytes = sum(
            r.get("disk_total", 0) for r in res.agent_resources.values()
        )
        res.used_disk_bytes = sum(
            r.get("disk_used", 0) for r in res.agent_resources.values()
        )
        res.total_memory_bytes = sum(
            r.get("memory_total", 0) for r in res.agent_resources.values()
        )
        res.used_memory_bytes = sum(
            r.get("memory_used", 0) for r in res.agent_resources.values()
        )
        res.total_cpu_percent = sum(
            r.get("cpu_percent", 0.0) for r in res.agent_resources.values()
        )

        return res.alerts()

    # ── private handlers ──────────────────────────────────

    def _handle_incident(self, agent_id: str, event: Any) -> list[HiveIncident]:
        """Handle an incident event from an agent."""
        new_incidents: list[HiveIncident] = []
        payload = event.payload
        symptom = payload.get("symptom", payload.get("message", "unknown"))

        # Track per-agent incident with cap
        if agent_id not in self._agent_incidents:
            self._agent_incidents[agent_id] = []
        incidents_list = self._agent_incidents[agent_id]
        # H2: incidents are keyed by their identity (deterministic incident
        # id from the payload), not by the carrying event id, so replayed or
        # re-emitted incident events do not inflate open_incidents.
        identity = payload.get("id") or event.id
        existing = next((i for i in incidents_list
                         if i["incident_id"] == identity), None)
        if existing is not None:
            existing["ts"] = max(existing["ts"], event.ts)
            if payload.get("resolved"):
                existing["resolved"] = True
            self._recompute_agent_health(agent_id)
            return new_incidents
        incidents_list.append({
            "incident_id": identity,
            "ts": event.ts,
            "symptom": symptom,
            "severity": payload.get("severity", "warn"),
            "plan_id": payload.get("plan_id", ""),
            "resolved": bool(payload.get("resolved", False)),
        })
        # Prune old entries beyond cap -- resolved ones first, never open ones
        if len(incidents_list) > MAX_AGENT_INCIDENTS:
            overflow = len(incidents_list) - MAX_AGENT_INCIDENTS
            kept, dropped = [], 0
            for i in incidents_list:
                if dropped < overflow and i.get("resolved"):
                    dropped += 1
                    continue
                kept.append(i)
            self._agent_incidents[agent_id] = kept[-MAX_AGENT_INCIDENTS:] if dropped < overflow else kept

        # Update agent health
        self._recompute_agent_health(agent_id)

        # Attempt cross-agent correlation
        correlated = self._correlate_incidents(symptom, event.ts)
        if correlated:
            new_incidents.append(correlated)

        logger.debug(
            "Handled incident from agent %s: symptom=%s", agent_id, symptom
        )
        return new_incidents

    def _correlate_incidents(self, symptom: str, ts: float) -> HiveIncident | None:
        """Check if this symptom appears across enough agents within the window."""
        cutoff = ts - self._correlation_window
        affected_agents: list[str] = []
        source_ids: list[str] = []

        for agent_id, incidents in self._agent_incidents.items():
            for inc in incidents:
                if (inc["symptom"] == symptom and inc["ts"] >= cutoff):
                    if agent_id not in affected_agents:
                        affected_agents.append(agent_id)
                    source_ids.append(inc["incident_id"])

        if len(affected_agents) >= self._correlation_threshold:
            # Create deterministic hive incident
            hinc = HiveIncident.deterministic(
                symptom=symptom,
                affected_agents=affected_agents,
                source_incidents=source_ids,
                severity=Severity.ERROR,
            )
            if hinc.id not in self._seen_hive_incidents:
                self._seen_hive_incidents.add(hinc.id)
                self._state.incidents.append(hinc)
                # Cap hive incidents list
                if len(self._state.incidents) > MAX_HIVE_INCIDENTS:
                    # Keep only resolved + most recent unresolved
                    resolved = [i for i in self._state.incidents if i.resolved]
                    unresolved = [i for i in self._state.incidents if not i.resolved]
                    self._state.incidents = resolved[-MAX_HIVE_INCIDENTS // 2:] + unresolved[-MAX_HIVE_INCIDENTS // 2:]
                logger.info(
                    "Correlated hive incident %s: symptom=%s, agents=%s",
                    hinc.id, symptom, affected_agents,
                )
                return hinc

        return None

    def _handle_observation(self, agent_id: str, event: Any) -> None:
        """Update agent state from observations."""
        if agent_id in self._state.agents:
            summary = self._state.agents[agent_id]
            payload = event.payload

            # Update services if service observation
            if "service" in payload:
                svc = payload["service"]
                active = payload.get("active", "unknown")
                summary.services[svc] = active

    def _handle_receipt(self, agent_id: str, event: Any) -> None:
        """Handle repair receipt — may resolve an agent's incident."""
        # H2: a receipt resolves a specific incident (matched by incident_id
        # or plan_id) at most once; replayed receipts are ignored.
        payload = event.payload
        if not payload.get("verified", False):
            return
        rid = payload.get("id") or event.id
        key = f"{agent_id}:{rid}"
        if key in self._seen_receipts:
            logger.debug("Ignoring replayed receipt %s from %s", rid, agent_id)
            return
        self._seen_receipts.add(key)
        open_list = self._open_agent_incidents(agent_id)
        target = None
        inc_id = payload.get("incident_id", "")
        plan_id = payload.get("plan_id", "")
        if inc_id:
            target = next((i for i in open_list if i["incident_id"] == inc_id), None)
        if target is None and plan_id:
            target = next((i for i in open_list if i.get("plan_id") == plan_id), None)
        if target is None and not inc_id and not plan_id and open_list:
            target = open_list[0]  # legacy: untargeted receipt -> oldest open
        if target is None:
            return
        target["resolved"] = True
        self._recompute_agent_health(agent_id)
        logger.info("Agent %s incident %s resolved (verified receipt)",
                    agent_id, target["incident_id"])

    def resolve_hive_incident(self, incident_id: str) -> bool:
        """Mark a hive-level incident as resolved."""
        for inc in self._state.incidents:
            if inc.id == incident_id and not inc.resolved:
                inc.resolved = True
                inc.resolution_ts = time.time()
                logger.info("Resolved hive incident %s", incident_id)
                return True
        return False

    def detect_drift(self) -> list[dict[str, Any]]:
        """Detect configuration/version drift across agents.

        Returns a list of drift observations (service name -> agents with
        differing statuses).
        """
        # Collect all services and their statuses per agent
        service_agents: dict[str, dict[str, str]] = {}  # service -> {agent: status}
        for agent_id, summary in self._state.agents.items():
            for svc, status in summary.services.items():
                service_agents.setdefault(svc, {})[agent_id] = status

        drifts: list[dict[str, Any]] = []
        for svc, agents in service_agents.items():
            statuses = set(agents.values())
            if len(statuses) > 1:
                drifts.append({
                    "service": svc,
                    "agents": dict(agents),
                    "statuses": list(statuses),
                })
        return drifts
