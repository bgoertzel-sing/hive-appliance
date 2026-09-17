"""
Tests for M3 — State Recovery (C09) and Controlled Upgrades (C10).
"""
from __future__ import annotations

import json
import os
import tempfile
import time
import unittest

from recovery.checkpoint import CheckpointManager, StateCheckpoint
from recovery.upgrade import (
    UpgradeController,
    UpgradeManifest,
    UpgradeStep,
    UpgradeResult,
)


class TestStateCheckpoint(unittest.TestCase):
    """Unit tests for the StateCheckpoint dataclass."""

    def test_round_trip(self):
        ckpt = StateCheckpoint(
            id="ckpt_test_1",
            ts=1000.0,
            label="test-label",
            appliance_state={"services": {"nginx": "running"}},
            metadata={"event_count": 42},
        )
        d = ckpt.to_dict()
        restored = StateCheckpoint.from_dict(d)
        self.assertEqual(restored.id, ckpt.id)
        self.assertEqual(restored.label, ckpt.label)
        self.assertEqual(restored.appliance_state, ckpt.appliance_state)
        self.assertEqual(restored.metadata, ckpt.metadata)

    def test_defaults(self):
        ckpt = StateCheckpoint()
        self.assertEqual(ckpt.id, "")
        self.assertIsInstance(ckpt.ts, float)
        self.assertEqual(ckpt.schema_version, "1")


class TestCheckpointManager(unittest.TestCase):
    """Unit tests for CheckpointManager CRUD operations."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.mgr = CheckpointManager(self._tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_create_and_load(self):
        ckpt = self.mgr.create({"key": "value"}, label="first")
        self.assertIn("ckpt_", ckpt.id)
        self.assertEqual(ckpt.appliance_state, {"key": "value"})

        loaded = self.mgr.load(ckpt.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.id, ckpt.id)
        self.assertEqual(loaded.appliance_state, {"key": "value"})

    def test_list_empty(self):
        self.assertEqual(self.mgr.list(), [])

    def test_list_ordering(self):
        c1 = self.mgr.create({"n": 1}, label="a")
        c2 = self.mgr.create({"n": 2}, label="b")
        c3 = self.mgr.create({"n": 3}, label="c")
        ckpts = self.mgr.list()
        self.assertEqual(len(ckpts), 3)
        self.assertEqual(ckpts[0].id, c1.id)
        self.assertEqual(ckpts[2].id, c3.id)

    def test_load_latest(self):
        self.mgr.create({"n": 1})
        latest = self.mgr.create({"n": 2}, label="latest")
        loaded = self.mgr.load_latest()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.id, latest.id)

    def test_load_latest_empty(self):
        self.assertIsNone(self.mgr.load_latest())

    def test_delete(self):
        ckpt = self.mgr.create({"x": 1})
        self.assertTrue(self.mgr.delete(ckpt.id))
        self.assertIsNone(self.mgr.load(ckpt.id))
        self.assertFalse(self.mgr.delete("nonexistent"))

    def test_prune(self):
        for i in range(7):
            self.mgr.create({"i": i})
        removed = self.mgr.prune(keep=3)
        self.assertEqual(removed, 4)
        self.assertEqual(len(self.mgr.list()), 3)

    def test_prune_no_op(self):
        self.mgr.create({"a": 1})
        removed = self.mgr.prune(keep=5)
        self.assertEqual(removed, 0)

    def test_load_nonexistent(self):
        self.assertIsNone(self.mgr.load("no_such_id"))

    def test_metadata_preserved(self):
        ckpt = self.mgr.create(
            {"s": "state"}, label="meta-test",
            metadata={"open_incidents": ["inc-1", "inc-2"]}
        )
        loaded = self.mgr.load(ckpt.id)
        self.assertEqual(loaded.metadata["open_incidents"], ["inc-1", "inc-2"])


class TestUpgradeManifest(unittest.TestCase):
    """Unit tests for UpgradeManifest and UpgradeStep."""

    def test_step_round_trip(self):
        step = UpgradeStep(verb="install", command="pip install pkg", timeout_s=30.0)
        d = step.to_dict()
        restored = UpgradeStep.from_dict(d)
        self.assertEqual(restored.verb, "install")
        self.assertEqual(restored.command, "pip install pkg")

    def test_manifest_round_trip(self):
        manifest = UpgradeManifest(
            id="upg-001",
            description="Test upgrade",
            steps=[
                UpgradeStep(verb="stop", command="systemctl stop app"),
                UpgradeStep(verb="update", command="apt update"),
            ],
        )
        d = manifest.to_dict()
        restored = UpgradeManifest.from_dict(d)
        self.assertEqual(restored.id, "upg-001")
        self.assertEqual(len(restored.steps), 2)
        self.assertEqual(restored.steps[0].verb, "stop")

    def test_manifest_from_json(self):
        j = {
            "id": "upg-json",
            "description": "from json",
            "steps": [{"verb": "echo", "command": "echo hello"}],
        }
        m = UpgradeManifest.from_dict(j)
        self.assertEqual(m.id, "upg-json")
        self.assertEqual(len(m.steps), 1)


class TestUpgradeController(unittest.TestCase):
    """Unit tests for UpgradeController."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.ckpt_mgr = CheckpointManager(self._tmpdir)
        self.ctrl = UpgradeController(self.ckpt_mgr)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_pre_flight_pass(self):
        self.ctrl.add_pre_flight(lambda: (True, "OK"))
        manifest = UpgradeManifest(id="pf-pass")
        results = self.ctrl.run_pre_flight(manifest)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0][0])

    def test_pre_flight_fail_blocks_upgrade(self):
        self.ctrl.add_pre_flight(lambda: (False, "disk full"))
        manifest = UpgradeManifest(id="pf-fail", steps=[
            UpgradeStep(verb="install"),
        ])
        result = self.ctrl.execute(manifest, {"state": "before"})
        self.assertFalse(result.success)
        self.assertIn("Pre-flight failed", result.error)
        # Should NOT have created a checkpoint
        self.assertEqual(len(self.ckpt_mgr.list()), 0)

    def test_dry_run(self):
        manifest = UpgradeManifest(id="dry-run-test", steps=[
            UpgradeStep(verb="reboot"),
        ])
        result = self.ctrl.execute(manifest, {"state": "current"}, dry_run=True)
        self.assertTrue(result.success)
        self.assertIn("dry-run", result.error)
        # Should have created a checkpoint even in dry-run
        self.assertEqual(len(self.ckpt_mgr.list()), 1)

    def test_execute_no_executor_noop(self):
        """With no executor configured, steps succeed as noop."""
        manifest = UpgradeManifest(id="noop-test", steps=[
            UpgradeStep(verb="step1"),
            UpgradeStep(verb="step2"),
        ])
        result = self.ctrl.execute(manifest, {"s": 1})
        self.assertTrue(result.success)
        self.assertEqual(result.steps_completed, 2)
        self.assertFalse(result.rolled_back)

    def test_pre_flight_exception(self):
        def bad_check():
            raise RuntimeError("boom")
        self.ctrl.add_pre_flight(bad_check)
        manifest = UpgradeManifest(id="exc-test")
        results = self.ctrl.run_pre_flight(manifest)
        self.assertFalse(results[0][0])
        self.assertIn("boom", results[0][1])

    def test_restore_checkpoint(self):
        ckpt = self.ckpt_mgr.create({"data": "important"}, label="for-restore")
        loaded = self.ctrl.restore_checkpoint(ckpt.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.appliance_state, {"data": "important"})

    def test_restore_nonexistent(self):
        self.assertIsNone(self.ctrl.restore_checkpoint("no-such-id"))


class TestUpgradeResult(unittest.TestCase):

    def test_defaults(self):
        r = UpgradeResult()
        self.assertFalse(r.success)
        self.assertFalse(r.rolled_back)
        self.assertEqual(r.steps_completed, 0)

    def test_to_dict(self):
        r = UpgradeResult(manifest_id="m1", success=True, steps_completed=3, steps_total=3)
        d = r.to_dict()
        self.assertEqual(d["manifest_id"], "m1")
        self.assertTrue(d["success"])


class TestApplianceRecoveryIntegration(unittest.TestCase):
    """Integration tests: Appliance checkpoint + restore + upgrade."""

    def _make_appliance(self):
        from controller.appliance import Appliance
        return Appliance(store_path=":memory:")

    def test_checkpoint_and_list(self):
        app = self._make_appliance()
        ckpt = app.checkpoint(label="int-test")
        self.assertIn("ckpt_", ckpt.id)
        ckpts = app.list_checkpoints()
        self.assertGreaterEqual(len(ckpts), 1)
        app.close()

    def test_checkpoint_and_restore(self):
        app = self._make_appliance()
        # Create initial state via observation
        app.observe()
        ckpt = app.checkpoint(label="before-change")

        # Make a state change
        from schemas.types import Event, EventKind, Severity
        evt = Event(
            kind=EventKind.OBSERVATION,
            source="test",
            subject="fake_service",
            payload={"active": "failed", "exists": True, "service": "fake_service"},
            severity=Severity.ERROR,
        )
        app.store.append(evt)
        app.reducer.reduce(evt)

        # Should have an incident now
        before_restore = len(app.open_incidents())
        self.assertGreater(before_restore, 0)

        # Restore
        ok = app.restore(ckpt.id)
        self.assertTrue(ok)
        app.close()

    def test_restore_nonexistent(self):
        app = self._make_appliance()
        self.assertFalse(app.restore("no-such-id"))
        app.close()

    def test_delete_checkpoint(self):
        app = self._make_appliance()
        ckpt = app.checkpoint(label="to-delete")
        self.assertTrue(app.delete_checkpoint(ckpt.id))
        self.assertFalse(app.delete_checkpoint("nope"))
        app.close()

    def test_prune_checkpoints(self):
        app = self._make_appliance()
        for i in range(6):
            app.checkpoint(label=f"p{i}")
        removed = app.prune_checkpoints(keep=2)
        self.assertEqual(removed, 4)
        self.assertEqual(len(app.list_checkpoints()), 2)
        app.close()

    def test_upgrade_dry_run(self):
        app = self._make_appliance()
        manifest = UpgradeManifest(
            id="upg-integ-dry",
            description="dry run test",
            steps=[UpgradeStep(verb="noop")],
        )
        result = app.upgrade(manifest, dry_run=True)
        self.assertTrue(result.success)
        self.assertIn("dry-run", result.error)
        app.close()

    def test_upgrade_noop_executor(self):
        app = self._make_appliance()
        manifest = UpgradeManifest(
            id="upg-integ-noop",
            description="noop executor test",
            steps=[
                UpgradeStep(verb="step-a"),
                UpgradeStep(verb="step-b"),
            ],
        )
        result = app.upgrade(manifest)
        self.assertTrue(result.success)
        self.assertEqual(result.steps_completed, 2)
        app.close()


if __name__ == "__main__":
    unittest.main()
