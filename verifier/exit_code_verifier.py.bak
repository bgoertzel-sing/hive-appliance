"""
Exit-code verifier: checks that command exit codes match expectations.

C04 work package — verifier.
"""
from __future__ import annotations

from typing import Any

from schemas.types import Receipt
from verifier.base import BaseVerifier


class ExitCodeVerifier(BaseVerifier):
    """Verifies receipts by checking exit codes."""

    name = "exit_code_verifier"

    def verify(self, receipt: Receipt, expected: dict[str, Any]) -> bool:
        expected_code = expected.get("exit_code", 0)
        actual_code = receipt.exit_code
        verified = (actual_code == expected_code)

        # Also check stdout/stderr patterns if specified
        if verified and "stdout_contains" in expected:
            verified = expected["stdout_contains"] in receipt.stdout
        if verified and "stderr_not_contains" in expected:
            verified = expected["stderr_not_contains"] not in receipt.stderr

        receipt.verified = verified
        return verified
