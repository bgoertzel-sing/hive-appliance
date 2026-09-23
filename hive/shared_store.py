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
    - Per-agent event access via registered adapters
    - Bookkeeping: agents_with_events, event_count, summary
    """

    def __init__(self, max_events: int = MAX_HIVE_EVENTS) -> None:
        self._adapters: dict[str, Any] = {}
        self._hive_events: list[HiveEvent] = []
        self._max_events = max_events

    def register_adapter(self, adapter_or_id: Any, adapter: Any = None) -> None:
        """Register an agent adapter for cross-agent queries.

        Accepts either:
          register_adapter(adapter)  — adapter.identity.agent_id used as key
          register_adapter(agent_id, adapter) — explicit key
        """
        if adapter is None:
            # Single-arg form: adapter has .identity.agent_id
            actual_adapter = adapter_or_id
            agent_id = actual_adapter.identity.agent_id
        else:
            agent_id = adapter_or_id
            actual_adapter = adapter
        self._adapters[agent_id] = actual_adapter
        logger.info("SharedStore registered adapter for %s", agent_id)

    def unregister_adapter(self, agent_id: str) -> None:
        """Unregister an agent adapter."""
        self._adapters.pop(agent_id, None)
        logger.info("SharedStore unregistered adapter for %s", agent_id)

    def ingest(self, hive_event: HiveEvent) -> None:
        """Ingest a hive event into the shared store."""
        self._hive_events.append(hive_event)
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
            if len(results) >= limit:
                break
        results.reverse()
        return results

    def query_agent(self, agent_id: str, limit: int = 100) -> list[Event]:
        """Query events directly from a specific agent's adapter."""
        adapter = self._adapters.get(agent_id)
        if adapter is None:
            logger.warning("query_agent: no adapter for %s", agent_id)
            return []
        try:
            events, _ = adapter.events_since(None)
            return events[-limit:]
        except Exception:
            logger.exception("Error querying agent %s store", agent_id)
            return []

    def cross_agent_incidents(
        self,
        symptom: str,
        window_seconds: float = 300.0,
    ) -> dict[str, list[HiveEvent]]:
        """Find incidents with a given symptom across agents within a time window."""
        cutoff = time.time() - window_seconds
        result: dict[str, list[HiveEvent]] = {}
        for hevt in self._hive_events:
            if hevt.hive_received_at < cutoff:
                continue
            if hevt.original_event and hevt.original_event.kind == EventKind.INCIDENT:
                if hevt.original_event.payload.get("symptom") == symptom:
                    result.setdefault(hevt.source_agent, []).append(hevt)
        return result

    @property
    def total_events(self) -> int:
        """Total number of ingested hive events."""
        return len(self._hive_events)

    def event_count(self, agent_id: Optional[str] = None) -> int:
        """Count events, optionally filtered by agent."""
        if agent_id is None:
            return len(self._hive_events)
        return sum(1 for e in self._hive_events if e.source_agent == agent_id)

    def agents_with_events(self) -> list[str]:
        """Return list of agent IDs that have ingested events."""
        seen: dict[str, None] = {}
        for e in self._hive_events:
            seen[e.source_agent] = None
        return list(seen.keys())

    @property
    def agents(self) -> list[str]:
        """Return registered agent IDs."""
        return list(self._adapters.keys())

    def recent_events(self, n: int = 50) -> list[HiveEvent]:
        """Return the N most recent hive events."""
        return self._hive_events[-n:]

    def summary(self) -> dict[str, Any]:
        """Return a summary of the shared store state."""
        agents_set = set()
        for e in self._hive_events:
            agents_set.add(e.source_agent)
        return {
            "total_events": len(self._hive_events),
            "agents": {a: self.event_count(a) for a in agents_set},
            "registered_adapters": list(self._adapters.keys()),
        }

    def clear(self) -> None:
        """Clear all ingested events."""
        self._hive_events.clear()
