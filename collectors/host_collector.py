"""
Host-level collector: discovers OS, kernel, CPU, memory, disk, and process info.

C00 work package — profile discovery.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
from typing import Any

from collectors.base import BaseCollector
from schemas.types import (
    Event,
    HiveProfile,
    ProfileTier,
    Resource,
    ResourceKind,
    Severity,
)


class HostCollector(BaseCollector):
    """Collects host-level system information."""

    name = "host_collector"

    def collect(self) -> list[Event]:
        """Execute collect operation."""
        events: list[Event] = []
        info = self._gather()
        events.append(self.emit("system", info, severity=Severity.INFO))
        for resource in info.get("resources", []):
            events.append(self.emit(
                resource["name"],
                {"kind": resource["kind"], **resource.get("attributes", {})},
                severity=Severity.INFO,
            ))
        return events

    def _gather(self) -> dict[str, Any]:
        info: dict[str, Any] = {
            "hostname": platform.node(),
            "os": f"{platform.system()} {platform.release()}",
            "kernel": platform.version(),
            "arch": platform.machine(),
            "python": platform.python_version(),
        }

        resources: list[dict[str, Any]] = []

        # CPU
        try:
            cpu_count = os.cpu_count() or 0
            resources.append({"kind": "service", "name": "cpu",
                              "attributes": {"cores": cpu_count}})
        except Exception:
            pass

        # Memory
        try:
            with open("/proc/meminfo") as f:
                memlines = f.readlines()
            mem = {}
            for line in memlines:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = int(parts[1].strip().split()[0])
                    mem[key] = val
            if mem:
                resources.append({"kind": "service", "name": "memory",
                                  "attributes": mem})
        except Exception:
            pass

        # Disk
        try:
            result = subprocess.run(["df", "-h", "/"],
                capture_output=True, text=True, timeout=5, check=False)
            if result.returncode == 0:
                resources.append({"kind": "volume", "name": "root",
                                  "attributes": {"df": result.stdout.strip()}})
        except Exception:
            pass

        # Network
        try:
            result = subprocess.run(["ip", "-j", "addr"],
                capture_output=True, text=True, timeout=5, check=False)
            if result.returncode == 0:
                interfaces = json.loads(result.stdout)
                for iface in interfaces:
                    resources.append({"kind": "network",
                        "name": iface.get("ifname", "unknown"),
                        "attributes": {"operstate": iface.get("operstate", ""),
                                       "addr_info": iface.get("addr_info", [])}})
        except Exception:
            pass

        info["resources"] = resources
        return info

    def discover_profile(self) -> HiveProfile:
        """Discover the hive profile from host info."""
        info = self._gather()
        resources = [
            Resource(kind=ResourceKind(r["kind"]), name=r["name"],
                     attributes=r.get("attributes", {}))
            for r in info.get("resources", [])
        ]
        return HiveProfile(
            hostname=info.get("hostname", ""),
            os=info.get("os", ""),
            kernel=info.get("kernel", ""),
            tier=ProfileTier.OBSERVED,
            resources=resources,
            tags=["m0", "observed"],
        )
