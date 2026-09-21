"""
Service mapper: Appliance services → NixOS service definitions.

Maps high-level Appliance service descriptions to NixOS systemd service
modules, handling common patterns (web servers, databases, agents, etc.).

C12.1 work package (supplementary).
"""
from __future__ import annotations

from typing import Any, Optional

from adapters.nixos.config_generator import NixPackageDef, NixServiceDef
from schemas.types import Resource, ResourceKind

# Well-known service templates
_TEMPLATES: dict[str, dict[str, Any]] = {
    "nginx": {
        "exec_start": "${pkgs.nginx}/bin/nginx -c /etc/nginx/nginx.conf",
        "after": ["network.target"],
        "nixpkgs": "nginx",
    },
    "postgresql": {
        "exec_start": "${pkgs.postgresql}/bin/postgres -D /var/lib/postgresql/data",
        "after": ["network.target"],
        "user": "postgres",
        "group": "postgres",
        "nixpkgs": "postgresql",
    },
    "redis": {
        "exec_start": "${pkgs.redis}/bin/redis-server /etc/redis/redis.conf",
        "after": ["network.target"],
        "nixpkgs": "redis",
    },
    "openssh": {
        "exec_start": "${pkgs.openssh}/bin/sshd -D",
        "after": ["network.target"],
        "nixpkgs": "openssh",
    },
}


class ServiceMapper:
    """Maps Appliance resources to NixOS service and package definitions.

    Recognizes well-known service types and applies appropriate NixOS
    module patterns. Unknown services get a generic systemd wrapper.
    """

    def __init__(self) -> None:
        self._templates = dict(_TEMPLATES)

    def register_template(self, name: str, template: dict[str, Any]) -> None:
        """Register a custom service template."""
        self._templates[name] = template

    def map_resource(self, resource: Resource) -> tuple[
        Optional[NixServiceDef], Optional[NixPackageDef]
    ]:
        """Map a single Appliance resource to NixOS definitions.

        Returns (service_def, package_def) — either may be None.
        Only SERVICE and PACKAGE resource kinds produce output.
        """
        if resource.kind == ResourceKind.SERVICE:
            return self._map_service(resource), self._infer_package(resource)
        elif resource.kind == ResourceKind.PACKAGE:
            return None, NixPackageDef(
                name=resource.name,
                nixpkgs_attr=resource.attributes.get("nixpkgs_attr", f"pkgs.{resource.name}"),
            )
        return None, None

    def map_resources(self, resources: list[Resource]) -> tuple[
        list[NixServiceDef], list[NixPackageDef]
    ]:
        """Map multiple resources, returning aggregated lists."""
        services = []
        packages = []
        for r in resources:
            svc, pkg = self.map_resource(r)
            if svc:
                services.append(svc)
            if pkg:
                packages.append(pkg)
        return services, packages

    def _map_service(self, r: Resource) -> NixServiceDef:
        """Map a SERVICE resource to a NixServiceDef."""
        attrs = r.attributes
        template_name = attrs.get("template", r.name.lower())
        template = self._templates.get(template_name, {})

        return NixServiceDef(
            name=r.name,
            exec_start=attrs.get("exec_start",
                        attrs.get("command",
                        template.get("exec_start", f"/usr/bin/{r.name}"))),
            description=attrs.get("description", f"Managed service: {r.name}"),
            after=attrs.get("after", template.get("after", ["network.target"])),
            wants=attrs.get("wants", template.get("wants", [])),
            environment=attrs.get("environment", {}),
            restart_policy=attrs.get("restart_policy",
                            template.get("restart_policy", "on-failure")),
            working_directory=attrs.get("working_directory",
                               template.get("working_directory", "")),
            user=attrs.get("user", template.get("user", "")),
            group=attrs.get("group", template.get("group", "")),
            enable=attrs.get("enable", True),
        )

    def _infer_package(self, r: Resource) -> Optional[NixPackageDef]:
        """Infer a package dependency from a service resource."""
        attrs = r.attributes
        template_name = attrs.get("template", r.name.lower())
        template = self._templates.get(template_name, {})

        pkg_name = attrs.get("nixpkgs_attr", template.get("nixpkgs", ""))
        if pkg_name:
            return NixPackageDef(name=r.name, nixpkgs_attr=f"pkgs.{pkg_name}")
        return None
