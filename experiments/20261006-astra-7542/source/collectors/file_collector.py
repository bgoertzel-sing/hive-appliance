"""
File-level collector: tracks file existence and checksums for critical paths.

C00 work package — profile discovery.
"""
from __future__ import annotations

import hashlib
import os
from typing import Any

from collectors.base import BaseCollector
from schemas.types import Event, Severity


class FileCollector(BaseCollector):
    """Collects file existence and checksum information."""

    name = "file_collector"

    def __init__(self, paths: list[str] | None = None):
        self.paths = paths or [
            "/etc/hostname",
            "/etc/os-release",
            "/etc/fstab",
            "/etc/passwd",
        ]

    def collect(self) -> list[Event]:
        """Execute collect operation."""
        events: list[Event] = []
        for path in self.paths:
            exists = os.path.exists(path)
            payload: dict[str, Any] = {"path": path, "exists": exists}
            if exists and os.path.isfile(path):
                try:
                    payload["size"] = os.path.getsize(path)
                    payload["mtime"] = os.path.getmtime(path)
                    with open(path, "rb") as f:
                        payload["sha256"] = hashlib.sha256(f.read()).hexdigest()
                except Exception as e:
                    payload["error"] = str(e)
            events.append(self.emit(path, payload,
                severity=Severity.INFO if exists else Severity.WARN))
        return events
