"""
NixOS configuration generator.

Maps Appliance Resource/Service definitions to NixOS module expressions.
Generates reproducible, evaluable Nix configuration files.

C12.1 work package.
"""
from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from typing import Any

from schemas.types import Resource, ResourceKind


@dataclass
class NixServiceDef:
    """A NixOS systemd service definition derived from an Appliance Resource."""
    name: str
    exec_start: str
    description: str = ""
    after: list[str] = field(default_factory=list)
    wants: list[str] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)
    restart_policy: str = "on-failure"
    working_directory: str = ""
    user: str = ""
    group: str = ""
    enable: bool = True

    def to_nix(self) -> str:
        """Render as a NixOS systemd.services.<name> module fragment."""
        lines = []
        lines.append(f'  systemd.services."{self.name}" = {{')
        if self.description:
            lines.append(f'    description = "{_nix_escape(self.description)}";')
        lines.append(f'    enable = {"true" if self.enable else "false"};')
        # serviceConfig
        lines.append('    serviceConfig = {')
        lines.append(f'      ExecStart = "{_nix_escape(self.exec_start)}";')
        lines.append(f'      Restart = "{self.restart_policy}";')
        if self.working_directory:
            lines.append(f'      WorkingDirectory = "{_nix_escape(self.working_directory)}";')
        if self.user:
            lines.append(f'      User = "{_nix_escape(self.user)}";')
        if self.group:
            lines.append(f'      Group = "{_nix_escape(self.group)}";')
        lines.append('    };')
        # environment
        if self.environment:
            lines.append('    environment = {')
            for k, v in sorted(self.environment.items()):
                lines.append(f'      "{_nix_escape(k)}" = "{_nix_escape(v)}";')
            lines.append('    };')
        # dependencies
        if self.after:
            after_str = " ".join(f'"{_nix_escape(a)}"' for a in self.after)
            lines.append(f'    after = [ {after_str} ];')
        if self.wants:
            wants_str = " ".join(f'"{_nix_escape(w)}"' for w in self.wants)
            lines.append(f'    wants = [ {wants_str} ];')
        lines.append('  };')
        return "\n".join(lines)


@dataclass
class NixPackageDef:
    """A package to include in environment.systemPackages."""
    name: str
    nixpkgs_attr: str = ""  # e.g. "pkgs.nginx", defaults to "pkgs.<name>"

    def to_nix(self) -> str:
        """Execute to nix operation."""
        attr = self.nixpkgs_attr or f"pkgs.{self.name}"
        return f"    {attr}"


@dataclass
class NixFileDef:
    """A file to deploy via environment.etc."""
    dest_path: str          # e.g. "myapp/config.json"
    content: str = ""
    source_path: str = ""   # alternative: copy from source
    mode: str = "0644"
    user: str = "root"
    group: str = "root"

    def to_nix(self) -> str:
        """Execute to nix operation."""
        lines = []
        safe_name = self.dest_path.replace("/", "-").replace(".", "-")
        lines.append(f'  environment.etc."{safe_name}" = {{')
        lines.append(f'    target = "{_nix_escape(self.dest_path)}";')
        if self.content:
            # Use pkgs.writeText for inline content
            escaped = _nix_escape(self.content)
            lines.append(f'    text = \x27\x27{escaped}\x27\x27;')
        elif self.source_path:
            lines.append(f'    source = {self.source_path};')
        lines.append(f'    mode = "{self.mode}";')
        lines.append(f'    user = "{_nix_escape(self.user)}";')
        lines.append(f'    group = "{_nix_escape(self.group)}";')
        lines.append('  };')
        return "\n".join(lines)


@dataclass
class NixNetworkDef:
    """Network configuration fragment."""
    hostname: str = ""
    firewall_allowed_tcp: list[int] = field(default_factory=list)
    firewall_allowed_udp: list[int] = field(default_factory=list)
    interfaces: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_nix(self) -> str:
        """Execute to nix operation."""
        lines = []
        if self.hostname:
            lines.append(f'  networking.hostName = "{_nix_escape(self.hostname)}";')
        if self.firewall_allowed_tcp:
            ports = " ".join(str(p) for p in self.firewall_allowed_tcp)
            lines.append(f'  networking.firewall.allowedTCPPorts = [ {ports} ];')
        if self.firewall_allowed_udp:
            ports = " ".join(str(p) for p in self.firewall_allowed_udp)
            lines.append(f'  networking.firewall.allowedUDPPorts = [ {ports} ];')
        for iface, cfg in sorted(self.interfaces.items()):
            if "address" in cfg:
                lines.append(f'  networking.interfaces."{_nix_escape(iface)}".ipv4.addresses = [')
                lines.append(f'    {{ address = "{cfg["address"]}"; prefixLength = {cfg.get("prefix", 24)}; }}')
                lines.append('  ];')
        return "\n".join(lines)


class ConfigGenerator:
    """Generate a complete NixOS configuration from Appliance resources.

    Transforms Appliance Resource objects into NixOS module expressions that
    can be evaluated by `nix-build` or `nixos-rebuild`.
    """

    def __init__(self, hostname: str = "hive-node"):
        self.hostname = hostname
        self._services: list[NixServiceDef] = []
        self._packages: list[NixPackageDef] = []
        self._files: list[NixFileDef] = []
        self._network: NixNetworkDef = NixNetworkDef(hostname=hostname)
        self._extra_modules: list[str] = []

    def add_resource(self, resource: Resource) -> None:
        """Map an Appliance Resource to the appropriate NixOS definition."""
        if resource.kind == ResourceKind.SERVICE:
            self._add_service(resource)
        elif resource.kind == ResourceKind.PACKAGE:
            self._add_package(resource)
        elif resource.kind == ResourceKind.FILE:
            self._add_file(resource)
        elif resource.kind == ResourceKind.NETWORK:
            self._add_network(resource)
        # CONFIG, PROCESS, VOLUME: silently skipped for now

    def add_service(self, svc: NixServiceDef) -> None:
        """Add a pre-built service definition."""
        self._services.append(svc)

    def add_package(self, pkg: NixPackageDef) -> None:
        """Add a pre-built package definition."""
        self._packages.append(pkg)

    def add_file(self, f: NixFileDef) -> None:
        """Add a pre-built file definition."""
        self._files.append(f)

    def add_extra_module(self, nix_expr: str) -> None:
        """Add a raw Nix expression to include in the configuration."""
        self._extra_modules.append(nix_expr)

    def set_network(self, net: NixNetworkDef) -> None:
        """Override the network configuration."""
        self._network = net

    def generate(self) -> str:
        """Generate the complete NixOS configuration.nix content."""
        sections = []

        # Header
        sections.append("# Generated by Omega Hive Appliance — M4 NixOS Backend")
        sections.append("# DO NOT EDIT MANUALLY — regenerate from Appliance state")
        sections.append("{ config, pkgs, lib, ... }:\n{")

        # Boot / basic system
        sections.append("  # Basic system configuration")
        sections.append('  system.stateVersion = "24.05";')
        sections.append("")

        # Network
        net_nix = self._network.to_nix()
        if net_nix:
            sections.append("  # Network configuration")
            sections.append(net_nix)
            sections.append("")

        # Packages
        if self._packages:
            sections.append("  # System packages")
            sections.append("  environment.systemPackages = with pkgs; [")
            for pkg in self._packages:
                sections.append(f"    {pkg.nixpkgs_attr or pkg.name}")
            sections.append("  ];")
            sections.append("")

        # Services
        if self._services:
            sections.append("  # Managed services")
            for svc in self._services:
                sections.append(svc.to_nix())
                sections.append("")

        # Files
        if self._files:
            sections.append("  # Managed files")
            for f in self._files:
                sections.append(f.to_nix())
                sections.append("")

        # Extra modules
        for mod in self._extra_modules:
            sections.append("  # Extra module")
            sections.append(f"  {mod}")
            sections.append("")

        # Enable SSH by default for managed nodes
        sections.append("  # SSH access for management")
        sections.append("  services.openssh.enable = true;")
        sections.append("  services.openssh.settings.PermitRootLogin = \"prohibit-password\";")
        sections.append("")

        # Nix settings
        sections.append("  # Nix configuration")
        sections.append("  nix.settings.experimental-features = [ \"nix-command\" \"flakes\" ];")

        sections.append("}")
        return "\n".join(sections)

    def generate_flake(self, system: str = "x86_64-linux") -> str:
        """Generate a flake.nix wrapper for the configuration."""
        return textwrap.dedent(f'''\
            # Generated by Omega Hive Appliance — M4 NixOS Backend
            {{
              description = "Hive Appliance managed NixOS configuration — {_nix_escape(self.hostname)}";

              inputs = {{
                nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
              }};

              outputs = {{ self, nixpkgs }}: {{
                nixosConfigurations."{_nix_escape(self.hostname)}" = nixpkgs.lib.nixosSystem {{
                  system = "{system}";
                  modules = [
                    ./configuration.nix
                  ];
                }};
              }};
            }}
        ''')

    def _add_service(self, r: Resource) -> None:
        attrs = r.attributes
        svc = NixServiceDef(
            name=r.name,
            exec_start=attrs.get("exec_start", attrs.get("command", f"/usr/bin/{r.name}")),
            description=attrs.get("description", f"Managed service: {r.name}"),
            after=attrs.get("after", ["network.target"]),
            wants=attrs.get("wants", []),
            environment=attrs.get("environment", {}),
            restart_policy=attrs.get("restart_policy", "on-failure"),
            working_directory=attrs.get("working_directory", ""),
            user=attrs.get("user", ""),
            group=attrs.get("group", ""),
            enable=attrs.get("enable", True),
        )
        self._services.append(svc)

    def _add_package(self, r: Resource) -> None:
        pkg = NixPackageDef(
            name=r.name,
            nixpkgs_attr=r.attributes.get("nixpkgs_attr", ""),
        )
        self._packages.append(pkg)

    def _add_file(self, r: Resource) -> None:
        f = NixFileDef(
            dest_path=r.attributes.get("dest_path", r.name),
            content=r.attributes.get("content", ""),
            source_path=r.attributes.get("source_path", ""),
            mode=r.attributes.get("mode", "0644"),
            user=r.attributes.get("user", "root"),
            group=r.attributes.get("group", "root"),
        )
        self._files.append(f)

    def _add_network(self, r: Resource) -> None:
        attrs = r.attributes
        if attrs.get("hostname"):
            self._network.hostname = attrs["hostname"]
        if attrs.get("firewall_tcp"):
            self._network.firewall_allowed_tcp.extend(attrs["firewall_tcp"])
        if attrs.get("firewall_udp"):
            self._network.firewall_allowed_udp.extend(attrs["firewall_udp"])
        if attrs.get("interfaces"):
            self._network.interfaces.update(attrs["interfaces"])


def _nix_escape(s: str) -> str:
    """Escape a string for safe inclusion in Nix expressions."""
    return (s
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("${", "\\${")
        .replace("\n", "\\n")
        .replace("\t", "\\t"))
