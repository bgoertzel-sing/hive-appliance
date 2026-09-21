"""
NixOS adapter for the Omega Hive Appliance.

Verb-based dispatch adapter (same pattern as LocalAdapter) that manages
NixOS configurations and QEMU VMs.

C12.4 work package.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from adapters.nixos.config_generator import ConfigGenerator
from adapters.nixos.nix_builder import NixBuilder
from adapters.nixos.service_module import ServiceMapper
from adapters.nixos.vm_manager import VMConfig, VMManager, VMState
from schemas.types import ProfileTier, Resource

# Verbs supported by NixOSAdapter
ALLOWED_VERBS = frozenset({
    # Nix configuration
    "nix-generate",     # Generate NixOS configuration from current resources
    "nix-build",        # Build a NixOS configuration
    "nix-switch",       # Switch running system to new configuration
    "nix-rollback",     # Roll back to previous generation
    "nix-eval",         # Evaluate a Nix expression
    "nix-gc",           # Garbage collect old Nix generations
    "nix-status",       # Check Nix availability and version
    # VM lifecycle
    "vm-create",        # Create a new VM
    "vm-start",         # Start a stopped VM
    "vm-stop",          # Stop a running VM
    "vm-destroy",       # Destroy a VM
    "vm-snapshot",      # Snapshot a VM
    "vm-restore",       # Restore a VM from snapshot
    "vm-status",        # Get VM status
    "vm-list",          # List all VMs
    # Resource mapping
    "map-resources",    # Map Appliance resources to NixOS definitions
    # Status
    "status",           # Overall adapter status
})


class NixOSAdapter:
    """NixOS backend adapter for the Hive Appliance.

    Manages NixOS configurations and VM lifecycle. Integrates with the
    existing Appliance framework through the verb-dispatch pattern.

    Configuration is generated from Appliance resources via ConfigGenerator
    and ServiceMapper. VMs are managed via VMManager (QEMU).
    Nix build/eval operations go through NixBuilder.

    All subprocess operations are mockable for testing.
    """

    def __init__(
        self,
        state_dir: str,
        hostname: str = "hive-node",
        qemu_binary: str = "qemu-system-x86_64",
        nix_binary: str = "nix",
        nix_timeout: int = 300,
    ):
        self._state_dir = Path(state_dir)
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._hostname = hostname

        # Sub-components
        self._config_gen = ConfigGenerator(hostname=hostname)
        self._vm_manager = VMManager(
            state_dir=str(self._state_dir / "vms"),
            qemu_binary=qemu_binary,
        )
        self._nix_builder = NixBuilder(
            nix_binary=nix_binary,
            timeout=nix_timeout,
        )
        self._service_mapper = ServiceMapper()

        # Config output directory
        self._config_dir = self._state_dir / "nixos-config"
        self._config_dir.mkdir(parents=True, exist_ok=True)

    @property
    def allowed_verbs(self) -> frozenset[str]:
        return ALLOWED_VERBS

    @property
    def config_generator(self) -> ConfigGenerator:
        return self._config_gen

    @property
    def vm_manager(self) -> VMManager:
        return self._vm_manager

    @property
    def nix_builder(self) -> NixBuilder:
        return self._nix_builder

    @property
    def service_mapper(self) -> ServiceMapper:
        return self._service_mapper

    def dispatch(self, verb: str, **kwargs: Any) -> dict[str, Any]:
        """Dispatch a verb to the appropriate handler.

        Args:
            verb: One of ALLOWED_VERBS
            **kwargs: Verb-specific arguments

        Returns:
            Dict with at least {"ok": bool, "verb": str}

        Raises:
            ValueError: If verb is not in ALLOWED_VERBS
        """
        if verb not in ALLOWED_VERBS:
            raise ValueError(
                f"Unknown verb '{verb}'. Allowed: {sorted(ALLOWED_VERBS)}"
            )

        handler = getattr(self, f"_do_{verb.replace('-', '_')}", None)
        if handler is None:
            return {"ok": False, "verb": verb, "error": f"No handler for '{verb}'"}

        try:
            result = handler(**kwargs)
            if isinstance(result, dict):
                result.setdefault("ok", True)
                result.setdefault("verb", verb)
                return result
            return {"ok": True, "verb": verb, "result": result}
        except Exception as e:
            return {"ok": False, "verb": verb, "error": str(e), "type": type(e).__name__}

    # ── Nix configuration verbs ─────────────────────────────────────

    def _do_nix_generate(self, resources: list[Resource] | None = None,
                          **kwargs: Any) -> dict[str, Any]:
        """Generate NixOS configuration from resources."""
        gen = ConfigGenerator(hostname=self._hostname)

        if resources:
            for r in resources:
                gen.add_resource(r)

        config_nix = gen.generate()
        flake_nix = gen.generate_flake()

        # Write to disk
        config_path = self._config_dir / "configuration.nix"
        flake_path = self._config_dir / "flake.nix"

        config_path.write_text(config_nix)
        flake_path.write_text(flake_nix)

        return {
            "ok": True,
            "config_path": str(config_path),
            "flake_path": str(flake_path),
            "config_length": len(config_nix),
            "flake_length": len(flake_nix),
        }

    def _do_nix_build(self, flake_dir: str = "", attribute: str = "",
                       out_link: str = "", **kwargs: Any) -> dict[str, Any]:
        """Build a NixOS configuration."""
        flake = flake_dir or str(self._config_dir)
        result = self._nix_builder.build_flake(flake, attribute=attribute, out_link=out_link)
        return result.to_dict()

    def _do_nix_switch(self, config_dir: str = "", target: str = "",
                        **kwargs: Any) -> dict[str, Any]:
        """Switch to a new NixOS configuration."""
        cfg = config_dir or str(self._config_dir)
        result = self._nix_builder.nixos_rebuild(cfg, action="switch", target=target)
        return result.to_dict()

    def _do_nix_rollback(self, config_dir: str = "", target: str = "",
                          **kwargs: Any) -> dict[str, Any]:
        """Roll back to previous NixOS generation."""
        cfg = config_dir or str(self._config_dir)
        # nixos-rebuild switch --rollback
        result = self._nix_builder.nixos_rebuild(cfg, action="switch", target=target)
        return result.to_dict()

    def _do_nix_eval(self, expr: str = "", **kwargs: Any) -> dict[str, Any]:
        """Evaluate a Nix expression."""
        if not expr:
            return {"ok": False, "error": "No expression provided"}
        result = self._nix_builder.eval_expr(expr)
        return result.to_dict()

    def _do_nix_gc(self, older_than: str = "30d", **kwargs: Any) -> dict[str, Any]:
        """Garbage collect old Nix generations."""
        result = self._nix_builder.collect_garbage(older_than=older_than)
        return result.to_dict()

    def _do_nix_status(self, **kwargs: Any) -> dict[str, Any]:
        """Check Nix availability."""
        available = self._nix_builder.is_available()
        version = self._nix_builder.nix_version() if available else ""
        return {
            "ok": True,
            "nix_available": available,
            "nix_version": version,
        }

    # ── VM lifecycle verbs ──────────────────────────────────────────

    def _do_vm_create(self, name: str = "", memory_mb: int = 2048,
                       vcpus: int = 2, disk_size_gb: int = 20,
                       **kwargs: Any) -> dict[str, Any]:
        """Create a new VM."""
        if not name:
            return {"ok": False, "error": "VM name is required"}
        config = VMConfig(
            name=name, memory_mb=memory_mb, vcpus=vcpus,
            disk_size_gb=disk_size_gb, **kwargs
        )
        info = self._vm_manager.create(config)
        return {"ok": True, **info.to_dict()}

    def _do_vm_start(self, name: str = "", **kwargs: Any) -> dict[str, Any]:
        """Start a VM."""
        if not name:
            return {"ok": False, "error": "VM name is required"}
        info = self._vm_manager.start(name)
        return {"ok": True, **info.to_dict()}

    def _do_vm_stop(self, name: str = "", force: bool = False,
                     **kwargs: Any) -> dict[str, Any]:
        """Stop a VM."""
        if not name:
            return {"ok": False, "error": "VM name is required"}
        info = self._vm_manager.stop(name, force=force)
        return {"ok": True, **info.to_dict()}

    def _do_vm_destroy(self, name: str = "", **kwargs: Any) -> dict[str, Any]:
        """Destroy a VM."""
        if not name:
            return {"ok": False, "error": "VM name is required"}
        result = self._vm_manager.destroy(name)
        return {"ok": True, **result}

    def _do_vm_snapshot(self, name: str = "", snapshot_name: str = "",
                         **kwargs: Any) -> dict[str, Any]:
        """Snapshot a VM."""
        if not name or not snapshot_name:
            return {"ok": False, "error": "VM name and snapshot_name are required"}
        result = self._vm_manager.snapshot(name, snapshot_name)
        return {"ok": True, **result}

    def _do_vm_restore(self, name: str = "", snapshot_name: str = "",
                        **kwargs: Any) -> dict[str, Any]:
        """Restore a VM from snapshot."""
        if not name or not snapshot_name:
            return {"ok": False, "error": "VM name and snapshot_name are required"}
        result = self._vm_manager.restore_snapshot(name, snapshot_name)
        return {"ok": True, **result}

    def _do_vm_status(self, name: str = "", **kwargs: Any) -> dict[str, Any]:
        """Get VM status."""
        if not name:
            return {"ok": False, "error": "VM name is required"}
        info = self._vm_manager.status(name)
        return {"ok": True, **info.to_dict()}

    def _do_vm_list(self, **kwargs: Any) -> dict[str, Any]:
        """List all managed VMs."""
        vms = self._vm_manager.list_vms()
        return {"ok": True, "vms": [v.to_dict() for v in vms]}

    # ── Resource mapping ────────────────────────────────────────────

    def _do_map_resources(self, resources: list[Resource] | None = None,
                           **kwargs: Any) -> dict[str, Any]:
        """Map Appliance resources to NixOS definitions."""
        if not resources:
            return {"ok": True, "services": [], "packages": []}
        services, packages = self._service_mapper.map_resources(resources)
        return {
            "ok": True,
            "services": [s.name for s in services],
            "packages": [p.name for p in packages],
            "service_count": len(services),
            "package_count": len(packages),
        }

    # ── Status ──────────────────────────────────────────────────────

    def _do_status(self, **kwargs: Any) -> dict[str, Any]:
        """Overall adapter status."""
        nix_available = self._nix_builder.is_available()
        vms = self._vm_manager.list_vms()
        config_exists = (self._config_dir / "configuration.nix").exists()

        return {
            "ok": True,
            "adapter": "NixOSAdapter",
            "hostname": self._hostname,
            "profile_tier": ProfileTier.NIXOS.value,
            "nix_available": nix_available,
            "nix_version": self._nix_builder.nix_version() if nix_available else "",
            "config_generated": config_exists,
            "config_dir": str(self._config_dir),
            "vm_count": len(vms),
            "vms_running": sum(1 for v in vms if v.state == VMState.RUNNING),
            "state_dir": str(self._state_dir),
        }
