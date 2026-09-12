"""
Base collector interface for the Omega Hive Appliance.

Collectors are responsible for observing the hive and emitting events.
"""
from __future__ import annotations

import abc
from typing import Any

from schemas.types import Event, EventKind, Severity


class BaseCollector(abc.ABC):
    """Abstract base for all collectors."""

    name: str = "base"

    @abc.abstractmethod
    def collect(self) -> list[Event]:
        """Observe the hive and return a list of Events."""
        ...

    def emit(self, subject: str, payload: dict[str, Any],
             severity: Severity = Severity.INFO,
             kind: EventKind = EventKind.OBSERVATION) -> Event:
        """Helper to build an observation event."""
        return Event(
            kind=kind,
            source=self.name,
            subject=subject,
            payload=payload,
            severity=severity,
        )
