# ADR: M4 — NixOS VM Backend (C12)

**Status:** Accepted  
**Date:** 2026-09-18  
**Author:** ProtoMegaBot2

## Context

The Omega Hive Appliance (M0–M3) manages services on the local host via the
`LocalAdapter`. While this works for existing Ubuntu/OCI environments, the
specification calls for **reproducible runtimes via Nix** and a NixOS VM
backend (C12) to achieve fully declarative, reproducible hive environments.

A NixOS VM backend would allow:
- Declarative service definitions (NixOS modules)
- Atomic upgrades and rollbacks (Nix generations)
- Reproducible builds from pinned Nix flake inputs
- VM-level isolation between agents
- Snapshot/restore at the VM level (complementing M3 app-level checkpoints)

## Decision

Implement M4 as a **NixOS adapter** that:

1. **Generates NixOS configurations** from Appliance service definitions
2. **Manages VM lifecycle** (create, start, stop, rebuild, destroy, snapshot)
3. **Integrates with the existing verb system** (extending ALLOWED_VERBS)
4. **Supports both local QEMU/microvm and remote NixOS hosts**
5. **Provides a NixOS profile tier** (already defined as `ProfileTier.NIXOS`)

### Architecture

```
adapters/
  nixos/
    __init__.py           — NixOSAdapter (verb-based, like LocalAdapter)
    config_generator.py   — Generate NixOS module expressions from Appliance state
    vm_manager.py         — QEMU/microvm lifecycle (create/start/stop/snapshot)
    nix_builder.py        — Nix build/eval operations (nix build, nix eval)
    service_module.py     — Map Appliance services → NixOS service definitions
```

### New Verbs

| Verb | Description |
|------|-------------|
| `nix-build` | Build a NixOS configuration (produces a system closure) |
| `nix-switch` | Switch a running VM to a new configuration generation |
| `nix-rollback` | Roll back to the previous NixOS generation |
| `vm-create` | Create a new QEMU/microvm VM from a NixOS config |
| `vm-start` | Start a stopped VM |
| `vm-stop` | Gracefully stop a running VM |
| `vm-destroy` | Remove a VM and its state |
| `vm-snapshot` | Snapshot a VM's disk state |
| `vm-restore` | Restore a VM from a snapshot |
| `vm-status` | Query VM running state |

### Nix Configuration Generation

The `ConfigGenerator` maps Appliance concepts to NixOS modules:

- `Resource(kind=SERVICE)` → `systemd.services.<name>` NixOS module
- `Resource(kind=FILE)` → `environment.etc.<name>` or file activation
- `Resource(kind=PACKAGE)` → `environment.systemPackages` entry
- `Resource(kind=NETWORK)` → `networking.*` NixOS options
- Repair plans → NixOS configuration changes (declarative, not imperative)

### VM Manager

The `VMManager` wraps QEMU/microvm operations:

- Uses `qemu-system-x86_64` or `microvm.nix` for lightweight VMs
- Each agent can have its own VM with isolated NixOS configuration
- Snapshots use QEMU's internal snapshot or ZFS/btrfs snapshots
- Supports headless operation with serial console access

### Integration with Existing Framework

- `NixOSAdapter` implements the same verb-dispatch pattern as `LocalAdapter`
- Existing `Appliance.set_executor()` works with a `NixOSExecutor`
- Existing checkpoint/restore (M3) integrates with VM snapshots
- Existing upgrade controller (M3) maps to `nix-switch`/`nix-rollback`

## Consequences

- **Nix must be available** on the host (or in the container) for build operations
- VMs require KVM/QEMU support (available on most Linux hosts)
- Configuration generation is deterministic and testable without Nix installed
- The adapter gracefully degrades: config generation works everywhere,
  VM operations require QEMU, Nix operations require Nix
- Tests use mocked subprocess calls for Nix/QEMU commands

## Work Packages

| ID | Description | Dependencies |
|----|-------------|--------------|
| C12.1 | NixOS config generator (service/file/package/network mapping) | M0 schemas |
| C12.2 | Nix builder wrapper (build, eval, flake operations) | C12.1 |
| C12.3 | VM manager (QEMU lifecycle, snapshots) | — |
| C12.4 | NixOSAdapter (verb dispatch, integration) | C12.1–C12.3 |
| C12.5 | NixOSExecutor (executor subclass for repair plans) | C12.4 |
| C12.6 | Tests (unit + integration, mocked Nix/QEMU) | C12.1–C12.5 |
| C12.7 | README + docs update | C12.6 |
