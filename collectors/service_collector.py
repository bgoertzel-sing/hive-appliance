"""
Service-level collector: discovers running services and their health.

C00 work package — profile discovery.
"""
from __future__ import annotations

import subprocess
from typing import Any

from collectors.base import BaseCollector
from schemas.types import Event, Severity, Resource, ResourceKind


class ServiceCollector(BaseCollector):
    """Collects information about running services."""

    name = "service_collector"

    def collect(self) -> list[Event]:
        events: list[Event] = []
        services = self._list_services()
        for svc in services:
            events.append(self.emit(
                svc["name"],
                {"state": svc.get("state", "unknown"),
                 "type": svc.get("type", "unknown")},
                severity=Severity.INFO,
            ))
        return events

    def _list_services(self) -> list[dict[str, Any]]:
        services: list[dict[str, Any]] = []
        # Try systemctl
        try:
            result = subprocess.run(
                ["systemctl", "list-units", "--type=service",
                 "--no-legend", "--no-pager"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.strip().splitlines():
                    parts = line.split()
                    if len(parts) >= 4:
                        services.append({
                            "name": parts[0],
                            "load": parts[1],
                            "active": parts[2],
                            "sub": parts[3],
                            "state": parts[3],
                            "type": "systemd",
                        })
        except Exception:
            pass
        # Fallback: ps
        if not services:
            try:
                result = subprocess.run(
                    ["ps", "aux"], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    for line in result.stdout.strip().splitlines()[1:]:
                        parts = line.split(None, 10)
                        if len(parts) >= 11:
                            services.append({
                                "name": parts[10][:60],
                                "state": "running",
                                "type": "process",
                            })
            except Exception:
                pass
        return services
