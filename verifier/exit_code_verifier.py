"""
Exit-code verifier - independently verifies repair results.

P0 fixes:
  F6: Independent verification path, separate from executor.
  F6: Fixed substring check (inactive no longer matches active).
"""
from __future__ import annotations

from typing import Any

from schemas.types import Receipt


class ExitCodeVerifier:
    """Verifies receipts by checking exit codes and output expectations."""

    def verify(self, receipt: Receipt, expected: dict[str, Any]) -> bool:
        """Independently verify a receipt against expectations."""
        expected_exit = expected.get("exit_code", 0)
        if receipt.exit_code != expected_exit:
            return False

        if "stdout_contains" in expected:
            needle = expected["stdout_contains"]
            # F6: Use exact word match, not naive substring
            # "inactive" should NOT match "active"
            haystack = receipt.stdout.strip()
            # Check word boundaries
            import re
            pattern = r'\b' + re.escape(needle) + r'\b'
            if not re.search(pattern, haystack):
                return False

        if "stderr_contains" in expected:
            needle = expected["stderr_contains"]
            if needle not in receipt.stderr:
                return False

        return True
