"""
Exit-code verifier - independently verifies repair results.

P0 fixes:
  F6: Independent verification, separate from executor.
  F6: Fixed substring check (inactive no longer matches active).
"""
from __future__ import annotations
import re
from typing import Any
from schemas.types import Receipt

class ExitCodeVerifier:
    name = "exit_code_verifier"
    def verify(self, receipt, expected):
        expected_exit = expected.get("exit_code", 0)
        if receipt.exit_code != expected_exit:
            receipt.verified = False
            return False
        if "stdout_contains" in expected:
            needle = expected["stdout_contains"]
            haystack = receipt.stdout.strip()
            pattern = r'\b' + re.escape(needle) + r'\b'
            if not re.search(pattern, haystack):
                receipt.verified = False
                return False
        if "stderr_not_contains" in expected:
            if expected["stderr_not_contains"] in receipt.stderr:
                receipt.verified = False
                return False
        receipt.verified = True
        return True
