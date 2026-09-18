"""
NixOS VM backend adapter for the Omega Hive Appliance.

M4 / C12 work package — NixOS VM backend.

Provides:
- NixOS configuration generation from Appliance service definitions
- VM lifecycle management (QEMU/microvm)
- Nix build/eval operations
- Declarative service mapping

The adapter follows the same verb-dispatch pattern as LocalAdapter.
"""

from adapters.nixos.adapter import NixOSAdapter
from adapters.nixos.config_generator import ConfigGenerator
from adapters.nixos.vm_manager import VMManager, VMState
from adapters.nixos.nix_builder import NixBuilder, NixBuildResult
from adapters.nixos.service_module import ServiceMapper

__all__ = [
    "NixOSAdapter",
    "ConfigGenerator",
    "VMManager",
    "VMState",
    "NixBuilder",
    "NixBuildResult",
    "ServiceMapper",
]
