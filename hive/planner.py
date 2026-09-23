"""
HivePlanner — generates hive-level actions from HiveState.

M5 component: inspects the current HiveState, identifies actionable
situations (correlated incidents, resource alerts, drift), and produces
HiveActions that can be delegated to per-agent adapters.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable

from hive.types import (
    AgentHealth,
    HiveAction,
    HiveActionKind,
    HiveState,
)

logger = logging.getLogger(__name__)

PlanRule = Callable[[HiveState], list[HiveAction]]


class HivePlanner:
    """Generate hive-level actions from current HiveState.

    Inspects open incidents, resource thresholds, checkpoint needs,
    and produces ordered HiveAction list for the orchestrator.
    """

    def __init__(
        self,
        correlation_threshold: int = 2,
        disk_threshold_pct: float = 0.90,
        disk_critical: float | None = None,
        agent_stale_seconds: float = 300.0,
    ) -> None:
        self._correlation_threshold = correlation_threshold
        self._disk_threshold = disk_critical if disk_critical is not None else disk_threshold_pct
        self._agent_stale_seconds = agent_stale_seconds
        self._custom_rules: list[PlanRule] = []
        self.action_log: list[HiveAction] = []

    def add_rule(self, rule: PlanRule) -> None:
        """Register a custom planning rule."""
        self._custom_rules.append(rule)

    def plan(self, state: HiveState) -> list[HiveAction]:
        """Produce an ordered list of HiveActions from current state.

        Priority order:
        1. Correlated incidents → delegate repair to affected agents
        2. Resource alerts → coordinate / rebalance
        3. Failed agents → checkpoint healthy ones
        4. Stale agents → restart
        5. Custom rules
        """
        actions: list[HiveAction] = []

        # 1. Correlated incidents → delegate repair
        for inc in state.open_incidents:
            if len(inc.affected_agents) >= self._correlation_threshold:
                actions.append(HiveAction(
                    kind=HiveActionKind.DELEGATE_REPAIR,
                    target_agents=list(inc.affected_agents),
                    parameters={"reason": f"correlated_{inc.symptom}",
                                "symptom": inc.symptom,
                                "incident_id": inc.id},
                ))

        # 2. Resource alerts → coordinate
        if state.resources and state.resources.total_disk_bytes > 0:
            disk_pct = state.resources.used_disk_bytes / state.resources.total_disk_bytes
            if disk_pct >= self._disk_threshold:
                all_agents = list(state.agents.keys())
                actions.append(HiveAction(
                    kind=HiveActionKind.COORDINATE,
                    target_agents=all_agents,
                    parameters={"reason": "disk_critical",
                                "disk_usage_pct": disk_pct},
                ))

        # 3. Failed agents → checkpoint healthy ones
        healthy = [aid for aid, h in state.agents.items()
                   if h.health == AgentHealth.HEALTHY]
        failed = [aid for aid, h in state.agents.items()
                  if h.health == AgentHealth.FAILED]
        if failed and healthy:
            actions.append(HiveAction(
                kind=HiveActionKind.CHECKPOINT_ALL,
                target_agents=healthy,
                parameters={"reason": "failed_agent_safeguard",
                            "failed_agents": failed},
            ))

        # 4. Stale agents → restart
        now = time.time()
        for aid, h in state.agents.items():
            if h.last_event_ts > 0 and (now - h.last_event_ts) > self._agent_stale_seconds:
                actions.append(HiveAction(
                    kind=HiveActionKind.RESTART_AGENT,
                    target_agents=[aid],
                    parameters={"reason": "stale_agent",
                                "last_event_age": now - h.last_event_ts},
                ))

        # 5. Custom rules
        for rule in self._custom_rules:
            try:
                custom_actions = rule(state)
                if custom_actions:
                    actions.extend(custom_actions)
            except Exception:
                logger.exception("Custom planner rule failed")

        self.action_log.extend(actions)
        return actions
