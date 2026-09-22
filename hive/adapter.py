"""
AgentApplianceAdapter — uniform interface for per-agent Appliances.

M5 component: each per-agent Appliance is wrapped by an adapter that
the Hive Appliance can poll for events, query state, and delegate actions.

Two implementations:
  - LocalAgentAdapter: for agents on the same filesystem (direct import)
  - StubAgentAdapter: for testing
"""
from __future__ import annotations

import logging
import time
from typing import Any, Protocol, runtime_checkable

from hive.types import (
    AgentHealth,
    AgentHealthSummary,
    AgentIdentity,
    HiveAction,
    HiveActionResult,
)
from recovery.checkpoint import StateCheckpoint
from schemas.types import Event

logger = logging.getLogger(__name__)

# ── Protocol ─────────────────────────────────────────────

@runtime_checkable
class AgentApplianceAdapter(Protocol):
    """Uniform interface a per-agent Appliance exposes to the Hive Appliance."""

    @property
    def identity(self) -> AgentIdentity: ...

    def events_since(self, cursor: str | None) -> tuple[list[Event], str]:
        """Return new events since cursor + new cursor. None = from start."""
        ...

    def state_snapshot(self) -> dict[str, Any]:
        """Current health/state summary."""
        ...

    def health_summary(self) -> AgentHealthSummary:
        """Structured health summary."""
        ...

    def execute(self, action: HiveAction) -> HiveActionResult:
        """Delegate a hive action to this agent's executor."""
        ...

    def checkpoint(self, label: str) -> StateCheckpoint:
        """Trigger a checkpoint on this agent's Appliance."""
        ...

    def restore(self, checkpoint_id: str) -> bool:
        """Restore this agent to a prior checkpoint."""
        ...


# ── Local implementation ─────────────────────────────────

class LocalAgentAdapter:
    """Adapter for a per-agent Appliance on the same filesystem.

    Wraps a controller.appliance.Appliance instance directly.
    """

    def __init__(self, agent_id: str, appliance: Any,
                 display_name: str = "", appliance_path: str = ""):
        self._identity = AgentIdentity(
            agent_id=agent_id,
            display_name=display_name or agent_id,
            appliance_path=appliance_path,
        )
        self._appliance = appliance
        self._cursor_counter: int = 0

    @property
    def identity(self) -> AgentIdentity:
        """Return identity."""
        return self._identity

    def events_since(self, cursor: str | None) -> tuple[list[Event], str]:
        """Poll events from the appliance's event store since cursor.

        Cursor is an event count offset (stringified int).
        Uses cursor-based pagination to avoid re-reading all events.
        """
        offset = int(cursor) if cursor else 0
        store = self._appliance.store

        # Use paginated query if available, otherwise fall back to bounded fetch
        if hasattr(store, 'query_since_offset'):
            new_events = store.query_since_offset(offset, limit=500)
            new_cursor = str(offset + len(new_events))
        else:
            all_events = store.query(limit=10000)
            new_events = all_events[offset:]
            new_cursor = str(len(all_events))

        if new_events:
            logger.debug(
                "Agent %s: %d new events since cursor %s",
                self._identity.agent_id, len(new_events), cursor,
            )
        return new_events, new_cursor

    def state_snapshot(self) -> dict[str, Any]:
        """Execute state snapshot operation."""
        if hasattr(self._appliance, 'state_snapshot'):
            return self._appliance.state_snapshot()
        return {"state": {}, "incidents": [], "event_count": 0}

    def health_summary(self) -> AgentHealthSummary:
        """Execute health summary operation."""
        snap = self.state_snapshot()
        incidents = snap.get("incidents", [])
        open_count = len([i for i in incidents if not i.get("resolved", False)])

        # Determine health from incidents
        if any(i.get("severity") in ("critical", "error") for i in incidents
               if not i.get("resolved", False)):
            health = AgentHealth.FAILED
        elif open_count > 0:
            health = AgentHealth.DEGRADED
        else:
            health = AgentHealth.HEALTHY

        return AgentHealthSummary(
            agent_id=self._identity.agent_id,
            health=health,
            open_incidents=open_count,
            last_event_ts=time.time(),
        )

    def execute(self, action: HiveAction) -> HiveActionResult:
        """Delegate action to per-agent appliance.

        For now, supports delegate_repair by forwarding to the agent's
        repair_incident method if available.
        """
        agent_id = self._identity.agent_id
        try:
            if hasattr(self._appliance, 'repair_incident'):
                result = self._appliance.repair_incident(action.params)
                logger.info(
                    "Agent %s executed action %s: success=%s",
                    agent_id, action.kind.value, result,
                )
                return HiveActionResult(
                    action_id=action.id,
                    success=bool(result),
                    output=str(result),
                )
            logger.warning(
                "Agent %s has no repair_incident method for action %s",
                agent_id, action.kind.value,
            )
            return HiveActionResult(
                action_id=action.id,
                success=False,
                output="Agent appliance does not support this action",
            )
        except Exception:
            logger.exception(
                "Agent %s action %s failed", agent_id, action.kind.value,
            )
            return HiveActionResult(
                action_id=action.id,
                success=False,
                output="Exception during action execution",
            )

    def checkpoint(self, label: str) -> StateCheckpoint:
        """Execute checkpoint operation."""
        if hasattr(self._appliance, 'checkpoint'):
            return self._appliance.checkpoint(label)
        return StateCheckpoint(label=label)

    def restore(self, checkpoint_id: str) -> bool:
        """Execute restore operation."""
        if hasattr(self._appliance, 'restore'):
            return self._appliance.restore(checkpoint_id)
        logger.warning("Agent %s does not support restore", self._identity.agent_id)
        return False


# ── Stub for testing ─────────────────────────────────────

class StubAgentAdapter:
    """Test adapter that serves canned events and health."""

    def __init__(self, agent_id: str, display_name: str = "",
                 events: list[Event] | None = None,
                 health: AgentHealth = AgentHealth.HEALTHY):
        self._identity = AgentIdentity(agent_id=agent_id, display_name=display_name or agent_id)
        self._events = list(events or [])
        self._health = health
        self._open_incidents = 0
        self._executed: list[HiveAction] = []
        self._checkpoints: dict[str, StateCheckpoint] = {}

    @property
    def identity(self) -> AgentIdentity:
        """Return identity."""
        return self._identity

    def events_since(self, cursor: str | None) -> tuple[list[Event], str]:
        """Execute events since operation."""
        offset = int(cursor) if cursor else 0
        new = self._events[offset:]
        return new, str(len(self._events))

    def state_snapshot(self) -> dict[str, Any]:
        """Execute state snapshot operation."""
        return {"state": {}, "incidents": [], "event_count": len(self._events)}

    def health_summary(self) -> AgentHealthSummary:
        """Execute health summary operation."""
        return AgentHealthSummary(
            agent_id=self._identity.agent_id,
            health=self._health,
            open_incidents=self._open_incidents,
            last_event_ts=time.time(),
        )

    def execute(self, action: HiveAction) -> HiveActionResult:
        """Execute execute operation."""
        self._executed.append(action)
        return HiveActionResult(
            action_id=action.id, success=True, output="stub",
            agent_results={self.identity.agent_id: {"success": True, "output": "stub"}},
        )

    def checkpoint(self, label: str) -> StateCheckpoint:
        """Execute checkpoint operation."""
        checkpoint = StateCheckpoint(id=f"stub-{len(self._checkpoints) + 1}", label=label)
        self._checkpoints[checkpoint.id] = checkpoint
        return checkpoint

    def restore(self, checkpoint_id: str) -> bool:
        """Execute restore operation."""
        return checkpoint_id in self._checkpoints

    def add_events(self, events: list[Event]) -> None:
        """Add events for testing."""
        self._events.extend(events)

    def inject_event(self, event: Event) -> None:
        self._events.append(event)

    def set_health(self, health: AgentHealth, open_incidents: int = 0) -> None:
        self._health = health
        self._open_incidents = open_incidents
