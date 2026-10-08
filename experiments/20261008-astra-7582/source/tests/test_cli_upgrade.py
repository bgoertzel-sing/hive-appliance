"""Tests for CLI upgrade manifest parsing (pre-existing UpgradeStep(name=) mismatch)."""
from __future__ import annotations

import json
import sys

import pytest

import cli
from recovery.upgrade import UpgradeManifest


def test_legacy_cli_shape_parses():
    m = cli.manifest_from_json({"name": "x", "version": "2", "steps": [
        {"name": "s", "command": "true", "verify_command": "true"}]})
    assert isinstance(m, UpgradeManifest)
    assert m.id == "x" and m.description == "x 2"
    assert m.steps[0].verb == "s" and m.steps[0].command == "true"
    assert m.steps[0].metadata["verify_command"] == "true"


def test_canonical_roundtrip_shape_parses():
    from recovery.upgrade import UpgradeStep
    orig = UpgradeManifest(id="m1", description="d", steps=[
        UpgradeStep(verb="install", command="true", timeout_s=5.0)])
    m = cli.manifest_from_json(json.loads(json.dumps(orig.to_dict())))
    assert m.id == "m1" and m.steps[0].verb == "install" and m.steps[0].timeout_s == 5.0


@pytest.mark.parametrize("bad", [
    {}, {"steps": []}, {"steps": [{"command": "true"}]},
    {"steps": [{"verb": "v"}]}, {"steps": [{"verb": "v", "command": "c", "bogus": 1}]},
    {"steps": ["x"]}, [],
])
def test_invalid_manifest_rejected(bad):
    with pytest.raises(ValueError):
        cli.manifest_from_json(bad)


def _run(monkeypatch, capsys, argv):
    monkeypatch.setattr(sys, "argv", ["cli"] + argv)
    code = 0
    try:
        cli.main()
    except SystemExit as e:
        code = e.code
    return code, capsys.readouterr().out


def test_cmd_upgrade_end_to_end_success(tmp_path, monkeypatch, capsys):
    mf = tmp_path / "m.json"
    mf.write_text(json.dumps({"name": "up", "steps": [{"name": "noop", "command": "true"}]}))
    code, out = _run(monkeypatch, capsys, ["--store", str(tmp_path / "s.db"),
                                          "upgrade", str(mf), "--recovery-ready"])
    assert code == 0, out
    assert "SUCCESS" in out and "Steps: 1/1" in out and "Checkpoint:" in out


def test_cmd_upgrade_failure_reports_rollback(tmp_path, monkeypatch, capsys):
    mf = tmp_path / "m.json"
    mf.write_text(json.dumps({"name": "up", "steps": [{"name": "boom", "command": "false"}]}))
    code, out = _run(monkeypatch, capsys, ["--store", str(tmp_path / "s.db"),
                                          "upgrade", str(mf), "--recovery-ready"])
    assert "FAILED" in out and "Rolled back:" in out


def test_cmd_upgrade_invalid_manifest_exit2(tmp_path, monkeypatch, capsys):
    mf = tmp_path / "m.json"
    mf.write_text(json.dumps({"name": "up", "steps": [{"command": "true"}]}))
    code, out = _run(monkeypatch, capsys, ["--store", str(tmp_path / "s.db"),
                                          "upgrade", str(mf), "--recovery-ready"])
    assert code == 2 and "invalid upgrade manifest" in out


def test_cmd_upgrade_requires_recovery_ready(tmp_path, monkeypatch, capsys):
    mf = tmp_path / "m.json"
    mf.write_text("{}")
    code, out = _run(monkeypatch, capsys, ["upgrade", str(mf)])
    assert code == 1
