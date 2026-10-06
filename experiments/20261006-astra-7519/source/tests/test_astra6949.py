"""Tests for Astra re-review 6949 PARTIAL findings: H2, U2, P2-store."""
from __future__ import annotations

from hive.reducer import HiveReducer
from hive.types import AgentHealth, HiveEvent
from schemas.types import Event, EventKind, Receipt
from recovery.upgrade import UpgradeController, UpgradeManifest, UpgradeStep
from recovery.checkpoint import CheckpointManager
from conversation.attachments import AttachmentStore, DownloadStatus
from conversation.types import Attachment


# ---------------------------------------------------------------- H2
def _ev(agent, kind, payload):
    return HiveEvent(source_agent=agent, original_event=Event(
        kind=kind, source="t", subject="svc", payload=payload))


def _r():
    r = HiveReducer()
    r.register_agent("a1")
    return r


def _open(r):
    return [i["incident_id"] for i in r._open_agent_incidents("a1")]


def test_h2_untargeted_receipt_resolves_nothing():
    r = _r()
    r.reduce(_ev("a1", EventKind.INCIDENT, {"id": "inc_1", "symptom": "s", "severity": "warn"}))
    r.reduce(_ev("a1", EventKind.INCIDENT, {"id": "inc_2", "symptom": "s", "severity": "warn"}))
    r.reduce(_ev("a1", EventKind.RECEIPT, {"id": "rc", "verified": True}))
    assert _open(r) == ["inc_1", "inc_2"]
    assert r.state.agents["a1"].open_incidents == 2


def test_h2_composite_plan_requires_every_step():
    r = _r()
    r.reduce(_ev("a1", EventKind.INCIDENT, {"id": "inc_1", "symptom": "s", "severity": "warn"}))
    r.reduce(_ev("a1", EventKind.PLAN, {"id": "p1", "incident_id": "inc_1",
                                        "steps": [{"verb": "a"}, {"verb": "b"}]}))
    r.reduce(_ev("a1", EventKind.RECEIPT, {"id": "r0", "verified": True,
                                           "plan_id": "p1", "step_index": 0}))
    assert _open(r) == ["inc_1"]
    assert r.state.agents["a1"].health == AgentHealth.DEGRADED
    # replaying step 0 under a new receipt id must not count as step 1
    r.reduce(_ev("a1", EventKind.RECEIPT, {"id": "r0b", "verified": True,
                                           "plan_id": "p1", "step_index": 0}))
    assert _open(r) == ["inc_1"]
    r.reduce(_ev("a1", EventKind.RECEIPT, {"id": "r1", "verified": True,
                                           "plan_id": "p1", "step_index": 1}))
    assert _open(r) == []
    assert r.state.agents["a1"].open_incidents == 0


def test_h2_failed_step_blocks_resolution():
    r = _r()
    r.reduce(_ev("a1", EventKind.INCIDENT, {"id": "inc_1", "symptom": "s", "severity": "warn"}))
    r.reduce(_ev("a1", EventKind.PLAN, {"id": "p1", "incident_id": "inc_1",
                                        "steps": [{"verb": "a"}, {"verb": "b"}]}))
    r.reduce(_ev("a1", EventKind.RECEIPT, {"id": "r0", "verified": False,
                                           "plan_id": "p1", "step_index": 0}))
    r.reduce(_ev("a1", EventKind.RECEIPT, {"id": "r1", "verified": True,
                                           "plan_id": "p1", "step_index": 1}))
    assert _open(r) == ["inc_1"]


def test_h2_contradictory_identity_rejected():
    r = _r()
    r.reduce(_ev("a1", EventKind.INCIDENT, {"id": "inc_1", "symptom": "s",
                                            "severity": "warn", "plan_id": "p1"}))
    r.reduce(_ev("a1", EventKind.RECEIPT, {"id": "rc", "verified": True,
                                           "incident_id": "inc_1", "plan_id": "pX"}))
    assert _open(r) == ["inc_1"]


# ---------------------------------------------------------------- U2
class CmdExecutor:
    """Real executor double: fails commands equal to 'fail' (or in fail_set)."""
    is_simulation = False
    name = "cmd"

    def __init__(self, fail_set=("fail",)):
        self.commands = []
        self.fail_set = set(fail_set)

    def execute_step(self, step, plan, step_index):
        cmd = step.get("command", "")
        self.commands.append(cmd)
        return Receipt(plan_id=plan.id if plan is not None else "",
                       step_index=step_index, verb=step.get("verb", ""),
                       exit_code=1 if cmd in self.fail_set else 0,
                       attempt_id=getattr(plan, "attempt_id", "") if plan else "")


def _manifest(rb_b="undoB"):
    return UpgradeManifest(id="up", steps=[
        UpgradeStep(verb="a", command="doA", rollback_command="undoA"),
        UpgradeStep(verb="b", command="fail", rollback_command=rb_b),
    ])


def test_u2_rollback_commands_run_in_reverse_and_count(tmp_path):
    ex = CmdExecutor()
    restored = []
    ctrl = UpgradeController(CheckpointManager(str(tmp_path)), executor=ex)
    r = ctrl.execute(_manifest(), {"state": {"a": 1}}, restore_fn=restored.append)
    assert not r.success
    assert ex.commands == ["doA", "fail", "undoB", "undoA"]
    assert r.metadata_restored is True and r.actions_rolled_back is True
    assert r.rolled_back is True and restored


def test_u2_failed_rollback_command_is_not_rolled_back(tmp_path):
    ex = CmdExecutor(fail_set=("fail", "undoA"))
    ctrl = UpgradeController(CheckpointManager(str(tmp_path)), executor=ex)
    r = ctrl.execute(_manifest(), {"state": {}}, restore_fn=lambda s: None)
    assert r.metadata_restored is True
    assert r.actions_rolled_back is False and r.rolled_back is False
    assert "rollback_command failed" in r.rollback_error


def test_u2_missing_rollback_command_is_not_rolled_back(tmp_path):
    ex = CmdExecutor()
    ctrl = UpgradeController(CheckpointManager(str(tmp_path)), executor=ex)
    r = ctrl.execute(_manifest(rb_b=""), {"state": {}}, restore_fn=lambda s: None)
    assert r.rolled_back is False
    assert "no rollback_command" in r.rollback_error
    assert ex.commands == ["doA", "fail", "undoA"]


# ---------------------------------------------------------------- P2-store
def _att(**kw):
    f = dict(message_id="m", venue="telegram_group", venue_id="-100",
             file_id="f", file_name="a.bin", created_at=1_700_000_000.0)
    f.update(kw)
    return Attachment(**f)


def _store(tmp_path):
    root = tmp_path / "files"
    root.mkdir()
    return root, AttachmentStore(str(tmp_path / "db.sqlite"), attachments_root=str(root))


def test_p2_append_rejects_external_path(tmp_path):
    root, store = _store(tmp_path)
    item = _att(local_path=str(tmp_path / "outside.bin"))
    assert store.append([item]) == 0
    assert store.get(item.id) is None


def test_p2_update_status_rejects_external_path(tmp_path):
    root, store = _store(tmp_path)
    item = _att()
    assert store.append([item]) == 1
    ext = str(tmp_path / "outside.bin")
    assert store.update_status(item.id, DownloadStatus.COMPLETED, local_path=ext) is False
    assert store.get(item.id).local_path != ext


def test_p2_finish_attempt_rejects_external_path(tmp_path):
    root, store = _store(tmp_path)
    item = _att()
    store.append([item])
    claimed = store.claim_pending(1)[0]
    ext = str(tmp_path / "outside.bin")
    assert store.finish_attempt(item.id, claimed.attempt_id, DownloadStatus.COMPLETED,
                                local_path=ext) is False
    assert store.get(item.id).local_path != ext
    inside = root / "ok.bin"
    inside.write_bytes(b"x")
    assert store.finish_attempt(item.id, claimed.attempt_id, DownloadStatus.COMPLETED,
                                local_path=str(inside)) is True
    assert store.get(item.id).local_path == str(inside)
