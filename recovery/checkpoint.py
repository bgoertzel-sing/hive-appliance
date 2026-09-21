"""
C09 — State Recovery: checkpoint and restore appliance state.

A checkpoint is a timestamped snapshot of the appliance's event store,
profile, and incidents that can be restored later.
"""
from __future__ import annotations

import glob
import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class StateCheckpoint:
    """Immutable snapshot of appliance state at a point in time."""
    id: str = ""
    ts: float = field(default_factory=time.time)
    label: str = ""
    appliance_state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> StateCheckpoint:
        return cls(
            id=d.get("id", ""),
            ts=d.get("ts", 0.0),
            label=d.get("label", ""),
            appliance_state=d.get("appliance_state", {}),
            metadata=d.get("metadata", {}),
            schema_version=d.get("schema_version", "1"),
        )


class CheckpointManager:
    """Manages creation, persistence, listing, and restoration of state checkpoints.

    Checkpoints are stored as JSON files in a dedicated directory alongside
    the event store.  The naming convention is ``ckpt_<timestamp>_<label>.json``.
    """

    def __init__(self, base_dir: str):
        self._dir = os.path.join(base_dir, "checkpoints")
        os.makedirs(self._dir, exist_ok=True)
        self._counter = 0  # monotonic suffix for uniqueness within same second

    # ── public API ───────────────────────────────────────

    def create(self, appliance_state: dict[str, Any],
               label: str = "", metadata: dict[str, Any] | None = None) -> StateCheckpoint:
        """Create and persist a new checkpoint from the given state dict."""
        ts = time.time()
        self._counter += 1
        ckpt_id = f"ckpt_{int(ts)}_{self._counter}"
        ckpt = StateCheckpoint(
            id=ckpt_id,
            ts=ts,
            label=label or ckpt_id,
            appliance_state=appliance_state,
            metadata=metadata or {},
        )
        self._save(ckpt)
        return ckpt

    def list(self) -> list[StateCheckpoint]:
        """Return all persisted checkpoints, oldest first."""
        ckpts: list[StateCheckpoint] = []
        for path in sorted(glob.glob(os.path.join(self._dir, "ckpt_*.json"))):
            try:
                with open(path) as f:
                    ckpts.append(StateCheckpoint.from_dict(json.load(f)))
            except (json.JSONDecodeError, KeyError):
                continue
        return ckpts

    def load(self, ckpt_id: str) -> Optional[StateCheckpoint]:
        """Load a specific checkpoint by id."""
        for path in glob.glob(os.path.join(self._dir, "ckpt_*.json")):
            try:
                with open(path) as f:
                    data = json.load(f)
                if data.get("id") == ckpt_id:
                    return StateCheckpoint.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                continue
        return None

    def load_latest(self) -> Optional[StateCheckpoint]:
        """Load the most recent checkpoint, or None."""
        ckpts = self.list()
        return ckpts[-1] if ckpts else None

    def delete(self, ckpt_id: str) -> bool:
        """Delete a checkpoint by id.  Returns True if found and removed."""
        for path in glob.glob(os.path.join(self._dir, "ckpt_*.json")):
            try:
                with open(path) as f:
                    data = json.load(f)
                if data.get("id") == ckpt_id:
                    os.remove(path)
                    return True
            except (json.JSONDecodeError, KeyError):
                continue
        return False

    def prune(self, keep: int = 5) -> int:
        """Keep only the *keep* newest checkpoints.  Returns count removed."""
        ckpts = self.list()
        removed = 0
        for ckpt in ckpts[:-keep] if len(ckpts) > keep else []:
            if self.delete(ckpt.id):
                removed += 1
        return removed

    # ── internal ─────────────────────────────────────────

    def _save(self, ckpt: StateCheckpoint) -> str:
        safe_label = "".join(c if c.isalnum() or c in "-_" else "_" for c in ckpt.label)
        filename = f"{ckpt.id}_{safe_label}.json"
        path = os.path.join(self._dir, filename)
        with open(path, "w") as f:
            json.dump(ckpt.to_dict(), f, indent=2, default=str)
        return path
