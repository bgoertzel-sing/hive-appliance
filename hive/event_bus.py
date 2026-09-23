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
import time
from typing import Any, Callable, Optional

from hive.types import HiveEvent
from schemas.types import Event

logger = logging.getLogger(__name__)

SubscriberFn = Callable[[HiveEvent], None]


class HiveEventBus:
    """Unified event stream from all registered agent adapters.

    Thread-safe: adapters and subscribers can be modified while polling.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, Any] = {}
        self._cursors: dict[str, Optional[str]] = {}
        self._subscribers: list[SubscriberFn] = []
        self._lock = threading.Lock()
        self._event_log: list[HiveEvent] = []
        self._max_log_size: int = 10_000

    def register_adapter(self, adapter: Any) -> None:
        """Register an agent adapter for polling (derives agent_id from adapter.identity)."""
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

    @property
    def registered_agents(self) -> set[str]:
        """Return set of registered agent IDs."""
        with self._lock:
            return set(self._adapters.keys())

    def add_subscriber(self, fn: SubscriberFn) -> None:
        """Add an event subscriber."""
        with self._lock:
            self._subscribers.append(fn)

    def remove_subscriber(self, fn: SubscriberFn) -> None:
        """Remove an event subscriber."""
        with self._lock:
            self._subscribers = [s for s in self._subscribers if s is not fn]

    def poll_all(self) -> list[HiveEvent]:
        """Poll all adapters and return merged events (sorted by time)."""
        with self._lock:
            agent_ids = list(self._adapters.keys())

        all_events: list[HiveEvent] = []
        for agent_id in agent_ids:
            with self._lock:
                adapter = self._adapters.get(agent_id)
                cursor = self._cursors.get(agent_id)
            if adapter is None:
                continue

            try:
                raw_events, new_cursor = adapter.events_since(cursor)
            except Exception:
                logger.exception("Error polling events from agent %s", agent_id)
                continue

            for evt in raw_events:
                hevt = HiveEvent(source_agent=agent_id, original_event=evt)
                all_events.append(hevt)

            with self._lock:
                self._cursors[agent_id] = new_cursor

        all_events.sort(key=lambda e: e.hive_received_at)

        # Append to log, trim if needed
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
                    logger.exception("Subscriber %s failed on event %s", sub, hevt.id)

        return all_events

    @property
    def event_count(self) -> int:
        """Total events in the log."""
        return len(self._event_log)

    def events_since(self, index: int) -> list[HiveEvent]:
        """Return events from the log starting at the given index."""
        return self._event_log[index:]

    def recent_events(self, seconds: float = 60.0) -> list[HiveEvent]:
        """Return events from the last N seconds."""
        cutoff = time.time() - seconds
        return [e for e in self._event_log if e.hive_received_at >= cutoff]

    def clear(self) -> None:
        """Clear all events from the log."""
        self._event_log.clear()

    @property
    def adapters(self) -> dict[str, Any]:
        """Return adapters dict."""
        with self._lock:
            return dict(self._adapters)
