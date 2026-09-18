"""
HiveEventBus — merges event streams from all registered agent adapters.

M5 component: polls each AgentApplianceAdapter for new events,
tags them with source agent, and provides a unified ordered stream
for the HiveReducer to consume.

Initially poll-based with configurable interval.
"""
from __future__ import annotations

import time
import threading
from typing import Any, Callable, Optional

from hive.types import HiveEvent
from schemas.types import Event


class HiveEventBus:
    """Merges per-agent event streams into a single hive-level stream.

    Usage:
        bus = HiveEventBus()
        bus.register_adapter(adapter)
        bus.add_subscriber(my_callback)
        bus.poll_all()  # pulls new events from all adapters
    """

    def __init__(self):
        self._adapters: dict[str, Any] = {}  # agent_id -> adapter
        self._cursors: dict[str, str | None] = {}  # agent_id -> cursor
        self._subscribers: list[Callable[[HiveEvent], None]] = []
        self._event_log: list[HiveEvent] = []
        self._max_log_size: int = 10000
        self._lock = threading.Lock()

    def register_adapter(self, adapter: Any) -> None:
        """Register an agent adapter for event polling."""
        agent_id = adapter.identity.agent_id
        with self._lock:
            self._adapters[agent_id] = adapter
            self._cursors[agent_id] = None

    def unregister_adapter(self, agent_id: str) -> None:
        """Remove an agent adapter."""
        with self._lock:
            self._adapters.pop(agent_id, None)
            self._cursors.pop(agent_id, None)

    def add_subscriber(self, callback: Callable[[HiveEvent], None]) -> None:
        """Add a subscriber that will be called for each new HiveEvent."""
        self._subscribers.append(callback)

    def remove_subscriber(self, callback: Callable[[HiveEvent], None]) -> None:
        """Remove a subscriber."""
        self._subscribers = [s for s in self._subscribers if s is not callback]

    @property
    def registered_agents(self) -> list[str]:
        return list(self._adapters.keys())

    @property
    def event_count(self) -> int:
        return len(self._event_log)

    def poll_agent(self, agent_id: str) -> list[HiveEvent]:
        """Poll a single agent for new events."""
        with self._lock:
            adapter = self._adapters.get(agent_id)
            if adapter is None:
                return []
            cursor = self._cursors.get(agent_id)

        try:
            events, new_cursor = adapter.events_since(cursor)
        except Exception:
            return []

        hive_events = []
        now = time.time()
        for event in events:
            hevt = HiveEvent(
                source_agent=agent_id,
                original_event=event,
                hive_received_at=now,
            )
            hive_events.append(hevt)

        with self._lock:
            self._cursors[agent_id] = new_cursor
            self._event_log.extend(hive_events)
            # Trim log if too large
            if len(self._event_log) > self._max_log_size:
                self._event_log = self._event_log[-self._max_log_size:]

        # Notify subscribers
        for hevt in hive_events:
            for sub in self._subscribers:
                try:
                    sub(hevt)
                except Exception:
                    pass  # Don't let one subscriber break others

        return hive_events

    def poll_all(self) -> list[HiveEvent]:
        """Poll all registered adapters for new events.

        Returns all new HiveEvents collected in this poll cycle,
        sorted by original event timestamp.
        """
        all_events: list[HiveEvent] = []
        agent_ids = list(self._adapters.keys())  # snapshot
        for agent_id in agent_ids:
            events = self.poll_agent(agent_id)
            all_events.extend(events)

        # Sort by original event timestamp for consistent ordering
        all_events.sort(
            key=lambda e: e.original_event.ts if e.original_event else e.hive_received_at
        )
        return all_events

    def events_since(self, offset: int = 0) -> list[HiveEvent]:
        """Return hive events from the log starting at offset."""
        with self._lock:
            return list(self._event_log[offset:])

    def recent_events(self, seconds: float = 300.0) -> list[HiveEvent]:
        """Return events from the last N seconds."""
        cutoff = time.time() - seconds
        with self._lock:
            return [e for e in self._event_log
                    if e.hive_received_at >= cutoff]

    def clear(self) -> None:
        """Clear event log (for testing)."""
        with self._lock:
            self._event_log.clear()
