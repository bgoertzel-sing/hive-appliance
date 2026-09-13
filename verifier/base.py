"""
Verifier interface.
"""
from __future__ import annotations

from typing import Any

from schemas.types import Receipt


class BaseVerifier:
    """Base class for verifiers."""

    def verify(self, receipt: Receipt, expected: dict[str, Any]) -> bool:
        """Verify a receipt against expected outcomes."""
        raise NotImplementedError
