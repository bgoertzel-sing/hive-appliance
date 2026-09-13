"""
Shell executor - executes commands via subprocess.

P0 fixes:
  F6: Does not set verified; only returns raw results.
"""
from __future__ import annotations

from executor.base import ShellExecutor as BaseShellExecutor

# Re-export from base for backward compatibility
ShellExecutor = BaseShellExecutor
