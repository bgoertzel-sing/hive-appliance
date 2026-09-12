"""
Base verifier interface for verifying repair outcomes.

C04 work package — verifier.
"""
from __future__ import annotations

import abc
from typing import Any

from schemas.types import Receipt, Event, EventKind, Severity


class BaseVerifier(abc.ABC):
    """Abstract base for all verifiers."""

    name: str = "base"

    @abc.abstractmethod
    def verify(self, receipt: Receipt, expected: dict[str, Any]) -> bool:
        """Verify that a receipt matches expected outcomes."""
        ...

    def make_receipt_event(self, receipt: Receipt) -> Event:
        """Convert a receipt into a RECEIPT event."""
        return Event(
            kind=EventKind.RECEIPT,
            source=self.name,
            subject=receipt.target or "system",
            payload=receipt.to_dict(),
            severity=Severity.INFO if receipt.verified else Severity.ERROR,
        )
