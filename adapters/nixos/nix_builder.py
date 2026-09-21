"""
Nix build/eval operations wrapper.

Wraps nix build, nix eval, nixos-rebuild, and related commands.
All operations go through _run_cmd() for testability.

C12.2 work package.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any

HARD_TIMEOUT = 300  # Nix builds can be slow


@dataclass
class NixBuildResult:
    """Result of a Nix build operation."""
    success: bool
    out_path: str = ""          # /nix/store/... result path
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "out_path": self.out_path,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
        }


@dataclass
class NixEvalResult:
    """Result of a Nix eval operation."""
    success: bool
    value: Any = None
    exit_code: int = 0
    stderr: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "value": self.value,
            "exit_code": self.exit_code,
            "stderr": self.stderr,
        }


class NixBuilder:
    """Wraps Nix CLI operations for building and evaluating NixOS configurations.

    Supports both flake-based and traditional nix-build workflows.
    """

    def __init__(self, nix_binary: str = "nix", timeout: int = HARD_TIMEOUT):
        self._nix = nix_binary
        self._timeout = min(timeout, HARD_TIMEOUT)

    def _run_cmd(self, cmd: list[str], timeout: int | None = None,
                 check: bool = False) -> subprocess.CompletedProcess:
        """Run a subprocess. Mockable for tests."""
        t = min(timeout or self._timeout, HARD_TIMEOUT)
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=t, check=check
        )

    def is_available(self) -> bool:
        """Check if nix is available on the system."""
        try:
            result = self._run_cmd([self._nix, "--version"], timeout=10)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def nix_version(self) -> str:
        """Return the nix version string, or empty if unavailable."""
        try:
            result = self._run_cmd([self._nix, "--version"], timeout=10)
            return result.stdout.strip() if result.returncode == 0 else ""
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""

    def build_flake(self, flake_dir: str, attribute: str = "",
                    out_link: str = "") -> NixBuildResult:
        """Build a flake-based NixOS configuration.

        Args:
            flake_dir: Directory containing flake.nix
            attribute: Flake output attribute (e.g. 'nixosConfigurations.hive-node.config.system.build.toplevel')
            out_link: Path for the result symlink (default: ./result)
        """
        import time
        start = time.time()

        flake_ref = flake_dir
        if attribute:
            flake_ref = f"{flake_dir}#{attribute}"

        cmd = [self._nix, "build", flake_ref, "--no-link"]
        if out_link:
            cmd = [self._nix, "build", flake_ref, "-o", out_link]

        cmd.extend(["--extra-experimental-features", "nix-command flakes"])

        try:
            result = self._run_cmd(cmd)
            elapsed = (time.time() - start) * 1000

            out_path = ""
            if result.returncode == 0:
                if out_link and os.path.islink(out_link):
                    out_path = os.readlink(out_link)
                elif not out_link:
                    # Try to get the output path from nix
                    path_result = self._run_cmd([
                        self._nix, "path-info", flake_ref,
                        "--extra-experimental-features", "nix-command flakes"
                    ], timeout=30)
                    if path_result.returncode == 0:
                        out_path = path_result.stdout.strip()

            return NixBuildResult(
                success=result.returncode == 0,
                out_path=out_path,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=elapsed,
            )
        except subprocess.TimeoutExpired:
            elapsed = (time.time() - start) * 1000
            return NixBuildResult(
                success=False, exit_code=-1,
                stderr=f"Build timed out after {self._timeout}s",
                duration_ms=elapsed,
            )

    def build_legacy(self, nix_file: str, out_link: str = "") -> NixBuildResult:
        """Build using traditional nix-build (non-flake)."""
        import time
        start = time.time()

        cmd = ["nix-build", nix_file]
        if out_link:
            cmd.extend(["-o", out_link])
        else:
            cmd.append("--no-out-link")

        try:
            result = self._run_cmd(cmd)
            elapsed = (time.time() - start) * 1000

            out_path = ""
            if result.returncode == 0:
                out_path = result.stdout.strip().split("\n")[-1]

            return NixBuildResult(
                success=result.returncode == 0,
                out_path=out_path,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=elapsed,
            )
        except subprocess.TimeoutExpired:
            elapsed = (time.time() - start) * 1000
            return NixBuildResult(
                success=False, exit_code=-1,
                stderr=f"Build timed out after {self._timeout}s",
                duration_ms=elapsed,
            )

    def eval_expr(self, expr: str) -> NixEvalResult:
        """Evaluate a Nix expression and return the result as JSON."""
        cmd = [
            self._nix, "eval", "--json", "--expr", expr,
            "--extra-experimental-features", "nix-command flakes"
        ]
        try:
            result = self._run_cmd(cmd, timeout=30)
            value = None
            if result.returncode == 0 and result.stdout.strip():
                try:
                    value = json.loads(result.stdout)
                except json.JSONDecodeError:
                    value = result.stdout.strip()
            return NixEvalResult(
                success=result.returncode == 0,
                value=value,
                exit_code=result.returncode,
                stderr=result.stderr,
            )
        except subprocess.TimeoutExpired:
            return NixEvalResult(
                success=False, exit_code=-1,
                stderr="Eval timed out",
            )

    def eval_flake_attr(self, flake_dir: str, attr: str) -> NixEvalResult:
        """Evaluate a flake attribute and return as JSON."""
        cmd = [
            self._nix, "eval", f"{flake_dir}#{attr}", "--json",
            "--extra-experimental-features", "nix-command flakes"
        ]
        try:
            result = self._run_cmd(cmd, timeout=30)
            value = None
            if result.returncode == 0 and result.stdout.strip():
                try:
                    value = json.loads(result.stdout)
                except json.JSONDecodeError:
                    value = result.stdout.strip()
            return NixEvalResult(
                success=result.returncode == 0,
                value=value,
                exit_code=result.returncode,
                stderr=result.stderr,
            )
        except subprocess.TimeoutExpired:
            return NixEvalResult(
                success=False, exit_code=-1,
                stderr="Eval timed out",
            )

    def nixos_rebuild(self, config_dir: str, action: str = "switch",
                      target: str = "") -> NixBuildResult:
        """Run nixos-rebuild (switch, boot, test, dry-activate).

        For remote targets, uses --target-host.
        """
        import time
        start = time.time()

        valid_actions = {"switch", "boot", "test", "dry-activate", "build", "dry-build"}
        if action not in valid_actions:
            raise ValueError(f"Invalid nixos-rebuild action: {action}. Valid: {valid_actions}")

        cmd = ["nixos-rebuild", action, "-I", f"nixos-config={config_dir}/configuration.nix"]
        if target:
            cmd.extend(["--target-host", target])

        try:
            result = self._run_cmd(cmd)
            elapsed = (time.time() - start) * 1000
            return NixBuildResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=elapsed,
            )
        except subprocess.TimeoutExpired:
            elapsed = (time.time() - start) * 1000
            return NixBuildResult(
                success=False, exit_code=-1,
                stderr=f"nixos-rebuild timed out after {self._timeout}s",
                duration_ms=elapsed,
            )

    def collect_garbage(self, older_than: str = "30d") -> NixBuildResult:
        """Run nix-collect-garbage to free disk space."""
        import time
        start = time.time()
        cmd = ["nix-collect-garbage", "--delete-older-than", older_than]
        try:
            result = self._run_cmd(cmd, timeout=120)
            elapsed = (time.time() - start) * 1000
            return NixBuildResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=elapsed,
            )
        except subprocess.TimeoutExpired:
            elapsed = (time.time() - start) * 1000
            return NixBuildResult(
                success=False, exit_code=-1,
                stderr="Garbage collection timed out",
                duration_ms=elapsed,
            )
