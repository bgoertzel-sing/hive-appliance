"""
Tests for the NixOS VM backend adapter (M4 / C12).

Tests cover:
- ConfigGenerator: NixOS configuration generation from resources
- VMManager: VM lifecycle (mocked subprocess)
- NixBuilder: Build/eval operations (mocked subprocess)
- ServiceMapper: Resource → NixOS service mapping
- NixOSAdapter: Verb dispatch integration
- NixOSExecutor: Repair plan execution
"""
from __future__ import annotations

import json
import os
import tempfile
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ── Ensure project root is importable ──
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from schemas.types import Resource, ResourceKind, ProfileTier

from adapters.nixos.config_generator import (
    ConfigGenerator, NixServiceDef, NixPackageDef, NixFileDef,
    NixNetworkDef, _nix_escape,
)
from adapters.nixos.vm_manager import (
    VMManager, VMConfig, VMState, VMInfo,
    _validate_config, _process_alive, MAX_MEMORY_MB, MAX_VCPUS, MAX_DISK_GB,
)
from adapters.nixos.nix_builder import NixBuilder, NixBuildResult, NixEvalResult
from adapters.nixos.service_module import ServiceMapper
from adapters.nixos.adapter import NixOSAdapter, ALLOWED_VERBS
from adapters.nixos.executor import NixOSExecutor
from schemas.types import Plan, Receipt


# ════════════════════════════════════════════════════════════════════
# ConfigGenerator tests
# ════════════════════════════════════════════════════════════════════

class TestNixEscape:
    def test_basic_string(self):
        assert _nix_escape("hello") == "hello"

    def test_quotes(self):
        assert _nix_escape('say "hi"') == 'say \\"hi\\"'

    def test_backslash(self):
        assert _nix_escape("a\\b") == "a\\\\b"

    def test_interpolation(self):
        assert _nix_escape("${foo}") == "\\${foo}"

    def test_newline_tab(self):
        assert _nix_escape("a\nb\tc") == "a\\nb\\tc"

    def test_combined(self):
        s = 'path="${HOME}"\nok'
        escaped = _nix_escape(s)
        assert '\\"' in escaped
        assert "\\${" in escaped
        assert "\\n" in escaped


class TestNixServiceDef:
    def test_basic_service(self):
        svc = NixServiceDef(name="myapp", exec_start="/usr/bin/myapp")
        nix = svc.to_nix()
        assert 'systemd.services."myapp"' in nix
        assert 'ExecStart = "/usr/bin/myapp"' in nix
        assert 'Restart = "on-failure"' in nix

    def test_service_with_user_env(self):
        svc = NixServiceDef(
            name="worker",
            exec_start="/bin/worker",
            user="appuser",
            group="appgroup",
            environment={"PORT": "8080", "ENV": "prod"},
        )
        nix = svc.to_nix()
        assert 'User = "appuser"' in nix
        assert 'Group = "appgroup"' in nix
        assert '"PORT" = "8080"' in nix
        assert '"ENV" = "prod"' in nix

    def test_service_with_deps(self):
        svc = NixServiceDef(
            name="web", exec_start="/bin/web",
            after=["network.target", "postgresql.service"],
            wants=["redis.service"],
        )
        nix = svc.to_nix()
        assert '"network.target"' in nix
        assert '"postgresql.service"' in nix
        assert '"redis.service"' in nix

    def test_disabled_service(self):
        svc = NixServiceDef(name="old", exec_start="", enable=False)
        nix = svc.to_nix()
        assert "enable = false" in nix


class TestNixPackageDef:
    def test_default_attr(self):
        pkg = NixPackageDef(name="git")
        assert "pkgs.git" in pkg.to_nix()

    def test_custom_attr(self):
        pkg = NixPackageDef(name="pg", nixpkgs_attr="pkgs.postgresql_15")
        assert "pkgs.postgresql_15" in pkg.to_nix()


class TestNixFileDef:
    def test_inline_content(self):
        f = NixFileDef(dest_path="myapp/config.json", content='{"key": "val"}')
        nix = f.to_nix()
        assert "environment.etc" in nix
        assert "myapp-config-json" in nix  # safe name
        assert "0644" in nix

    def test_source_path(self):
        f = NixFileDef(dest_path="certs/ca.pem", source_path="./ca.pem")
        nix = f.to_nix()
        assert "source = ./ca.pem" in nix


class TestNixNetworkDef:
    def test_hostname(self):
        net = NixNetworkDef(hostname="hive-01")
        nix = net.to_nix()
        assert 'networking.hostName = "hive-01"' in nix

    def test_firewall(self):
        net = NixNetworkDef(firewall_allowed_tcp=[22, 80, 443])
        nix = net.to_nix()
        assert "allowedTCPPorts" in nix
        assert "22" in nix and "443" in nix

    def test_interface(self):
        net = NixNetworkDef(interfaces={"eth0": {"address": "10.0.0.5", "prefix": 24}})
        nix = net.to_nix()
        assert "10.0.0.5" in nix
        assert "prefixLength = 24" in nix

    def test_empty(self):
        net = NixNetworkDef()
        assert net.to_nix() == ""


class TestConfigGenerator:
    def test_empty_config(self):
        gen = ConfigGenerator(hostname="test-node")
        config = gen.generate()
        assert "{ config, pkgs, lib, ... }:" in config
        assert "system.stateVersion" in config
        assert 'networking.hostName = "test-node"' in config
        assert "services.openssh.enable = true" in config

    def test_with_services_and_packages(self):
        gen = ConfigGenerator(hostname="prod-node")
        gen.add_service(NixServiceDef(name="web", exec_start="/bin/web"))
        gen.add_package(NixPackageDef(name="curl"))
        config = gen.generate()
        assert 'systemd.services."web"' in config
        assert "curl" in config

    def test_add_resource_service(self):
        gen = ConfigGenerator()
        r = Resource(name="myapp", kind=ResourceKind.SERVICE,
                     attributes={"exec_start": "/bin/myapp", "user": "app"})
        gen.add_resource(r)
        config = gen.generate()
        assert "myapp" in config
        assert 'User = "app"' in config

    def test_add_resource_package(self):
        gen = ConfigGenerator()
        r = Resource(name="vim", kind=ResourceKind.PACKAGE, attributes={})
        gen.add_resource(r)
        config = gen.generate()
        assert "vim" in config

    def test_add_resource_file(self):
        gen = ConfigGenerator()
        r = Resource(name="app.conf", kind=ResourceKind.FILE,
                     attributes={"dest_path": "app/config", "content": "key=val"})
        gen.add_resource(r)
        config = gen.generate()
        assert "environment.etc" in config

    def test_add_resource_network(self):
        gen = ConfigGenerator()
        r = Resource(name="net", kind=ResourceKind.NETWORK,
                     attributes={"hostname": "my-host", "firewall_tcp": [22, 443]})
        gen.add_resource(r)
        config = gen.generate()
        assert 'networking.hostName = "my-host"' in config
        assert "allowedTCPPorts" in config

    def test_generate_flake(self):
        gen = ConfigGenerator(hostname="flake-test")
        flake = gen.generate_flake()
        assert "flake-test" in flake
        assert "nixpkgs" in flake
        assert "nixosConfigurations" in flake
        assert "configuration.nix" in flake

    def test_extra_module(self):
        gen = ConfigGenerator()
        gen.add_extra_module('services.tailscale.enable = true;')
        config = gen.generate()
        assert "tailscale" in config


# ════════════════════════════════════════════════════════════════════
# VMManager tests
# ════════════════════════════════════════════════════════════════════

class TestVMConfig:
    def test_roundtrip(self):
        cfg = VMConfig(name="test-vm", memory_mb=4096, vcpus=4, disk_size_gb=50)
        d = cfg.to_dict()
        cfg2 = VMConfig.from_dict(d)
        assert cfg2.name == "test-vm"
        assert cfg2.memory_mb == 4096
        assert cfg2.vcpus == 4
        assert cfg2.disk_size_gb == 50


class TestValidateConfig:
    def test_valid(self):
        _validate_config(VMConfig(name="ok-vm"))  # Should not raise

    def test_empty_name(self):
        with pytest.raises(ValueError, match="name is required"):
            _validate_config(VMConfig(name=""))

    def test_bad_name(self):
        with pytest.raises(ValueError, match="alphanumeric"):
            _validate_config(VMConfig(name="bad vm!"))

    def test_memory_zero(self):
        with pytest.raises(ValueError, match="Memory"):
            _validate_config(VMConfig(name="x", memory_mb=0))

    def test_memory_over_limit(self):
        with pytest.raises(ValueError, match="Memory"):
            _validate_config(VMConfig(name="x", memory_mb=MAX_MEMORY_MB + 1))

    def test_vcpus_over_limit(self):
        with pytest.raises(ValueError, match="vCPUs"):
            _validate_config(VMConfig(name="x", vcpus=MAX_VCPUS + 1))

    def test_disk_over_limit(self):
        with pytest.raises(ValueError, match="Disk"):
            _validate_config(VMConfig(name="x", disk_size_gb=MAX_DISK_GB + 1))


class TestVMManager:
    @pytest.fixture
    def vm_mgr(self, tmp_path):
        mgr = VMManager(state_dir=str(tmp_path / "vms"))
        # Mock _run_cmd to avoid actual subprocess calls
        mgr._run_cmd = MagicMock(return_value=MagicMock(
            returncode=0, stdout="", stderr=""
        ))
        return mgr

    def test_create_vm(self, vm_mgr):
        info = vm_mgr.create(VMConfig(name="test-vm"))
        assert info.name == "test-vm"
        assert info.state == VMState.STOPPED
        # Check that qemu-img create was called
        vm_mgr._run_cmd.assert_called_once()
        call_args = vm_mgr._run_cmd.call_args[0][0]
        assert "qemu-img" in call_args
        assert "create" in call_args

    def test_create_duplicate_fails(self, vm_mgr):
        vm_mgr.create(VMConfig(name="dup-vm"))
        with pytest.raises(ValueError, match="already exists"):
            vm_mgr.create(VMConfig(name="dup-vm"))

    def test_list_vms_empty(self, vm_mgr):
        assert vm_mgr.list_vms() == []

    def test_list_vms_after_create(self, vm_mgr):
        vm_mgr.create(VMConfig(name="vm1"))
        vm_mgr.create(VMConfig(name="vm2"))
        vms = vm_mgr.list_vms()
        assert len(vms) == 2
        names = {v.name for v in vms}
        assert names == {"vm1", "vm2"}

    def test_status_unknown(self, vm_mgr):
        info = vm_mgr.status("nonexistent")
        assert info.state == VMState.UNKNOWN

    def test_status_stopped(self, vm_mgr):
        vm_mgr.create(VMConfig(name="stopped-vm"))
        info = vm_mgr.status("stopped-vm")
        assert info.state == VMState.STOPPED

    def test_destroy(self, vm_mgr):
        vm_mgr.create(VMConfig(name="doomed"))
        result = vm_mgr.destroy("doomed")
        assert result["destroyed"] is True
        assert vm_mgr.list_vms() == []

    def test_snapshot(self, vm_mgr):
        vm_mgr.create(VMConfig(name="snap-vm"))
        result = vm_mgr.snapshot("snap-vm", "snap1")
        assert result["success"] is True
        snaps = vm_mgr.list_snapshots("snap-vm")
        assert len(snaps) == 1
        assert snaps[0]["name"] == "snap1"

    def test_restore_while_running_fails(self, vm_mgr):
        vm_mgr.create(VMConfig(name="running-vm"))
        # Simulate a running VM by writing a PID file with our own PID
        pid_path = vm_mgr._pid_path("running-vm")
        pid_path.write_text(str(os.getpid()))
        with pytest.raises(RuntimeError, match="must be stopped"):
            vm_mgr.restore_snapshot("running-vm", "snap1")

    def test_config_roundtrip(self, vm_mgr):
        cfg = VMConfig(name="rt-vm", memory_mb=4096, vcpus=4)
        vm_mgr.create(cfg)
        loaded = vm_mgr._load_config("rt-vm")
        assert loaded.memory_mb == 4096
        assert loaded.vcpus == 4

    def test_load_config_missing(self, vm_mgr):
        with pytest.raises(FileNotFoundError):
            vm_mgr._load_config("no-such-vm")

    def test_build_qemu_cmd(self, vm_mgr):
        cfg = VMConfig(
            name="cmd-vm",
            memory_mb=2048, vcpus=2,
            disk_image_path="/tmp/disk.qcow2",
            ssh_port_forward=2222,
        )
        cmd = vm_mgr._build_qemu_cmd(cfg)
        assert "-m" in cmd
        assert "2048" in cmd
        assert "-smp" in cmd
        assert "2" in cmd
        assert any("disk.qcow2" in c for c in cmd)
        assert any("2222" in c for c in cmd)

    def test_vm_info_to_dict(self):
        info = VMInfo(name="test", state=VMState.RUNNING, pid=1234, snapshots=["s1"])
        d = info.to_dict()
        assert d["state"] == "running"
        assert d["pid"] == 1234
        assert d["snapshots"] == ["s1"]


# ════════════════════════════════════════════════════════════════════
# NixBuilder tests
# ════════════════════════════════════════════════════════════════════

class TestNixBuilder:
    @pytest.fixture
    def builder(self):
        b = NixBuilder()
        b._run_cmd = MagicMock()
        return b

    def test_is_available_true(self, builder):
        builder._run_cmd.return_value = MagicMock(returncode=0, stdout="nix 2.18.1")
        assert builder.is_available() is True

    def test_is_available_false(self, builder):
        builder._run_cmd.side_effect = FileNotFoundError()
        assert builder.is_available() is False

    def test_nix_version(self, builder):
        builder._run_cmd.return_value = MagicMock(returncode=0, stdout="nix (Nix) 2.18.1\n")
        assert "2.18.1" in builder.nix_version()

    def test_build_flake_success(self, builder):
        builder._run_cmd.return_value = MagicMock(
            returncode=0, stdout="/nix/store/abc-system\n", stderr=""
        )
        result = builder.build_flake("/tmp/flake")
        assert result.success is True

    def test_build_flake_failure(self, builder):
        builder._run_cmd.return_value = MagicMock(
            returncode=1, stdout="", stderr="error: flake not found"
        )
        result = builder.build_flake("/tmp/flake")
        assert result.success is False

    def test_build_legacy_success(self, builder):
        builder._run_cmd.return_value = MagicMock(
            returncode=0, stdout="/nix/store/xyz-result\n", stderr=""
        )
        result = builder.build_legacy("/tmp/default.nix")
        assert result.success is True
        assert "/nix/store/xyz-result" in result.out_path

    def test_eval_expr_json(self, builder):
        builder._run_cmd.return_value = MagicMock(
            returncode=0, stdout='{"a": 1}', stderr=""
        )
        result = builder.eval_expr("{ a = 1; }")
        assert result.success is True
        assert result.value == {"a": 1}

    def test_eval_expr_failure(self, builder):
        builder._run_cmd.return_value = MagicMock(
            returncode=1, stdout="", stderr="error: syntax error"
        )
        result = builder.eval_expr("bad {")
        assert result.success is False

    def test_nixos_rebuild_valid_actions(self, builder):
        builder._run_cmd.return_value = MagicMock(returncode=0, stdout="", stderr="")
        for action in ["switch", "boot", "test", "dry-activate", "build", "dry-build"]:
            result = builder.nixos_rebuild("/cfg", action=action)
            assert result.success is True

    def test_nixos_rebuild_invalid_action(self, builder):
        with pytest.raises(ValueError, match="Invalid"):
            builder.nixos_rebuild("/cfg", action="destroy")

    def test_collect_garbage(self, builder):
        builder._run_cmd.return_value = MagicMock(
            returncode=0, stdout="3 store paths deleted\n", stderr=""
        )
        result = builder.collect_garbage(older_than="7d")
        assert result.success is True

    def test_build_result_to_dict(self):
        r = NixBuildResult(success=True, out_path="/nix/store/x", exit_code=0)
        d = r.to_dict()
        assert d["success"] is True
        assert d["out_path"] == "/nix/store/x"

    def test_eval_result_to_dict(self):
        r = NixEvalResult(success=True, value=42)
        d = r.to_dict()
        assert d["value"] == 42


# ════════════════════════════════════════════════════════════════════
# ServiceMapper tests
# ════════════════════════════════════════════════════════════════════

class TestServiceMapper:
    def test_map_generic_service(self):
        mapper = ServiceMapper()
        r = Resource(name="myapp", kind=ResourceKind.SERVICE,
                     attributes={"exec_start": "/bin/myapp"})
        svc, pkg = mapper.map_resource(r)
        assert svc is not None
        assert svc.name == "myapp"
        assert svc.exec_start == "/bin/myapp"
        assert pkg is None  # no known template

    def test_map_known_service_nginx(self):
        mapper = ServiceMapper()
        r = Resource(name="nginx", kind=ResourceKind.SERVICE, attributes={})
        svc, pkg = mapper.map_resource(r)
        assert svc is not None
        assert "nginx" in svc.exec_start
        assert pkg is not None
        assert "nginx" in pkg.nixpkgs_attr

    def test_map_known_service_postgresql(self):
        mapper = ServiceMapper()
        r = Resource(name="postgresql", kind=ResourceKind.SERVICE, attributes={})
        svc, pkg = mapper.map_resource(r)
        assert svc.user == "postgres"
        assert pkg is not None

    def test_map_package(self):
        mapper = ServiceMapper()
        r = Resource(name="curl", kind=ResourceKind.PACKAGE, attributes={})
        svc, pkg = mapper.map_resource(r)
        assert svc is None
        assert pkg is not None
        assert "curl" in pkg.nixpkgs_attr

    def test_map_unknown_kind(self):
        mapper = ServiceMapper()
        r = Resource(name="vol", kind=ResourceKind.VOLUME, attributes={})
        svc, pkg = mapper.map_resource(r)
        assert svc is None
        assert pkg is None

    def test_map_resources_multiple(self):
        mapper = ServiceMapper()
        resources = [
            Resource(name="web", kind=ResourceKind.SERVICE,
                     attributes={"exec_start": "/bin/web"}),
            Resource(name="git", kind=ResourceKind.PACKAGE, attributes={}),
        ]
        services, packages = mapper.map_resources(resources)
        assert len(services) == 1
        assert len(packages) == 1

    def test_custom_template(self):
        mapper = ServiceMapper()
        mapper.register_template("custom", {
            "exec_start": "/opt/custom/run",
            "user": "custom",
            "nixpkgs": "customPkg",
        })
        r = Resource(name="custom", kind=ResourceKind.SERVICE, attributes={})
        svc, pkg = mapper.map_resource(r)
        assert svc.exec_start == "/opt/custom/run"
        assert svc.user == "custom"
        assert pkg is not None


# ════════════════════════════════════════════════════════════════════
# NixOSAdapter integration tests
# ════════════════════════════════════════════════════════════════════

class TestNixOSAdapter:
    @pytest.fixture
    def adapter(self, tmp_path):
        a = NixOSAdapter(
            state_dir=str(tmp_path / "nixos-state"),
            hostname="test-node",
        )
        # Mock subprocess calls in sub-components
        a._vm_manager._run_cmd = MagicMock(return_value=MagicMock(
            returncode=0, stdout="", stderr=""
        ))
        a._nix_builder._run_cmd = MagicMock(return_value=MagicMock(
            returncode=0, stdout="", stderr=""
        ))
        return a

    def test_allowed_verbs(self, adapter):
        assert "nix-generate" in adapter.allowed_verbs
        assert "vm-create" in adapter.allowed_verbs
        assert "status" in adapter.allowed_verbs

    def test_unknown_verb_raises(self, adapter):
        with pytest.raises(ValueError, match="Unknown verb"):
            adapter.dispatch("bogus-verb")

    def test_nix_generate(self, adapter):
        result = adapter.dispatch("nix-generate")
        assert result["ok"] is True
        assert "config_path" in result
        # File should exist
        assert os.path.exists(result["config_path"])

    def test_nix_generate_with_resources(self, adapter):
        resources = [
            Resource(name="web", kind=ResourceKind.SERVICE,
                     attributes={"exec_start": "/bin/web"}),
        ]
        result = adapter.dispatch("nix-generate", resources=resources)
        assert result["ok"] is True

    def test_nix_status(self, adapter):
        result = adapter.dispatch("nix-status")
        assert result["ok"] is True
        assert "nix_available" in result

    def test_nix_eval_no_expr(self, adapter):
        result = adapter.dispatch("nix-eval")
        assert result["ok"] is False

    def test_vm_create(self, adapter):
        result = adapter.dispatch("vm-create", name="test-vm")
        assert result["ok"] is True
        assert result["state"] == "stopped"

    def test_vm_create_no_name(self, adapter):
        result = adapter.dispatch("vm-create")
        assert result["ok"] is False

    def test_vm_list_empty(self, adapter):
        result = adapter.dispatch("vm-list")
        assert result["ok"] is True
        assert result["vms"] == []

    def test_vm_lifecycle(self, adapter):
        # Create
        adapter.dispatch("vm-create", name="lifecycle-vm")
        # Status
        result = adapter.dispatch("vm-status", name="lifecycle-vm")
        assert result["state"] == "stopped"
        # Destroy
        result = adapter.dispatch("vm-destroy", name="lifecycle-vm")
        assert result["ok"] is True
        assert result["destroyed"] is True

    def test_vm_snapshot(self, adapter):
        adapter.dispatch("vm-create", name="snap-vm")
        result = adapter.dispatch("vm-snapshot", name="snap-vm", snapshot_name="s1")
        assert result["ok"] is True

    def test_status(self, adapter):
        result = adapter.dispatch("status")
        assert result["ok"] is True
        assert result["adapter"] == "NixOSAdapter"
        assert result["hostname"] == "test-node"

    def test_map_resources_empty(self, adapter):
        result = adapter.dispatch("map-resources")
        assert result["ok"] is True
        assert result["services"] == []

    def test_nix_build(self, adapter):
        result = adapter.dispatch("nix-build")
        assert "ok" in result  # May fail without real Nix, but handler runs

    def test_nix_gc(self, adapter):
        result = adapter.dispatch("nix-gc", older_than="7d")
        assert "ok" in result


# ════════════════════════════════════════════════════════════════════
# NixOSExecutor tests
# ════════════════════════════════════════════════════════════════════

class TestNixOSExecutor:
    @pytest.fixture
    def executor(self, tmp_path):
        config_dir = str(tmp_path / "nixos-config")
        os.makedirs(config_dir, exist_ok=True)
        nix_builder = NixBuilder()
        nix_builder._run_cmd = MagicMock(return_value=MagicMock(
            returncode=0, stdout="", stderr=""
        ))
        return NixOSExecutor(
            config_dir=config_dir,
            nix_builder=nix_builder,
            dry_run=True,
        )

    def _make_plan(self):
        return Plan(
            steps=[],
        )

    def test_executor_name(self, executor):
        assert executor.name == "nixos"
        assert executor.is_simulation is False

    def test_restart_dry_run(self, executor):
        step = {"verb": "restart", "target": "myapp"}
        receipt = executor.execute_step(step, self._make_plan(), 0)
        assert receipt.exit_code == 0
        assert "[dry-run]" in receipt.stdout

    def test_enable_dry_run(self, executor):
        step = {"verb": "enable", "target": "web"}
        receipt = executor.execute_step(step, self._make_plan(), 0)
        assert receipt.exit_code == 0
        assert "[dry-run]" in receipt.stdout
        assert len(executor.get_pending_changes()) == 1

    def test_disable_dry_run(self, executor):
        step = {"verb": "disable", "target": "old-service"}
        receipt = executor.execute_step(step, self._make_plan(), 0)
        assert receipt.exit_code == 0
        assert "[dry-run]" in receipt.stdout

    def test_generic_verb_dry_run(self, executor):
        step = {"verb": "check", "target": "system"}
        receipt = executor.execute_step(step, self._make_plan(), 0)
        assert receipt.exit_code == 0

    def test_clear_pending(self, executor):
        step = {"verb": "enable", "target": "svc"}
        executor.execute_step(step, self._make_plan(), 0)
        assert len(executor.get_pending_changes()) == 1
        executor.clear_pending()
        assert len(executor.get_pending_changes()) == 0

    def test_invalid_verb_rejected(self, executor):
        step = {"verb": "DEFINITELY_NOT_ALLOWED_99", "target": "x"}
        receipt = executor.execute_step(step, self._make_plan(), 0)
        assert receipt.exit_code == 1
        assert "not in ALLOWED_VERBS" in receipt.stderr


# ════════════════════════════════════════════════════════════════════
# ProfileTier.NIXOS existence test
# ════════════════════════════════════════════════════════════════════

class TestProfileTierNixOS:
    def test_nixos_tier_exists(self):
        assert hasattr(ProfileTier, "NIXOS")
        assert ProfileTier.NIXOS.value  # has a non-empty value
