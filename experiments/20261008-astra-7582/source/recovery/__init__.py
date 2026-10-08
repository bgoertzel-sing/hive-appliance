"""
Recovery module: state checkpointing and controlled upgrades.

C09 — State Recovery: checkpoint/restore appliance state
C10 — Controlled Upgrades: pre-flight, checkpoint, execute, verify, rollback
"""
from recovery.checkpoint import CheckpointManager
from recovery.upgrade import UpgradeController

__all__ = ["CheckpointManager", "UpgradeController"]
