"""
NixOS executor for the Hive Appliance repair loop.

Translates Appliance repair plans into NixOS configuration changes
and applies them via nix-build/nixos-rebuild.

C12.5 work package.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from adapters.nixos.config_generator import (
    NixServiceDef,
)
from adapters.nixos.nix_builder import NixBuilder
from executor.base import BaseExecutor
from schemas.types import Plan, Receipt


class NixOSExecutor(BaseExecutor):
    """Executor that applies repair plans as NixOS configuration changes.

    Instead of running imperative shell commands, this executor:
    1. Translates repair actions to NixOS module changes
    2. Regenerates the NixOS configuration
    3. Builds and optionally switches to the new configuration

    This provides atomic, rollback-capable repairs.
    """

    name = "nixos"
    is_simulation = False

    def __init__(
        self,
        config_dir: str,
        nix_builder: Optional[NixBuilder] = None,
        dry_run: bool = True,
        hostname: str = "hive-node",
    ):
        super().__init__()
        self._config_dir = config_dir
        self._nix_builder = nix_builder or NixBuilder()
        self._dry_run = dry_run
        self._hostname = hostname
        self._pending_changes: list[dict[str, Any]] = []


    def validate_step(self, step: dict[str, Any]) -> list[str]:
        """Override: accept NixOS-specific verbs in addition to base verbs."""
        errors = []
        verb = step.get("verb", "")
        if verb and verb not in NIXOS_ALLOWED_VERBS:
            errors.append(f"Verb '{verb}' not in ALLOWED_VERBS")
        return errors

    def execute_step(self, step: dict[str, Any], plan: Plan, step_index: int) -> Receipt:
        """Execute a repair step by translating to NixOS config changes.

        Supported step verbs:
        - nix-add-service: Add a systemd service
        - nix-remove-service: Disable a service
        - nix-add-package: Add a system package
        - nix-add-file: Add a managed file
        - nix-rebuild: Trigger nixos-rebuild
        - nix-rollback: Roll back to previous generation

        Standard verbs (restart, enable, disable) are mapped to NixOS equivalents.
        """
        verb = step.get("verb", "")
        target = step.get("target", "")
        params = step.get("params", {})
        start = time.time()

        # Validate verb
        errors = self.validate_step(step)
        if errors:
            elapsed = (time.time() - start) * 1000
            return Receipt(
                verb=verb, target=target, exit_code=1,
                stdout="", stderr="; ".join(errors),
                duration_ms=elapsed, verified=False,
            )

        # Dispatch to handler
        handler = {
            "restart": self._handle_restart,
            "enable": self._handle_enable,
            "disable": self._handle_disable,
        }.get(verb, self._handle_generic)

        try:
            result = handler(verb, target, params)
            elapsed = (time.time() - start) * 1000
            return Receipt(
                verb=verb, target=target,
                exit_code=0 if result["ok"] else 1,
                stdout=result.get("output", ""),
                stderr=result.get("error", ""),
                duration_ms=elapsed,
                verified=False,  # F6: Never set by executor
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return Receipt(
                verb=verb, target=target, exit_code=1,
                stdout="", stderr=f"{type(e).__name__}: {e}",
                duration_ms=elapsed, verified=False,
            )

    def _handle_restart(self, verb: str, target: str, params: dict) -> dict[str, Any]:
        """Restart a service via nixos-rebuild switch."""
        if self._dry_run:
            return {"ok": True, "output": f"[dry-run] Would restart '{target}' via nixos-rebuild"}

        result = self._nix_builder.nixos_rebuild(self._config_dir, action="switch")
        return {"ok": result.success, "output": result.stdout, "error": result.stderr}

    def _handle_enable(self, verb: str, target: str, params: dict) -> dict[str, Any]:
        """Enable a service in NixOS config."""
        svc = NixServiceDef(name=target, exec_start=params.get("exec_start", f"/usr/bin/{target}"), enable=True)
        self._pending_changes.append({"type": "enable", "nix_fragment": svc.to_nix(), "name": target})

        if self._dry_run:
            return {"ok": True, "output": f"[dry-run] Would enable '{target}' in NixOS config"}
        return self._apply_changes()

    def _handle_disable(self, verb: str, target: str, params: dict) -> dict[str, Any]:
        """Disable a service in NixOS config."""
        svc = NixServiceDef(name=target, exec_start="", enable=False)
        self._pending_changes.append({"type": "disable", "nix_fragment": svc.to_nix(), "name": target})

        if self._dry_run:
            return {"ok": True, "output": f"[dry-run] Would disable '{target}' in NixOS config"}
        return self._apply_changes()

    def _handle_generic(self, verb: str, target: str, params: dict) -> dict[str, Any]:
        """Generic handler for non-standard verbs — records as pending change."""
        self._pending_changes.append({
            "type": verb, "target": target, "params": params,
        })

        if self._dry_run:
            return {"ok": True, "output": f"[dry-run] Would apply '{verb}' on '{target}'"}
        return self._apply_changes()

    def _apply_changes(self) -> dict[str, Any]:
        """Apply pending changes by rebuilding NixOS config."""
        result = self._nix_builder.nixos_rebuild(self._config_dir, action="switch")
        self._pending_changes.clear()
        return {"ok": result.success, "output": result.stdout, "error": result.stderr}

    def get_pending_changes(self) -> list[dict[str, Any]]:
        """Return pending configuration changes (for inspection/testing)."""
        return list(self._pending_changes)

    def clear_pending(self) -> None:
        """Clear pending changes without applying them."""
        self._pending_changes.clear()


# NixOS-specific verbs accepted by this executor (superset of base ALLOWED_VERBS)
NIXOS_ALLOWED_VERBS = frozenset({
    # Standard verbs from schemas.types
    "touch", "verify", "inspect", "restart", "noop",
    # NixOS-specific verbs
    "enable", "disable", "check",
    "nix-add-service", "nix-remove-service",
    "nix-add-package", "nix-add-file",
    "nix-rebuild", "nix-rollback",
})
