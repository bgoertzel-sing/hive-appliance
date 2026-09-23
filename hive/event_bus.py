"""
HiveEventBus — merges event streams from all registered agent adapters.

M5 component: polls each AgentApplianceAdapter for new events,
tags them with source agent, and provides a unified ordered stream
for the HiveReducer to consume.

Initially poll-based; can be extended to push/WebSocket later.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Optional

from hive.types import HiveEvent
from schemas.types import Event

logger = logging.getLogger(__name__)

# Type alias for subscribers
SubscriberFn = Callable[[HiveEvent], None]


class HiveEventBus:
    """Unified event stream from all registered agent adapters.

    Thread-safe: adapters and subscribers can be modified while polling.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, Any] = {}       # agent_id -> adapter
        self._cursors: dict[str, Optional[str]] = {}  # agent_id -> cursor
        self._subscribers: list[SubscriberFn] = []
        self._lock = threading.Lock()
        self._event_log: list[HiveEvent] = []
        self._max_log_size: int = 10_000

    def register_adapter(self, agent_id: str | Any, adapter: Any = None) -> None:
        """Register an agent adapter for polling."""
        if adapter is None:
            adapter = agent_id
            agent_id = adapter.identity.agent_id
        with self._lock:
            self._adapters[agent_id] = adapter
            self._cursors[agent_id] = None
        logger.info("Registered adapter for agent %s", agent_id)

    def unregister_adapter(self, agent_id: str) -> None:
        """Unregister an agent adapter."""
        with self._lock:
            self._adapters.pop(agent_id, None)
            self._cursors.pop(agent_id, None)
        logger.info("Unregistered adapter for agent %s", agent_id)

    def subscribe(self, fn: SubscriberFn) -> None:
        """Add an event subscriber."""
        with self._lock:
            self._subscribers.append(fn)

    add_subscriber = subscribe

    def unsubscribe(self, fn: SubscriberFn) -> None:
        """Remove an event subscriber."""
        with self._lock:
            self._subscribers = [s for s in self._subscribers if s is not fn]

    remove_subscriber = unsubscribe

    def poll_agent(self, agent_id: str) -> list[HiveEvent]:
        """Poll one agent for new events."""
        with self._lock:
            adapter = self._adapters.get(agent_id)
            cursor = self._cursors.get(agent_id)
        if adapter is None:
            logger.warning("poll_agent called for unregistered agent %s", agent_id)
            return []

        try:
            raw_events, new_cursor = adapter.events_since(cursor)
        except Exception:
            logger.exception("Error polling events from agent %s", agent_id)
            return []

        hive_events: list[HiveEvent] = []
        for evt in raw_events:
            hevt = HiveEvent(source_agent=agent_id, original_event=evt)
            hive_events.append(hevt)

        with self._lock:
            self._cursors[agent_id] = new_cursor
        return hive_events

    def poll_all(self) -> list[HiveEvent]:
        """Poll all adapters and return merged events (sorted by time)."""
        with self._lock:
            agent_ids = list(self._adapters.keys())

        all_events: list[HiveEvent] = []
        for agent_id in agent_ids:
            events = self.poll_agent(agent_id)
            all_events.extend(events)

        # Sort by receive time
        all_events.sort(key=lambda e: e.hive_received_at)

        # Append to event log with cap
        self._event_log.extend(all_events)
        if len(self._event_log) > self._max_log_size:
            self._event_log = self._event_log[-self._max_log_size:]

        # Notify subscribers
        with self._lock:
            subscribers = list(self._subscribers)
        for hevt in all_events:
            for sub in subscribers:
                try:
                    sub(hevt)
                except Exception:
                    logger.exception(
                        "Subscriber %s failed on event %s", sub, hevt.id
                    )

        return all_events

    @property
    def event_count(self) -> int:
        """Return event count."""
        return len(self._event_log)

    def recent_events(self, seconds: float = 60.0) -> list[HiveEvent]:
        cutoff = __import__("time").time() - seconds
        return [event for event in self._event_log if event.hive_received_at > cutoff]

    def events_since(self, offset: int) -> list[HiveEvent]:
        return self._event_log[offset:]

    def clear(self) -> None:
        self._event_log.clear()

    @property
    def registered_agents(self) -> list[str]:
        return list(self._adapters)

    @property
    def adapters(self) -> dict[str, Any]:
        """Return adapters."""
        with self._lock:
            return dict(self._adapters)
