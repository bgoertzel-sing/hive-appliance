"""
File verifier - checks file existence as independent observation.

P0 fixes:
  F6: Independent verification - checks actual file state, not executor output.
"""
from __future__ import annotations

import os
from typing import Any

from schemas.types import Receipt


class FileVerifier:
    """Verifies receipts by checking actual file existence."""

    def verify(self, receipt: Receipt, expected: dict[str, Any]) -> bool:
        """F6: Independently verify file existence on disk."""
        if "file_exists" in expected:
            path = expected["file_exists"]
            # F6: Check the actual filesystem, not executor-reported status
            return os.path.exists(path)
        return True
