"""Tests for Astra 6986 / Opus 6979 re-review at 1ab8e5f: N1, N2, H2 residual, P2."""
from __future__ import annotations

from pathlib import Path

from controller.appliance import Appliance
from controller.reducer import Reducer
from hive.reducer import HiveReducer
from hive.types import AgentHealth, HiveEvent
from schemas.types import Event, EventKind, IncidentReport, Plan, Receipt
from conversation.attachments import AttachmentStore
from conversation.types import Attachment


def _lev(kind, payload):
    return Event(kind=kind, source="t", subject="svc", payload=payload)


def _local_with_plan(n=2):
    r = Reducer()
    inc = IncidentReport(component="svc", symptom="down")
    r.reduce(_lev(EventKind.INCIDENT, inc.to_dict()))
    r.reduce(_lev(EventKind.PLAN, {"id": "p1", "incident_id": inc.id,
                                   "steps": [{"verb": "v"}] * n}))
    return r, inc


# ---------------------------------------------------------------- N1
def test_n1_plan_links_unlinked_incident_locally():
    r, inc = _local_with_plan(1)
    assert r.incidents[0].plan_id == "p1"
    r.reduce(_lev(EventKind.RECEIPT, {"id": "r0", "plan_id": "p1",
                                      "step_index": 0, "verified": True}))
    assert r.open_incidents() == []


def test_n1_appliance_record_flow_resolves_without_preset_plan_id():
    app = Appliance(":memory:")
    inc = IncidentReport(component="svc", symptom="down")
    app.record_incident(inc)
    plan = Plan(incident_id=inc.id, steps=[{"verb": "restart_service"}])
    app.record_plan(plan)
    app.record_receipt(Receipt(plan_id=plan.id, step_index=0, verified=True))
    assert app.reducer.open_incidents() == []
    app.close()


def test_n1_failed_receipt_keeps_incident_open():
    r, inc = _local_with_plan(1)
    r.reduce(_lev(EventKind.RECEIPT, {"id": "r0", "plan_id": "p1",
                                      "step_index": 0, "verified": False}))
    assert [i.id for i in r.open_incidents()] == [inc.id]


# ---------------------------------------------------------------- N2
def test_n2_duplicate_step_index_does_not_complete_plan():
    r, inc = _local_with_plan(2)
    for rid in ("r0", "r0b"):
        r.reduce(_lev(EventKind.RECEIPT, {"id": rid, "plan_id": "p1",
                                          "step_index": 0, "verified": True}))
    assert [i.id for i in r.open_incidents()] == [inc.id]
    r.reduce(_lev(EventKind.RECEIPT, {"id": "r1", "plan_id": "p1",
                                      "step_index": 1, "verified": True}))
    assert r.open_incidents() == []


def test_n2_bool_negative_out_of_range_indices_rejected():
    r, inc = _local_with_plan(2)
    for rid, idx in (("a", True), ("b", False), ("c", -1), ("d", 2), ("e", "1")):
        r.reduce(_lev(EventKind.RECEIPT, {"id": rid, "plan_id": "p1",
                                          "step_index": idx, "verified": True}))
    assert [i.id for i in r.open_incidents()] == [inc.id]


def test_n2_snapshot_roundtrip_keeps_distinct_indices():
    r, inc = _local_with_plan(2)
    r.reduce(_lev(EventKind.RECEIPT, {"id": "r0", "plan_id": "p1",
                                      "step_index": 0, "verified": True}))
    r2 = Reducer()
    r2.restore_snapshot(r.snapshot())
    r2.reduce(_lev(EventKind.RECEIPT, {"id": "r0x", "plan_id": "p1",
                                       "step_index": 0, "verified": True}))
    assert len(r2.open_incidents()) == 1
    r2.reduce(_lev(EventKind.RECEIPT, {"id": "r1", "plan_id": "p1",
                                       "step_index": 1, "verified": True}))
    assert r2.open_incidents() == []


def test_local_receipt_before_plan_is_buffered_then_replayed():
    r = Reducer()
    inc = IncidentReport(component="svc", symptom="down")
    r.reduce(_lev(EventKind.INCIDENT, inc.to_dict()))
    r.reduce(_lev(EventKind.RECEIPT, {"id": "r0", "plan_id": "p1",
                                      "step_index": 0, "verified": True}))
    assert len(r.open_incidents()) == 1
    r.reduce(_lev(EventKind.PLAN, {"id": "p1", "incident_id": inc.id,
                                   "steps": [{"verb": "v"}]}))
    assert r.open_incidents() == []


# ---------------------------------------------------------------- H2 residual (hive)
def _hev(kind, payload, agent="a1"):
    return HiveEvent(source_agent=agent, original_event=_lev(kind, payload))


def _hr():
    r = HiveReducer()
    r.register_agent("a1")
    r.reduce(_hev(EventKind.INCIDENT, {"id": "inc_1", "symptom": "s",
                                       "severity": "warn", "plan_id": "p1"}))
    return r


def _hopen(r):
    return [i["incident_id"] for i in r._open_agent_incidents("a1")]


def test_h2_missing_plan_fails_closed():
    r = _hr()
    r.reduce(_hev(EventKind.RECEIPT, {"id": "rc", "verified": True, "plan_id": "p1",
                                      "incident_id": "inc_1", "step_index": 0}))
    assert _hopen(r) == ["inc_1"]
    assert r.state.agents["a1"].open_incidents == 1


def test_h2_late_plan_replays_buffered_receipts():
    r = _hr()
    r.reduce(_hev(EventKind.RECEIPT, {"id": "r0", "verified": True, "plan_id": "p1",
                                      "step_index": 0}))
    r.reduce(_hev(EventKind.RECEIPT, {"id": "r1", "verified": True, "plan_id": "p1",
                                      "step_index": 1}))
    assert _hopen(r) == ["inc_1"]
    r.reduce(_hev(EventKind.PLAN, {"id": "p1", "incident_id": "inc_1",
                                   "steps": [{"verb": "a"}, {"verb": "b"}]}))
    assert _hopen(r) == []
    assert r.state.agents["a1"].health == AgentHealth.HEALTHY


def test_h2_late_plan_with_too_few_steps_stays_open():
    r = _hr()
    r.reduce(_hev(EventKind.RECEIPT, {"id": "r0", "verified": True, "plan_id": "p1",
                                      "step_index": 0}))
    r.reduce(_hev(EventKind.PLAN, {"id": "p1", "incident_id": "inc_1",
                                   "steps": [{"verb": "a"}, {"verb": "b"}]}))
    assert _hopen(r) == ["inc_1"]


def test_h2_bool_step_index_rejected():
    r = _hr()
    r.reduce(_hev(EventKind.PLAN, {"id": "p1", "incident_id": "inc_1",
                                   "steps": [{"verb": "a"}, {"verb": "b"}]}))
    r.reduce(_hev(EventKind.RECEIPT, {"id": "r0", "verified": True, "plan_id": "p1",
                                      "step_index": 0}))
    r.reduce(_hev(EventKind.RECEIPT, {"id": "rT", "verified": True, "plan_id": "p1",
                                      "step_index": True}))
    assert _hopen(r) == ["inc_1"]


def test_local_and_hive_agree_on_same_stream():
    """N2: one event stream, both reducers, same verdict."""
    inc = IncidentReport(component="svc", symptom="down")
    stream = [
        _lev(EventKind.INCIDENT, inc.to_dict()),
        _lev(EventKind.PLAN, {"id": "p1", "incident_id": inc.id,
                              "steps": [{"verb": "a"}, {"verb": "b"}]}),
        _lev(EventKind.RECEIPT, {"id": "r0", "plan_id": "p1", "step_index": 0, "verified": True}),
        _lev(EventKind.RECEIPT, {"id": "r0b", "plan_id": "p1", "step_index": 0, "verified": True}),
    ]
    loc, hive = Reducer(), HiveReducer()
    hive.register_agent("a1")
    for e in stream:
        loc.reduce(e)
        hive.reduce(HiveEvent(source_agent="a1", original_event=e))
    assert len(loc.open_incidents()) == 1
    assert hive.state.agents["a1"].open_incidents == 1


# ---------------------------------------------------------------- P2
def _att(**kw):
    f = dict(message_id="m", venue="telegram_group", venue_id="-100",
             file_id="f", file_name="a.bin", created_at=1_700_000_000.0)
    f.update(kw)
    return Attachment(**f)


def test_p2_persists_resolved_checked_path(tmp_path):
    root = tmp_path / "files"
    (root / "sub").mkdir(parents=True)
    store = AttachmentStore(str(tmp_path / "db.sqlite"), attachments_root=str(root))
    raw = str(root / "sub" / ".." / "ok.bin")
    item = _att(local_path=raw)
    assert store.append([item]) == 1
    assert store.get(item.id).local_path == str((root / "ok.bin").resolve())


def test_p2_relative_and_dotdot_escape_rejected(tmp_path):
    root = tmp_path / "files"
    root.mkdir()
    store = AttachmentStore(str(tmp_path / "db.sqlite"), attachments_root=str(root))
    assert store.append([_att(local_path="files/x.bin")]) == 0
    assert store.append([_att(local_path=str(root / ".." / "x.bin"))]) == 0


def test_p2_symlink_inside_root_pointing_out_rejected(tmp_path):
    root = tmp_path / "files"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)
    store = AttachmentStore(str(tmp_path / "db.sqlite"), attachments_root=str(root))
    assert store.append([_att(local_path=str(root / "link" / "x.bin"))]) == 0


def test_p2_default_client_store_is_rooted(tmp_path):
    from conversation.client import ConversationStoreClient
    from conversation.store import MessageStore
    c = ConversationStoreClient(store=MessageStore(str(tmp_path / "c.db")), index=object())
    assert c.attachment_store._root_folder is not None
    assert c.attachment_store._root_folder.base_dir == c.folder_manager.base_dir
    assert c.attachment_store.append([_att(local_path=str(tmp_path / "evil.bin"))]) == 0
