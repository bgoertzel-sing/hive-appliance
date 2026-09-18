"""
SharedStoreAdapter — cross-agent event store aggregation.

M5 component: provides a unified view across all per-agent event stores,
enabling hive-level queries and incident correlation.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from hive.types import HiveEvent
from schemas.types import Event, EventKind, Severity


class SharedStoreAdapter:
    """Aggregates event stores across multiple agent adapters.

    Provides:
    - Unified query interface across all agents
    - Cross-agent event correlation
    - Hive-level event history
    """

    def __init__(self, max_events: int = 50000):
        self._adapters: dict[str, Any] = {}  # agent_id -> adapter
        self._hive_events: list[HiveEvent] = []
        self._max_events = max_events

    def register_adapter(self, adapter: Any) -> None:
        """Register an agent adapter for store access."""
        self._adapters[adapter.identity.agent_id] = adapter

    def unregister_adapter(self, agent_id: str) -> None:
        """Remove an agent adapter."""
        self._adapters.pop(agent_id, None)

    def ingest(self, hive_event: HiveEvent) -> None:
        """Add a HiveEvent to the shared store."""
        self._hive_events.append(hive_event)
        if len(self._hive_events) > self._max_events:
            self._hive_events = self._hive_events[-self._max_events:]

    def query(
        self,
        kind: Optional[EventKind] = None,
        severity: Optional[Severity] = None,
        agent_id: Optional[str] = None,
        since: Optional[float] = None,
        limit: int = 100,
    ) -> list[HiveEvent]:
        """Query hive events with optional filters.

        Args:
            kind: Filter by original event kind
            severity: Filter by severity
            agent_id: Filter by source agent
            since: Only events received after this timestamp
            limit: Max results
        """
        results: list[HiveEvent] = []

        for hevt in reversed(self._hive_events):
            if len(results) >= limit:
                break
            if agent_id and hevt.source_agent != agent_id:
                continue
            if since and hevt.hive_received_at < since:
                continue
            if hevt.original_event:
                if kind and hevt.original_event.kind != kind:
                    continue
                if severity and hevt.original_event.payload.get("severity") != severity.value:
                    continue
            results.append(hevt)

        results.reverse()  # chronological order
        return results

    def query_agent(self, agent_id: str, limit: int = 100) -> list[Event]:
        """Query events from a specific agent's store directly."""
        adapter = self._adapters.get(agent_id)
        if adapter is None:
            return []
        try:
            events, _ = adapter.events_since(None)
            return events[-limit:]
        except Exception:
            return []

    def cross_agent_incidents(
        self,
        symptom: str,
        window_seconds: float = 300.0,
    ) -> dict[str, list[HiveEvent]]:
        """Find incidents with a given symptom across agents within a time window.

        Returns: {agent_id: [matching events]}
        """
        cutoff = time.time() - window_seconds
        result: dict[str, list[HiveEvent]] = {}

        for hevt in self._hive_events:
            if hevt.hive_received_at < cutoff:
                continue
            if hevt.original_event is None:
                continue
            if hevt.original_event.kind != EventKind.INCIDENT:
                continue
            if symptom in hevt.original_event.payload.get("symptom", ""):
                result.setdefault(hevt.source_agent, []).append(hevt)

        return result

    def event_count(self, agent_id: Optional[str] = None) -> int:
        """Count events, optionally filtered by agent."""
        if agent_id is None:
            return len(self._hive_events)
        return sum(1 for e in self._hive_events if e.source_agent == agent_id)

    def agents_with_events(self) -> list[str]:
        """Return list of agent IDs that have events in the store."""
        return list(set(e.source_agent for e in self._hive_events))

    @property
    def total_events(self) -> int:
        return len(self._hive_events)

    def clear(self) -> None:
        """Clear all events (for testing)."""
        self._hive_events.clear()

    def summary(self) -> dict[str, Any]:
        """Return a summary of the shared store state."""
        agent_counts: dict[str, int] = {}
        for hevt in self._hive_events:
            agent_counts[hevt.source_agent] = agent_counts.get(hevt.source_agent, 0) + 1

        return {
            "total_events": len(self._hive_events),
            "agents": list(agent_counts.keys()),
            "events_per_agent": agent_counts,
            "max_events": self._max_events,
        }
