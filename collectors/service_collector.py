"""
Service-level collector: discovers systemd services and their status.

C00/C02 work package — service observation with health detection.
"""
from __future__ import annotations

import subprocess
from typing import Any

from collectors.base import BaseCollector
from schemas.types import Event, Severity


class ServiceCollector(BaseCollector):
    """Collects systemd service status information.

    Monitors a configurable list of services and emits WARN events
    for services that are inactive or failed.
    """

    name = "service_collector"

    def __init__(self, services: list[str] | None = None):
        self.services = services or [
            "ssh",
            "cron",
            "rsyslog",
            "systemd-journald",
        ]

    def collect(self) -> list[Event]:
        events: list[Event] = []
        for svc in self.services:
            status = self._query_service(svc)
            severity = Severity.INFO
            if status.get("active") == "inactive" or status.get("active") == "failed":
                severity = Severity.WARN
            events.append(self.emit(svc, status, severity=severity))
        return events

    def _query_service(self, svc: str) -> dict[str, Any]:
        """Query a single systemd service."""
        payload: dict[str, Any] = {"service": svc, "exists": False}

        # Check if systemd is available
        try:
            result = subprocess.run(
                ["systemctl", "is-active", svc],
                capture_output=True, text=True, timeout=5, check=False)
            active_state = result.stdout.strip()
            payload["active"] = active_state
            payload["exists"] = True

            if result.returncode != 0 and active_state not in ("active",):
                payload["down"] = True

            # Also get the full status for richer info
            result2 = subprocess.run(
                ["systemctl", "is-enabled", svc],
                capture_output=True, text=True, timeout=5, check=False)
            payload["enabled"] = result2.stdout.strip()

        except FileNotFoundError:
            # systemctl not available (non-systemd environment)
            payload["error"] = "systemctl not found"
            payload["exists"] = False
        except subprocess.TimeoutExpired:
            payload["error"] = f"timeout querying {svc}"
            payload["exists"] = True
        except Exception as e:
            payload["error"] = str(e)
            payload["exists"] = False

        return payload
