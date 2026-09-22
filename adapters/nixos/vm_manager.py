"""
VM lifecycle manager for NixOS VMs.

Manages QEMU/microvm instances: create, start, stop, destroy, snapshot, restore.
All operations go through subprocess calls to qemu-system or virsh, making
them testable via mocked subprocess.

C12.3 work package.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class VMState(str, Enum):
    """Possible states of a managed VM."""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    CREATING = "creating"
    UNKNOWN = "unknown"


@dataclass
class VMConfig:
    """Configuration for a NixOS VM."""
    name: str
    memory_mb: int = 2048
    vcpus: int = 2
    disk_size_gb: int = 20
    nixos_config_path: str = ""     # path to configuration.nix
    disk_image_path: str = ""       # path to qcow2 disk image
    kernel_path: str = ""           # optional: direct kernel boot
    initrd_path: str = ""           # optional: direct kernel boot
    extra_qemu_args: list[str] = field(default_factory=list)
    network_mode: str = "user"      # user, tap, bridge
    serial_console: bool = True
    ssh_port_forward: int = 0       # host port for SSH forwarding (user mode)

    def to_dict(self) -> dict[str, Any]:
        """Execute to dict operation."""
        return {
            "name": self.name,
            "memory_mb": self.memory_mb,
            "vcpus": self.vcpus,
            "disk_size_gb": self.disk_size_gb,
            "nixos_config_path": self.nixos_config_path,
            "disk_image_path": self.disk_image_path,
            "kernel_path": self.kernel_path,
            "initrd_path": self.initrd_path,
            "extra_qemu_args": self.extra_qemu_args,
            "network_mode": self.network_mode,
            "serial_console": self.serial_console,
            "ssh_port_forward": self.ssh_port_forward,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> VMConfig:
        """Execute from dict operation."""
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class VMInfo:
    """Runtime information about a VM."""
    name: str
    state: VMState
    pid: int = 0
    config: Optional[VMConfig] = None
    uptime_seconds: float = 0.0
    snapshots: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Execute to dict operation."""
        return {
            "name": self.name,
            "state": self.state.value,
            "pid": self.pid,
            "uptime_seconds": self.uptime_seconds,
            "snapshots": self.snapshots,
        }


# Hard limits
MAX_MEMORY_MB = 16384
MAX_VCPUS = 8
MAX_DISK_GB = 200
HARD_TIMEOUT = 120


class VMManager:
    """Manages NixOS VM lifecycle via QEMU.

    All QEMU/Nix operations go through _run_cmd() which can be mocked
    for testing. The manager tracks VMs via a state directory containing
    JSON metadata and PID files.
    """

    def __init__(self, state_dir: str, qemu_binary: str = "qemu-system-x86_64"):
        self._state_dir = Path(state_dir)
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._qemu_binary = qemu_binary

    @property
    def state_dir(self) -> Path:
        """Return state dir."""
        return self._state_dir

    def _vm_dir(self, name: str) -> Path:
        """Per-VM state directory."""
        d = self._state_dir / name
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _config_path(self, name: str) -> Path:
        return self._vm_dir(name) / "vm-config.json"

    def _pid_path(self, name: str) -> Path:
        return self._vm_dir(name) / "qemu.pid"

    def _run_cmd(self, cmd: list[str], timeout: int = HARD_TIMEOUT,
                 check: bool = False) -> subprocess.CompletedProcess:
        """Run a subprocess command. Mockable for tests."""
        timeout = min(timeout, HARD_TIMEOUT)
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=check
        )

    def list_vms(self) -> list[VMInfo]:
        """List all managed VMs."""
        vms = []
        if not self._state_dir.exists():
            return vms
        for entry in sorted(self._state_dir.iterdir()):
            if entry.is_dir() and (entry / "vm-config.json").exists():
                vms.append(self.status(entry.name))
        return vms

    def create(self, config: VMConfig) -> VMInfo:
        """Create a new VM. Does not start it.

        Validates config, creates disk image, saves metadata.
        """
        _validate_config(config)

        vm_dir = self._vm_dir(config.name)
        cfg_path = self._config_path(config.name)

        if cfg_path.exists():
            raise ValueError(f"VM '{config.name}' already exists")

        # Set default disk image path if not specified
        if not config.disk_image_path:
            config.disk_image_path = str(vm_dir / f"{config.name}.qcow2")

        # Create disk image
        self._run_cmd([
            "qemu-img", "create", "-f", "qcow2",
            config.disk_image_path, f"{config.disk_size_gb}G"
        ], check=True)

        # Save config
        cfg_path.write_text(json.dumps(config.to_dict(), indent=2))

        return VMInfo(name=config.name, state=VMState.STOPPED, config=config)

    def start(self, name: str) -> VMInfo:
        """Start a stopped VM."""
        config = self._load_config(name)
        pid_path = self._pid_path(name)

        if pid_path.exists():
            pid = self._read_pid(name)
            if pid and _process_alive(pid):
                return VMInfo(name=name, state=VMState.RUNNING, pid=pid, config=config)

        # Build QEMU command
        cmd = self._build_qemu_cmd(config)

        # Start QEMU as a background process (detached)
        proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        pid_path.write_text(str(proc.pid))

        return VMInfo(name=name, state=VMState.RUNNING, pid=proc.pid, config=config)

    def stop(self, name: str, force: bool = False) -> VMInfo:
        """Stop a running VM. Graceful by default, force kills with force=True."""
        config = self._load_config(name)
        pid = self._read_pid(name)

        if not pid or not _process_alive(pid):
            self._pid_path(name).unlink(missing_ok=True)
            return VMInfo(name=name, state=VMState.STOPPED, config=config)

        import signal
        sig = signal.SIGKILL if force else signal.SIGTERM
        try:
            os.kill(pid, sig)
            # Wait briefly for process to exit
            for _ in range(10):
                if not _process_alive(pid):
                    break
                time.sleep(0.5)
        except ProcessLookupError:
            pass

        self._pid_path(name).unlink(missing_ok=True)
        return VMInfo(name=name, state=VMState.STOPPED, config=config)

    def destroy(self, name: str) -> dict[str, Any]:
        """Destroy a VM: stop it, remove disk and state."""
        self.stop(name, force=True)
        vm_dir = self._vm_dir(name)
        if vm_dir.exists():
            shutil.rmtree(str(vm_dir))
        return {"name": name, "destroyed": True}

    def snapshot(self, name: str, snapshot_name: str) -> dict[str, Any]:
        """Create a QEMU snapshot of the VM's disk."""
        config = self._load_config(name)
        disk = config.disk_image_path
        if not disk:
            raise ValueError(f"No disk image for VM '{name}'")

        result = self._run_cmd([
            "qemu-img", "snapshot", "-c", snapshot_name, disk
        ])
        success = result.returncode == 0

        # Record snapshot in metadata
        if success:
            snap_file = self._vm_dir(name) / "snapshots.json"
            snaps = json.loads(snap_file.read_text()) if snap_file.exists() else []
            snaps.append({"name": snapshot_name, "ts": time.time()})
            snap_file.write_text(json.dumps(snaps, indent=2))

        return {
            "name": name,
            "snapshot": snapshot_name,
            "success": success,
            "stderr": result.stderr,
        }

    def restore_snapshot(self, name: str, snapshot_name: str) -> dict[str, Any]:
        """Restore a VM to a previously created snapshot."""
        config = self._load_config(name)
        disk = config.disk_image_path

        # VM must be stopped to restore
        pid = self._read_pid(name)
        if pid and _process_alive(pid):
            raise RuntimeError(f"VM '{name}' must be stopped before restoring a snapshot")

        result = self._run_cmd([
            "qemu-img", "snapshot", "-a", snapshot_name, disk
        ])
        return {
            "name": name,
            "snapshot": snapshot_name,
            "restored": result.returncode == 0,
            "stderr": result.stderr,
        }

    def list_snapshots(self, name: str) -> list[dict[str, Any]]:
        """List available snapshots for a VM."""
        snap_file = self._vm_dir(name) / "snapshots.json"
        if snap_file.exists():
            return json.loads(snap_file.read_text())
        return []

    def status(self, name: str) -> VMInfo:
        """Get current status of a VM."""
        try:
            config = self._load_config(name)
        except (FileNotFoundError, ValueError):
            return VMInfo(name=name, state=VMState.UNKNOWN)

        pid = self._read_pid(name)
        if pid and _process_alive(pid):
            state = VMState.RUNNING
        else:
            state = VMState.STOPPED
            if pid:
                self._pid_path(name).unlink(missing_ok=True)

        snaps = self.list_snapshots(name)
        return VMInfo(
            name=name, state=state, pid=pid or 0,
            config=config, snapshots=[s["name"] for s in snaps]
        )

    def _load_config(self, name: str) -> VMConfig:
        cfg_path = self._config_path(name)
        if not cfg_path.exists():
            raise FileNotFoundError(f"VM '{name}' does not exist")
        return VMConfig.from_dict(json.loads(cfg_path.read_text()))

    def _read_pid(self, name: str) -> int:
        pid_path = self._pid_path(name)
        if not pid_path.exists():
            return 0
        try:
            return int(pid_path.read_text().strip())
        except (ValueError, OSError):
            return 0

    def _build_qemu_cmd(self, config: VMConfig) -> list[str]:
        """Build the QEMU command line from VMConfig."""
        cmd = [
            self._qemu_binary,
            "-m", str(config.memory_mb),
            "-smp", str(config.vcpus),
            "-drive", f"file={config.disk_image_path},format=qcow2,if=virtio",
            "-nographic" if config.serial_console else "-display", "none" if not config.serial_console else "",
            "-daemonize",
            "-pidfile", str(self._pid_path(config.name)),
        ]

        # Clean up empty args
        cmd = [c for c in cmd if c]

        # Direct kernel boot
        if config.kernel_path:
            cmd.extend(["-kernel", config.kernel_path])
        if config.initrd_path:
            cmd.extend(["-initrd", config.initrd_path])

        # Network
        if config.network_mode == "user":
            net_opts = "user,id=net0"
            if config.ssh_port_forward:
                net_opts += f",hostfwd=tcp::{config.ssh_port_forward}-:22"
            cmd.extend(["-netdev", net_opts, "-device", "virtio-net-pci,netdev=net0"])
        elif config.network_mode == "tap":
            cmd.extend(["-netdev", "tap,id=net0", "-device", "virtio-net-pci,netdev=net0"])

        # Extra args
        cmd.extend(config.extra_qemu_args)

        return cmd


def _validate_config(config: VMConfig) -> None:
    """Validate VM configuration parameters."""
    if not config.name:
        raise ValueError("VM name is required")
    if not config.name.replace("-", "").replace("_", "").isalnum():
        raise ValueError(f"VM name must be alphanumeric (with - and _): '{config.name}'")
    if config.memory_mb <= 0 or config.memory_mb > MAX_MEMORY_MB:
        raise ValueError(f"Memory must be 1–{MAX_MEMORY_MB} MB, got {config.memory_mb}")
    if config.vcpus <= 0 or config.vcpus > MAX_VCPUS:
        raise ValueError(f"vCPUs must be 1–{MAX_VCPUS}, got {config.vcpus}")
    if config.disk_size_gb <= 0 or config.disk_size_gb > MAX_DISK_GB:
        raise ValueError(f"Disk must be 1–{MAX_DISK_GB} GB, got {config.disk_size_gb}")


def _process_alive(pid: int) -> bool:
    """Check if a process with the given PID is alive."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
