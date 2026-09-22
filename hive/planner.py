"""
HivePlanner — generates hive-level actions from HiveState.

M5 component: inspects the current HiveState, identifies actionable
situations (correlated incidents, resource alerts, drift), and produces
HiveActions that can be delegated to per-agent adapters.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional

from hive.types import (
    AgentHealth,
    HiveAction,
    HiveActionKind,
    HiveActionResult,
    HiveState,
)

logger = logging.getLogger(__name__)

# Type alias for custom rule functions
RuleFn = Callable[[HiveState], list[HiveAction]]

MAX_ACTION_LOG = 500


class HivePlanner:
    """Plans hive-level actions from HiveState.

    Built-in rules:
    - Restart failed agents
    - Delegate repair for correlated incidents
    - Resource rebalance when thresholds exceeded

    Custom rules can be registered via add_rule().
    """

    def __init__(self) -> None:
        self._rules: list[RuleFn] = []
        self._action_log: list[dict[str, Any]] = []
        self._cooldowns: dict[str, float] = {}  # action_key -> last_fired_ts
        self._cooldown_period: float = 60.0  # seconds between same action

    def add_rule(self, rule: RuleFn) -> None:
        """Register a custom planning rule."""
        self._rules.append(rule)

    def plan(self, state: HiveState) -> list[HiveAction]:
        """Generate actions from current state. Returns de-duped actions."""
        actions: list[HiveAction] = []

        # Built-in rules
        actions.extend(self._rule_restart_failed(state))
        actions.extend(self._rule_delegate_repair(state))
        actions.extend(self._rule_resource_rebalance(state))

        # Custom rules
        for rule in self._rules:
            try:
                actions.extend(rule(state))
            except Exception:
                logger.exception("Custom planning rule %s failed", rule)

        # Deduplicate and cooldown filter
        filtered: list[HiveAction] = []
        now = time.time()
        for action in actions:
            key = f"{action.kind.value}:{action.target_agent}"
            last = self._cooldowns.get(key, 0.0)
            if now - last >= self._cooldown_period:
                filtered.append(action)
                self._cooldowns[key] = now

        # Log planned actions
        for action in filtered:
            self._action_log.append({
                "id": action.id,
                "kind": action.kind.value,
                "target": action.target_agent,
                "ts": now,
            })

        # Cap action log
        if len(self._action_log) > MAX_ACTION_LOG:
            self._action_log = self._action_log[-MAX_ACTION_LOG:]

        if filtered:
            logger.info("Planned %d actions: %s", len(filtered),
                        [a.kind.value for a in filtered])
        return filtered

    def record_result(self, result: HiveActionResult) -> None:
        """Record the outcome of an executed action."""
        for entry in reversed(self._action_log):
            if entry["id"] == result.action_id:
                entry["success"] = result.success
                entry["output"] = result.output[:200]
                break

    # ── Built-in rules ───────────────────────────────────

    def _rule_restart_failed(self, state: HiveState) -> list[HiveAction]:
        """Generate restart actions for failed agents."""
        actions: list[HiveAction] = []
        for agent_id in state.failed_agents:
            actions.append(HiveAction(
                kind=HiveActionKind.RESTART_AGENT,
                target_agent=agent_id,
                reason=f"Agent {agent_id} health=FAILED",
                params={"agent_id": agent_id},
            ))
        return actions

    def _rule_delegate_repair(self, state: HiveState) -> list[HiveAction]:
        """Delegate repair for unresolved correlated incidents."""
        actions: list[HiveAction] = []
        for incident in state.open_incidents:
            if incident.affected_agents:
                primary = incident.affected_agents[0]
                actions.append(HiveAction(
                    kind=HiveActionKind.DELEGATE_REPAIR,
                    target_agent=primary,
                    reason=f"Correlated incident: {incident.symptom}",
                    params={
                        "incident_id": incident.id,
                        "symptom": incident.symptom,
                        "affected_agents": incident.affected_agents,
                    },
                ))
        return actions

    def _rule_resource_rebalance(self, state: HiveState) -> list[HiveAction]:
        """Generate rebalance actions when resource alerts fire."""
        alerts = state.resources.alerts()
        if not alerts:
            return []
        # Find agent with highest resource usage
        max_agent = ""
        max_usage = 0.0
        for agent_id, res in state.resources.agent_resources.items():
            usage = res.get("cpu_percent", 0.0) + res.get("disk_used", 0) / max(res.get("disk_total", 1), 1)
            if usage > max_usage:
                max_usage = usage
                max_agent = agent_id
        if max_agent:
            return [HiveAction(
                kind=HiveActionKind.REBALANCE,
                target_agent=max_agent,
                reason=f"Resource alerts: {', '.join(alerts)}",
                params={"alerts": alerts},
            )]
        return []

    @property
    def action_log(self) -> list[dict[str, Any]]:
        """Return action log."""
        return list(self._action_log)
