"""
Shell executor - executes commands via subprocess.

P0 fixes:
  F6: Does not set verified; only returns raw execution results.
"""
from __future__ import annotations

import subprocess
import time
from typing import Any

from schemas.types import Receipt, Plan
from executor.base import ShellExecutor as BaseShellExecutor

# Re-export from base for backward compatibility
ShellExecutor = BaseShellExecutor
