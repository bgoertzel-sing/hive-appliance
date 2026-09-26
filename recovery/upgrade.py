"""
C10 — Controlled Upgrades: pre-flight checks, checkpoint-before,
execute upgrade steps, verify, and rollback on failure.

An upgrade is a sequence of steps (shell commands or Python callables)
executed under a safety net: a checkpoint is taken before the upgrade
begins, and if any step fails verification the appliance state is
rolled back to that checkpoint.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Optional

from recovery.checkpoint import CheckpointManager, StateCheckpoint


@dataclass
class UpgradeStep:
    """One atomic step in an upgrade manifest."""
    verb: str = ""          # human-readable action name
    command: str = ""       # shell command (if shell-based)
    rollback_command: str = ""  # optional explicit rollback command
    timeout_s: float = 60.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Execute to dict operation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> UpgradeStep:
        """Execute from dict operation."""
        return cls(
            verb=d.get("verb", ""),
            command=d.get("command", ""),
            rollback_command=d.get("rollback_command", ""),
            timeout_s=d.get("timeout_s", 60.0),
            metadata=d.get("metadata", {}),
        )


@dataclass
class UpgradeManifest:
    """Describes a complete upgrade: pre-flight checks + ordered steps."""
    id: str = ""
    ts: float = field(default_factory=time.time)
    description: str = ""
    pre_flight: list[dict[str, Any]] = field(default_factory=list)
    steps: list[UpgradeStep] = field(default_factory=list)
    schema_version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        """Execute to dict operation."""
        d = asdict(self)
        d["steps"] = [s.to_dict() for s in self.steps]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> UpgradeManifest:
        """Execute from dict operation."""
        return cls(
            id=d.get("id", ""),
            ts=d.get("ts", 0.0),
            description=d.get("description", ""),
            pre_flight=d.get("pre_flight", []),
            steps=[UpgradeStep.from_dict(s) for s in d.get("steps", [])],
            schema_version=d.get("schema_version", "1"),
        )


@dataclass
class UpgradeResult:
    """Outcome of an upgrade attempt."""
    manifest_id: str = ""
    success: bool = False
    steps_completed: int = 0
    steps_total: int = 0
    rolled_back: bool = False      # U2: True ONLY if state was actually restored
    rollback_error: str = ""       # U2: why rollback did not happen / failed
    pre_checkpoint_id: str = ""
    error: str = ""
    step_results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Execute to dict operation."""
        return asdict(self)


class UpgradeController:
    """Orchestrates controlled upgrades with checkpoint safety net.

    Workflow:
      1. Run pre-flight checks (each is a callable returning (ok, msg))
      2. Take a state checkpoint
      3. Execute each UpgradeStep via the executor
      4. Verify each step via the verifier
      5. On failure: restore from pre-upgrade checkpoint
    """

    def __init__(self, checkpoint_mgr: CheckpointManager,
                 executor: Any = None, verifier: Any = None):
        self._ckpt = checkpoint_mgr
        self._executor = executor
        self._verifier = verifier
        self._pre_flight_checks: list[Callable[[], tuple[bool, str]]] = []

    def add_pre_flight(self, check: Callable[[], tuple[bool, str]]) -> None:
        """Register a pre-flight check (returns (ok, message))."""
        self._pre_flight_checks.append(check)

    def run_pre_flight(self, manifest: UpgradeManifest) -> list[tuple[bool, str]]:
        """Execute all registered pre-flight checks."""
        results = []
        for check in self._pre_flight_checks:
            try:
                ok, msg = check()
                results.append((ok, msg))
            except Exception as exc:
                results.append((False, f"Pre-flight exception: {exc}"))
        return results

    def execute(self, manifest: UpgradeManifest,
                appliance_state: dict[str, Any],
                dry_run: bool = False,
                restore_fn: Optional[Callable[[dict[str, Any]], None]] = None,
                ) -> UpgradeResult:
        """Execute an upgrade manifest with checkpoint safety net.

        Args:
            manifest: The upgrade to execute.
            appliance_state: Current appliance state dict (for checkpoint).
            dry_run: If True, skip actual execution, just validate and plan.
            restore_fn: U2 - callable that applies a checkpointed state.  On
                step failure the pre-upgrade checkpoint is re-loaded from disk
                and passed to it.  rolled_back is True only if that succeeds.

        Returns:
            UpgradeResult with outcome details.
        """
        result = UpgradeResult(
            manifest_id=manifest.id,
            steps_total=len(manifest.steps),
        )

        # 1. Pre-flight
        pf_results = self.run_pre_flight(manifest)
        if any(not ok for ok, _ in pf_results):
            failures = [msg for ok, msg in pf_results if not ok]
            result.error = f"Pre-flight failed: {'; '.join(failures)}"
            return result

        # 2. Checkpoint before upgrade
        ckpt = self._ckpt.create(
            appliance_state,
            label=f"pre_upgrade_{manifest.id}",
            metadata={"upgrade_manifest": manifest.id},
        )
        result.pre_checkpoint_id = ckpt.id

        if dry_run:
            result.success = True
            result.error = "dry-run: no steps executed"
            return result

        # 3. Execute steps
        for i, step in enumerate(manifest.steps):
            step_result = self._execute_step(step, i)
            result.step_results.append(step_result)

            if not step_result.get("success", False):
                result.error = (
                    f"Step {i} ({step.verb}) failed: "
                    f"{step_result.get('error', 'unknown')}"
                )
                failed = True
                break
            result.steps_completed += 1
        else:
            failed = False

        if not failed:
            result.success = True
            return result

        # 4. Rollback (U2): actually restore; never claim it otherwise.
        self._rollback(ckpt.id, restore_fn, result)
        return result

    def _rollback(self, ckpt_id: str,
                  restore_fn: Optional[Callable[[dict[str, Any]], None]],
                  result: UpgradeResult) -> None:
        """U2: Restore the pre-upgrade checkpoint; set rolled_back only on success."""
        result.rolled_back = False
        if restore_fn is None:
            result.rollback_error = "no restore function configured; state NOT restored"
            return
        try:
            restored = self._ckpt.load(ckpt_id)
        except Exception as exc:
            result.rollback_error = f"checkpoint load failed: {type(exc).__name__}: {exc}"
            return
        if restored is None:
            result.rollback_error = f"checkpoint {ckpt_id} missing; state NOT restored"
            return
        try:
            restore_fn(restored.appliance_state)
        except Exception as exc:
            result.rollback_error = f"restore failed: {type(exc).__name__}: {exc}"
            return
        result.rolled_back = True

    def _execute_step(self, step: UpgradeStep, index: int) -> dict[str, Any]:
        """Execute a single upgrade step and verify it."""
        if self._executor is None:
            return {"success": True, "index": index, "verb": step.verb,
                    "note": "no executor configured (noop)"}

        try:
            # Build a plan-like step dict for the executor
            step_dict = {
                "verb": step.verb,
                "command": step.command,
                "timeout_s": step.timeout_s,
            }
            # Use executor's execute_step if available
            if hasattr(self._executor, "execute_step"):
                receipt = self._executor.execute_step(step_dict, None, index)
                # Verify
                if self._verifier and hasattr(self._verifier, "verify"):
                    verified = self._verifier.verify(receipt, step_dict)
                    receipt_dict = receipt.to_dict() if hasattr(receipt, "to_dict") else {"exit_code": 0}
                    receipt_dict["verified"] = verified
                    return {"success": verified, "index": index,
                            "verb": step.verb, "receipt": receipt_dict}
                else:
                    receipt_dict = receipt.to_dict() if hasattr(receipt, "to_dict") else {}
                    return {"success": receipt_dict.get("exit_code", 0) == 0,
                            "index": index, "verb": step.verb, "receipt": receipt_dict}
            else:
                return {"success": False, "index": index, "verb": step.verb,
                        "error": "executor has no execute_step method"}
        except Exception as exc:
            return {"success": False, "index": index, "verb": step.verb,
                    "error": str(exc)}

    def restore_checkpoint(self, ckpt_id: str) -> Optional[StateCheckpoint]:
        """Load a checkpoint for restoration.  The caller (Appliance) is
        responsible for actually applying the state."""
        return self._ckpt.load(ckpt_id)
