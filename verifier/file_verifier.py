"""
File verifier - checks file existence as independent observation.
P0 fixes:
  F6: Independent verification - checks actual file state.
"""
from __future__ import annotations
import os
from typing import Any
from schemas.types import Receipt

class FileVerifier:
    name = "file_verifier"
    def verify(self, receipt, expected):
        if "file_exists" in expected:
            path = expected["file_exists"]
            result = os.path.exists(path)
            receipt.verified = result
            return result
        expected_code = expected.get("exit_code", 0)
        result = receipt.exit_code == expected_code
        if result and "stdout_contains" in expected:
            result = expected["stdout_contains"] in receipt.stdout
        receipt.verified = result
        return result
