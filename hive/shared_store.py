"""
SharedStoreAdapter — cross-agent event store aggregation.

M5 component: provides a unified view across all per-agent event stores,
enabling hive-level queries and incident correlation.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

from hive.types import HiveEvent
from schemas.types import Event, EventKind, Severity

logger = logging.getLogger(__name__)

MAX_HIVE_EVENTS = 10_000


class SharedStoreAdapter:
    """Unified event store across all agents.

    Provides:
    - Ingestion of HiveEvents from the event bus
    - Cross-agent queries with filtering
    - Per-agent event access
    """

    def __init__(self, max_events: int = MAX_HIVE_EVENTS) -> None:
        self._adapters: dict[str, Any] = {}
        self._hive_events: list[HiveEvent] = []
        self._max_events = max_events

    def register_adapter(self, agent_id: str | Any, adapter: Any = None) -> None:
        """Register an agent adapter for cross-agent queries."""
        if adapter is None:
            adapter = agent_id
            agent_id = adapter.identity.agent_id
        self._adapters[agent_id] = adapter
        logger.info("SharedStore registered adapter for %s", agent_id)

    def unregister_adapter(self, agent_id: str) -> None:
        """Unregister an agent adapter."""
        self._adapters.pop(agent_id, None)
        logger.info("SharedStore unregistered adapter for %s", agent_id)

    def ingest(self, hive_event: HiveEvent) -> None:
        """Ingest a hive event into the shared store."""
        self._hive_events.append(hive_event)
        # Cap event list to prevent unbounded growth
        if len(self._hive_events) > self._max_events:
            self._hive_events = self._hive_events[-self._max_events:]

    def query(
        self,
        limit: int = 100,
        agent_id: Optional[str] = None,
        since: Optional[float] = None,
        kind: Optional[EventKind] = None,
        severity: Optional[Severity] = None,
    ) -> list[HiveEvent]:
        """Query hive events with filtering.

        Filters are applied before the limit to ensure correct results.
        """
        results: list[HiveEvent] = []

        for hevt in reversed(self._hive_events):
            # Apply filters first
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
            # Apply limit after filtering
            if len(results) >= limit:
                break

        results.reverse()  # chronological order
        return results

    def query_agent(self, agent_id: str, limit: int = 100) -> list[Event]:
        """Query events directly from a specific agent's store."""
        adapter = self._adapters.get(agent_id)
        if adapter is None:
            logger.warning("query_agent: no adapter for %s", agent_id)
            return []
        try:
            if hasattr(adapter, '_appliance') and hasattr(adapter._appliance, 'store'):
                return adapter._appliance.store.query(limit=limit)
            # Fall back to events_since
            events, _ = adapter.events_since(None)
            return events[-limit:]
        except Exception:
            logger.exception("Error querying agent %s store", agent_id)
            return []

    def event_count(self, agent_id: str | None = None) -> int:
        if agent_id is None:
            return len(self._hive_events)
        return sum(event.source_agent == agent_id for event in self._hive_events)

    @property
    def total_events(self) -> int:
        return len(self._hive_events)

    @property
    def agents(self) -> list[str]:
        """Return agents."""
        return list(self._adapters.keys())

    def recent_events(self, n: int = 50) -> list[HiveEvent]:
        """Return the N most recent hive events."""
        return self._hive_events[-n:]

    def agents_with_events(self) -> list[str]:
        return sorted({event.source_agent for event in self._hive_events})

    def cross_agent_incidents(self, symptom: str, window_seconds: float = 300.0) -> dict[str, list[HiveEvent]]:
        if not self._hive_events:
            return {}
        newest = max(event.hive_received_at for event in self._hive_events)
        cutoff = newest - window_seconds
        matches: dict[str, list[HiveEvent]] = {}
        for event in self._hive_events:
            original = event.original_event
            if (event.hive_received_at >= cutoff and original
                    and original.kind == EventKind.INCIDENT
                    and original.payload.get("symptom") == symptom):
                matches.setdefault(event.source_agent, []).append(event)
        return matches

    def summary(self) -> dict[str, Any]:
        return {"total_events": len(self._hive_events), "agents": self.agents_with_events()}

    def clear(self) -> None:
        self._hive_events.clear()
