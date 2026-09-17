"""
Exit-code verifier: checks that command exit codes match expectations.

C04 work package — verifier.

P0 fixes:
  F6: Simulated receipts never pass verification.
"""
from __future__ import annotations

import re

from typing import Any

from schemas.types import Receipt
from verifier.base import BaseVerifier


class ExitCodeVerifier(BaseVerifier):
    """Verifies receipts by checking exit codes."""

    name = "exit_code_verifier"

    def verify(self, receipt: Receipt, expected: dict[str, Any]) -> bool:
        """Verify receipt against expected outcomes.

        F6: Simulated receipts are never verified as true.
        """
        # F6: Simulated (dry-run) receipts cannot be verified
        if receipt.simulated:
            receipt.verified = False
            return False

        expected_code = expected.get("exit_code", 0)
        actual_code = receipt.exit_code
        verified = (actual_code == expected_code)

        # Also check stdout/stderr patterns if specified
        if verified and "stdout_contains" in expected:
            pattern = expected["stdout_contains"]
            verified = bool(re.search(r'\b' + re.escape(pattern) + r'\b', receipt.stdout))
        if verified and "stderr_not_contains" in expected:
            verified = expected["stderr_not_contains"] not in receipt.stderr

        receipt.verified = verified
        return verified
