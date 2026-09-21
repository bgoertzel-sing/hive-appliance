"""
HivePlanner — generates hive-level actions from HiveState.

M5 component: inspects the current HiveState, identifies actionable
situations (correlated incidents, resource alerts, drift), and produces
HiveActions that can be delegated to per-agent adapters.

Design principle: request-only authority. The HivePlanner suggests actions
but does not force-execute on agents. The HiveAppliance orchestrator
decides whether to execute.
"""
from __future__ import annotations

import time
from typing import Any

from hive.types import (
    HiveAction,
    HiveActionKind,
    HiveState,
)

# ── Configuration ────────────────────────────────────────

DEFAULT_DISK_CRITICAL = 0.95
DEFAULT_DISK_WARN = 0.80
DEFAULT_MAX_OPEN_INCIDENTS = 5
DEFAULT_AGENT_STALE_SECONDS = 600.0


class HivePlanner:
    """Generates HiveActions from HiveState analysis.

    Rule-based planner with pluggable rules. Each rule inspects the
    current HiveState and returns zero or more proposed HiveActions.
    """

    def __init__(
        self,
        disk_critical: float = DEFAULT_DISK_CRITICAL,
        disk_warn: float = DEFAULT_DISK_WARN,
        max_open_incidents: int = DEFAULT_MAX_OPEN_INCIDENTS,
        agent_stale_seconds: float = DEFAULT_AGENT_STALE_SECONDS,
    ):
        self._disk_critical = disk_critical
        self._disk_warn = disk_warn
        self._max_open_incidents = max_open_incidents
        self._agent_stale_seconds = agent_stale_seconds
        self._custom_rules: list[Any] = []
        self._action_log: list[HiveAction] = []

    @property
    def action_log(self) -> list[HiveAction]:
        return list(self._action_log)

    def add_rule(self, rule_fn) -> None:
        """Add a custom planning rule.

        rule_fn(state: HiveState) -> list[HiveAction]
        """
        self._custom_rules.append(rule_fn)

    def plan(self, state: HiveState) -> list[HiveAction]:
        """Analyze current HiveState and return proposed actions.

        Built-in rules:
        1. Correlated incident response — delegate repairs
        2. Resource threshold alerts — coordinate if critical
        3. Failed agent response — checkpoint healthy neighbors
        4. Stale agent detection — flag agents that stopped reporting
        5. Custom rules
        """
        actions: list[HiveAction] = []

        actions.extend(self._rule_correlated_incidents(state))
        actions.extend(self._rule_resource_thresholds(state))
        actions.extend(self._rule_failed_agents(state))
        actions.extend(self._rule_stale_agents(state))

        # Custom rules
        for rule_fn in self._custom_rules:
            try:
                custom_actions = rule_fn(state)
                if custom_actions:
                    actions.extend(custom_actions)
            except Exception:
                pass  # Don't let broken custom rules crash planning

        self._action_log.extend(actions)
        return actions

    def _rule_correlated_incidents(self, state: HiveState) -> list[HiveAction]:
        """For each open correlated incident, propose delegate_repair to affected agents."""
        actions: list[HiveAction] = []
        for inc in state.open_incidents:
            if len(inc.affected_agents) >= 2:
                action = HiveAction(
                    kind=HiveActionKind.DELEGATE_REPAIR,
                    target_agents=list(inc.affected_agents),
                    incident_id=inc.id,
                    parameters={
                        "symptom": inc.symptom,
                        "source_incidents": inc.source_incidents,
                    },
                    status="proposed",
                )
                actions.append(action)
        return actions

    def _rule_resource_thresholds(self, state: HiveState) -> list[HiveAction]:
        """If hive-level resources are critical, propose coordination."""
        actions: list[HiveAction] = []
        res = state.resources

        if res.disk_usage_ratio >= self._disk_critical:
            # Critical: coordinate across all agents
            actions.append(HiveAction(
                kind=HiveActionKind.COORDINATE,
                target_agents=list(state.agents.keys()),
                parameters={
                    "reason": "disk_critical",
                    "disk_usage": res.disk_usage_ratio,
                },
                status="proposed",
            ))

        return actions

    def _rule_failed_agents(self, state: HiveState) -> list[HiveAction]:
        """If an agent is failed, checkpoint healthy neighbors."""
        actions: list[HiveAction] = []
        failed = state.failed_agents
        healthy = state.healthy_agents

        if failed and healthy:
            actions.append(HiveAction(
                kind=HiveActionKind.CHECKPOINT_ALL,
                target_agents=healthy,
                parameters={
                    "reason": "neighbor_failure",
                    "failed_agents": failed,
                },
                status="proposed",
            ))

        return actions

    def _rule_stale_agents(self, state: HiveState) -> list[HiveAction]:
        """Detect agents that haven't reported events recently."""
        actions: list[HiveAction] = []
        now = time.time()

        for agent_id, summary in state.agents.items():
            if summary.last_event_ts > 0:
                gap = now - summary.last_event_ts
                if gap > self._agent_stale_seconds:
                    actions.append(HiveAction(
                        kind=HiveActionKind.COORDINATE,
                        target_agents=[agent_id],
                        parameters={
                            "reason": "stale_agent",
                            "last_event_gap_seconds": gap,
                        },
                        status="proposed",
                    ))

        return actions
