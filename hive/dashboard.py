"""
Health Dashboard — hive-level health reporting and visualization data.

M5 component: consumes HiveState and produces structured dashboard
data suitable for rendering as text, JSON, or HTML.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

from hive.types import (
    AgentHealth,
    HiveState,
)

logger = logging.getLogger(__name__)


class HealthDashboard:
    """Generates structured health reports from HiveState.

    Provides both machine-readable summaries and human-readable text
    reports for the hive.
    """

    def __init__(self, state: Optional[HiveState] = None):
        self._state = state or HiveState()
        self._snapshots: list[dict[str, Any]] = []
        self._max_snapshots: int = 100

    def update_state(self, state: HiveState) -> None:
        """Update the dashboard with a new HiveState."""
        self._state = state

    def take_snapshot(self) -> dict[str, Any]:
        """Take a point-in-time snapshot for history tracking."""
        snap = self.summary()
        snap["snapshot_ts"] = time.time()
        self._snapshots.append(snap)
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots = self._snapshots[-self._max_snapshots:]
        return snap

    def summary(self) -> dict[str, Any]:
        """Return a structured summary of hive health."""
        state = self._state
        agent_summaries: dict[str, dict[str, Any]] = {}

        for agent_id, health in state.agents.items():
            agent_summaries[agent_id] = {
                "health": health.health.value,
                "open_incidents": health.open_incidents,
                "services": dict(health.services),
                "last_event_ts": health.last_event_ts,
            }

        open_incidents = [
            {
                "id": inc.id,
                "symptom": inc.symptom,
                "severity": inc.severity.value,
                "affected_agents": inc.affected_agents,
                "correlated_at": inc.correlated_at,
            }
            for inc in state.open_incidents
        ]

        resolved_count = len([i for i in state.incidents if i.resolved])

        return {
            "hive_health": self._overall_health().value,
            "agent_count": len(state.agents),
            "healthy_count": len(state.healthy_agents),
            "degraded_count": len(state.degraded_agents),
            "failed_count": len(state.failed_agents),
            "agents": agent_summaries,
            "open_incidents": open_incidents,
            "open_incident_count": len(open_incidents),
            "resolved_incident_count": resolved_count,
            "resource_alerts": state.resources.alerts(),
            "resources": {
                "disk_usage": state.resources.disk_usage_ratio,
                "memory_usage": state.resources.memory_usage_ratio,
                "cpu_total": state.resources.total_cpu_percent,
            },
            "last_updated": state.last_updated,
        }

    def _overall_health(self) -> AgentHealth:
        """Derive overall hive health from agent states."""
        state = self._state
        if not state.agents:
            return AgentHealth.UNKNOWN

        if state.failed_agents:
            return AgentHealth.FAILED
        if state.degraded_agents:
            return AgentHealth.DEGRADED
        return AgentHealth.HEALTHY

    def text_report(self) -> str:
        """Generate a human-readable text health report."""
        try:
            return self._generate_text_report()
        except Exception:
            logger.exception("Error generating text report")
            return "ERROR: Could not generate health report"

    def _generate_text_report(self) -> str:
        """Internal text report generation."""
        s = self._state
        lines: list[str] = []

        lines.append("=" * 60)
        lines.append("  HIVE HEALTH DASHBOARD")
        lines.append("=" * 60)
        lines.append(f"  Overall: {self._overall_health().value.upper()}")
        lines.append(f"  Agents: {len(s.agents)} total | "
                     f"{len(s.healthy_agents)} healthy | "
                     f"{len(s.degraded_agents)} degraded | "
                     f"{len(s.failed_agents)} failed")
        lines.append("")

        # Agent details
        lines.append("  AGENTS:")
        lines.append("  " + "-" * 56)
        for agent_id, summary in sorted(s.agents.items()):
            health_icon = {
                AgentHealth.HEALTHY: "✅",
                AgentHealth.DEGRADED: "⚠️",
                AgentHealth.FAILED: "❌",
                AgentHealth.UNKNOWN: "❓",
            }.get(summary.health, "❓")
            lines.append(
                f"  {health_icon} {agent_id:<20} "
                f"health={summary.health.value:<10} "
                f"incidents={summary.open_incidents}"
            )
            if summary.services:
                for svc, status in sorted(summary.services.items()):
                    lines.append(f"      └─ {svc}: {status}")
        lines.append("")

        # Incidents
        open_inc = s.open_incidents
        if open_inc:
            lines.append(f"  OPEN INCIDENTS ({len(open_inc)}):")
            lines.append("  " + "-" * 56)
            for inc in open_inc:
                lines.append(
                    f"  🔴 [{inc.severity.value.upper()}] {inc.symptom}"
                )
                lines.append(
                    f"      Agents: {', '.join(inc.affected_agents)}"
                )
        else:
            lines.append("  INCIDENTS: None open")
        lines.append("")

        # Resources
        res = s.resources
        alerts = res.alerts()
        lines.append("  RESOURCES:")
        lines.append("  " + "-" * 56)
        lines.append(f"  Disk:   {res.disk_usage_ratio:.1%}")
        lines.append(f"  Memory: {res.memory_usage_ratio:.1%}")
        lines.append(f"  CPU:    {res.total_cpu_percent:.1f}%")
        if alerts:
            for alert in alerts:
                lines.append(f"  ⚠️  {alert}")
        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    @property
    def snapshot_count(self) -> int:
        """Return snapshot count."""
        return len(self._snapshots)

    @property
    def snapshots(self) -> list[dict[str, Any]]:
        """Return snapshots."""
        return list(self._snapshots)
