"""
File verifier: checks file existence after repair.

C05 work package — file-based verification.
"""
from __future__ import annotations

import os
from typing import Any

from schemas.types import Receipt
from verifier.base import BaseVerifier


class FileVerifier(BaseVerifier):
    """Verifies that files exist after a repair step."""

    name = "file_verifier"

    def verify(self, receipt: Receipt, expected: dict[str, Any]) -> bool:
        # If expected specifies a file_path, check its existence
        """Execute verify operation."""
        file_path = expected.get("file_exists")
        if file_path:
            exists = os.path.exists(file_path)
            receipt.verified = exists
            return exists

        # Fall back to exit-code verification
        expected_code = expected.get("exit_code", 0)
        verified = receipt.exit_code == expected_code

        if verified and "stdout_contains" in expected:
            verified = expected["stdout_contains"] in receipt.stdout

        receipt.verified = verified
        return verified
