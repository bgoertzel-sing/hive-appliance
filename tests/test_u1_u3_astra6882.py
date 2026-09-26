"""Tests for Astra re-review 6882 findings U1-U3 (durable postconditions)."""
from __future__ import annotations

import pytest

import controller.appliance as appliance_mod
from controller.appliance import (
    Appliance,
    OUTCOME_BLOCKED_NO_CHECKPOINT,
    OUTCOME_ROLLBACK_FAILED,
    OUTCOME_ROLLED_BACK,
)
from controller.reducer import Reducer
from reasoning.planner import SimplePlanner
from recovery.upgrade import UpgradeController, UpgradeManifest, UpgradeStep
from recovery.checkpoint import CheckpointManager
from schemas.types import Event, EventKind, IncidentReport, Receipt
from verifier.exit_code_verifier import ExitCodeVerifier


class RecordingFailExecutor:
    """Real (non-simulated) executor that records calls and always fails."""
    is_simulation = False
    name = "recording_fail"

    def __init__(self, on_call=None):
        self.calls = []
        self.on_call = on_call

    def execute_step(self, step, plan, step_index):
        self.calls.append((step.get("verb"), step_index))
        if self.on_call:
            self.on_call()
        return Receipt(
            plan_id=plan.id if plan is not None else "",
            step_index=step_index,
            verb=step.get("verb", ""),
            exit_code=1,
            attempt_id=getattr(plan, "attempt_id", "") if plan is not None else "",
        )


def _app(tmp_path, executor):
    app = Appliance(str(tmp_path / "events.db"))
    app.set_planner(SimplePlanner())
    app.set_executor(executor)
    app.set_verifier(ExitCodeVerifier())
    return app


def _incident(app):
    inc = IncidentReport.deterministic("svc_a", "service_down")
    ev = Event(kind=EventKind.INCIDENT, source="test", subject="svc_a",
               payload=inc.to_dict())
    app.store.append(ev)
    app.reducer.reduce(ev)
    return inc


def _recovery_events(app):
    return [e for e in app.store.query(kind=EventKind.RECOVERY)]


# ---------------------------------------------------------------- U1
def test_u1_module_logger_defined():
    assert hasattr(appliance_mod, "logger")


def test_u1_checkpoint_failure_blocks_dispatch(tmp_path, monkeypatch):
    ex = RecordingFailExecutor()
    app = _app(tmp_path, ex)
    inc = _incident(app)

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(app._checkpoint_mgr, "create", boom)

    receipts = app.repair(inc)

    assert receipts == []
    assert ex.calls == [], "executor must not be called without a checkpoint"
    assert app.repair_outcomes[inc.id] == OUTCOME_BLOCKED_NO_CHECKPOINT
    rec = _recovery_events(app)
    assert rec and rec[-1].payload["outcome"] == OUTCOME_BLOCKED_NO_CHECKPOINT
    assert "disk full" in rec[-1].payload["error"]
    # No receipts durably recorded
    assert app.store.query(kind=EventKind.RECEIPT) == []
    # Blocked repair is not marked completed -> can be retried
    assert inc.id not in app._completed_repairs
    # Durable across restart
    app2 = Appliance(str(tmp_path / "events.db"))
    assert any(e.payload.get("outcome") == OUTCOME_BLOCKED_NO_CHECKPOINT
               for e in app2.store.query(kind=EventKind.RECOVERY))


def test_u1_unreadable_checkpoint_blocks_dispatch(tmp_path, monkeypatch):
    ex = RecordingFailExecutor()
    app = _app(tmp_path, ex)
    inc = _incident(app)
    monkeypatch.setattr(app._checkpoint_mgr, "load", lambda cid: None)
    assert app.repair(inc) == []
    assert ex.calls == []
    assert app.repair_outcomes[inc.id] == OUTCOME_BLOCKED_NO_CHECKPOINT


def test_u1_failed_repair_rolls_back(tmp_path):
    app = _app(tmp_path, None)
    ex = RecordingFailExecutor(on_call=lambda: app.reducer.state.update(
        {"svc_a": {"mutated": True}}))
    app.set_executor(ex)
    inc = _incident(app)
    pre_state = app.reducer.snapshot()["state"]

    app.repair(inc)

    assert ex.calls, "repair should have been dispatched"
    assert app.repair_outcomes[inc.id] == OUTCOME_ROLLED_BACK
    assert not app.reducer.state.get("svc_a", {}).get("mutated")
    for k, v in pre_state.items():
        for kk, vv in v.items():
            assert app.reducer.state[k][kk] == vv
    rec = _recovery_events(app)[-1]
    assert rec.payload["outcome"] == OUTCOME_ROLLED_BACK
    assert rec.payload["checkpoint_id"]


def test_u1_rollback_failure_is_distinct(tmp_path, monkeypatch):
    app = _app(tmp_path, None)
    real_load = app._checkpoint_mgr.load
    state = {"n": 0}

    def load_then_vanish(cid):
        state["n"] += 1
        return real_load(cid) if state["n"] == 1 else None
    monkeypatch.setattr(app._checkpoint_mgr, "load", load_then_vanish)
    ex = RecordingFailExecutor()
    app.set_executor(ex)
    inc = _incident(app)

    app.repair(inc)

    assert ex.calls
    assert app.repair_outcomes[inc.id] == OUTCOME_ROLLBACK_FAILED
    rec = _recovery_events(app)[-1]
    assert rec.payload["outcome"] == OUTCOME_ROLLBACK_FAILED
    assert "missing" in rec.payload["error"]
    assert not inc.resolved


# ---------------------------------------------------------------- U2
def _failing_manifest():
    return UpgradeManifest(id="up1", steps=[UpgradeStep(verb="restart", command="x")])


def test_u2_no_restore_fn_is_not_rolled_back(tmp_path):
    ctrl = UpgradeController(CheckpointManager(str(tmp_path)),
                             executor=RecordingFailExecutor())
    r = ctrl.execute(_failing_manifest(), {"state": {"a": 1}})
    assert not r.success
    assert r.rolled_back is False
    assert "NOT restored" in r.rollback_error


def test_u2_restore_failure_is_not_rolled_back(tmp_path):
    ctrl = UpgradeController(CheckpointManager(str(tmp_path)),
                             executor=RecordingFailExecutor())

    def bad_restore(s):
        raise RuntimeError("nope")
    r = ctrl.execute(_failing_manifest(), {"state": {}}, restore_fn=bad_restore)
    assert r.rolled_back is False
    assert "restore failed" in r.rollback_error


def test_u2_appliance_upgrade_actually_restores(tmp_path):
    app = Appliance(str(tmp_path / "events.db"))
    inc = _incident(app)
    ex = RecordingFailExecutor(on_call=lambda: (
        app.reducer.state.update({"svc_a": {"mutated": True}}),
        app.reducer.incidents.clear(),
    ))
    app.set_executor(ex)

    r = app.upgrade(_failing_manifest())

    assert ex.calls
    assert r.rolled_back is True and r.rollback_error == ""
    assert not app.reducer.state.get("svc_a", {}).get("mutated")
    assert [i.id for i in app.reducer.incidents] == [inc.id]


# ---------------------------------------------------------------- U3
def test_u3_snapshot_roundtrips_incident_records(tmp_path):
    r = Reducer()
    inc = IncidentReport.deterministic("svc_b", "service_down")
    r.reduce(Event(kind=EventKind.INCIDENT, source="t", subject="svc_b",
                   payload=inc.to_dict()))
    mgr = CheckpointManager(str(tmp_path))
    ck = mgr.create(r.snapshot(), label="t")

    r2 = Reducer()
    r2.restore_snapshot(mgr.load(ck.id).appliance_state)

    assert [i.to_dict() for i in r2.incidents] == [i.to_dict() for i in r.incidents]
    assert inc.id in r2._seen_incident_ids
    # dedup still works after restore
    r2.reduce(Event(kind=EventKind.INCIDENT, source="t", subject="svc_b",
                    payload=inc.to_dict()))
    assert len(r2.incidents) == 1


def test_u3_legacy_lossy_snapshot_refused_without_mutation():
    r = Reducer()
    inc = IncidentReport.deterministic("svc_c", "service_down")
    r.reduce(Event(kind=EventKind.INCIDENT, source="t", subject="svc_c",
                   payload=inc.to_dict()))
    before = r.snapshot()
    with pytest.raises(ValueError):
        r.restore_snapshot({"state": {}, "incidents_total": 3, "incidents_open": 3})
    assert r.snapshot() == before
