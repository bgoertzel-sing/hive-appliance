"""
Base verifier interface.
"""
from __future__ import annotations

import abc
from typing import Any

from schemas.types import Receipt


class BaseVerifier(abc.ABC):
    """Abstract base for verifiers. F6: independent observation."""

    name: str = "base"

    @abc.abstractmethod
    def verify(self, receipt: Receipt, expected: dict) -> bool:
        ...
