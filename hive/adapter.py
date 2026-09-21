"""
AgentApplianceAdapter — uniform interface for per-agent Appliances.

M5 component: each per-agent Appliance is wrapped by an adapter that
the Hive Appliance can poll for events, query state, and delegate actions.

Two implementations:
  - LocalAgentAdapter: for agents on the same filesystem (direct import)
  - StubAgentAdapter: for testing
"""
from __future__ import annotations

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
        return self._identity

    def events_since(self, cursor: str | None) -> tuple[list[Event], str]:
        """Poll events from the appliance's event store since cursor.

        Cursor is an event count offset (stringified int).
        """
        offset = int(cursor) if cursor else 0
        all_events = self._appliance.store.query(limit=10000)
        new_events = all_events[offset:]
        new_cursor = str(len(all_events))
        return new_events, new_cursor

    def state_snapshot(self) -> dict[str, Any]:
        if hasattr(self._appliance, 'state_snapshot'):
            return self._appliance.state_snapshot()
        return {"state": {}, "incidents": [], "event_count": 0}

    def health_summary(self) -> AgentHealthSummary:
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
        try:
            if hasattr(self._appliance, 'repair_incident'):
                # Try to repair via the agent's own appliance
                result = self._appliance.repair_incident(
                    action.parameters.get("incident_id", "")
                )
                return HiveActionResult(
                    action_id=action.id,
                    success=bool(result),
                    agent_results={self._identity.agent_id: {"result": str(result)}},
                )
            return HiveActionResult(
                action_id=action.id,
                success=False,
                error="Agent appliance has no repair_incident method",
            )
        except Exception as e:
            return HiveActionResult(
                action_id=action.id,
                success=False,
                error=str(e),
            )

    def checkpoint(self, label: str) -> StateCheckpoint:
        if hasattr(self._appliance, 'create_checkpoint'):
            return self._appliance.create_checkpoint(label)
        # Fallback: create a basic checkpoint from state snapshot
        return StateCheckpoint(
            id=f"ckpt_{self._identity.agent_id}_{int(time.time())}",
            label=label,
            appliance_state=self.state_snapshot(),
        )

    def restore(self, checkpoint_id: str) -> bool:
        if hasattr(self._appliance, 'restore_checkpoint'):
            return self._appliance.restore_checkpoint(checkpoint_id)
        return False


# ── Stub for testing ─────────────────────────────────────

class StubAgentAdapter:
    """In-memory stub adapter for testing the hive layer."""

    def __init__(self, agent_id: str, display_name: str = ""):
        self._identity = AgentIdentity(
            agent_id=agent_id,
            display_name=display_name or agent_id,
        )
        self._events: list[Event] = []
        self._state: dict[str, Any] = {}
        self._health = AgentHealth.HEALTHY
        self._open_incidents: int = 0
        self._checkpoints: dict[str, StateCheckpoint] = {}

    @property
    def identity(self) -> AgentIdentity:
        return self._identity

    def inject_event(self, event: Event) -> None:
        """Test helper: inject an event."""
        self._events.append(event)

    def set_health(self, health: AgentHealth, open_incidents: int = 0) -> None:
        """Test helper: set health status."""
        self._health = health
        self._open_incidents = open_incidents

    def events_since(self, cursor: str | None) -> tuple[list[Event], str]:
        offset = int(cursor) if cursor else 0
        new_events = self._events[offset:]
        return new_events, str(len(self._events))

    def state_snapshot(self) -> dict[str, Any]:
        return dict(self._state)

    def health_summary(self) -> AgentHealthSummary:
        return AgentHealthSummary(
            agent_id=self._identity.agent_id,
            health=self._health,
            open_incidents=self._open_incidents,
            last_event_ts=time.time(),
        )

    def execute(self, action: HiveAction) -> HiveActionResult:
        return HiveActionResult(
            action_id=action.id,
            success=True,
            agent_results={self._identity.agent_id: {"stub": True}},
        )

    def checkpoint(self, label: str) -> StateCheckpoint:
        ckpt = StateCheckpoint(
            id=f"ckpt_{self._identity.agent_id}_{int(time.time())}",
            label=label,
            appliance_state=self.state_snapshot(),
        )
        self._checkpoints[ckpt.id] = ckpt
        return ckpt

    def restore(self, checkpoint_id: str) -> bool:
        return checkpoint_id in self._checkpoints
