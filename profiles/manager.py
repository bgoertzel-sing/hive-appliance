"""
Profile manager: discovers, stores, and retrieves hive profiles.

C00/C05 work package — profile discovery and persistence.
"""
from __future__ import annotations

import json
from pathlib import Path

from collectors.host_collector import HostCollector
from schemas.types import HiveProfile


class ProfileManager:
    """Manages hive profiles — discovery and persistence."""

    def __init__(self, store_dir: str | Path = "."):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def discover(self) -> HiveProfile:
        """Discover the current hive profile using collectors."""
        collector = HostCollector()
        return collector.discover_profile()

    def save(self, profile: HiveProfile) -> Path:
        """Save a profile to disk."""
        path = self.store_dir / f"profile_{profile.id}.json"
        with open(path, "w") as f:
            json.dump(profile.to_dict(), f, indent=2)
        return path

    def load(self, profile_id: str) -> HiveProfile | None:
        """Load a profile from disk."""
        path = self.store_dir / f"profile_{profile_id}.json"
        if not path.exists():
            return None
        with open(path) as f:
            return HiveProfile.from_dict(json.load(f))

    def list_profiles(self) -> list[str]:
        """List all saved profile IDs."""
        profiles = []
        for p in self.store_dir.glob("profile_*.json"):
            stem = p.stem.replace("profile_", "")
            profiles.append(stem)
        return profiles

    def latest(self) -> HiveProfile | None:
        """Get the most recent profile."""
        ids = self.list_profiles()
        if not ids:
            return None
        # Sort by modification time
        files = sorted(
            self.store_dir.glob("profile_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not files:
            return None
        with open(files[0]) as f:
            return HiveProfile.from_dict(json.load(f))
