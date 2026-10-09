"""Astra 7656 (docs/ASTRA_REVIEW_7656.md, 7a372c3):
1 Med  F-fence-restart: the indeterminate-write fence is a durable marker
       (<journal>.fence) written BEFORE the append; at startup it fences the
       journal (entry not replayed, rebinds refused) until clear_journal_fence().
2 Med  F-journal-content: stream hash covers event CONTENT; each entry carries
       an entry_hash; edited entries / edited events are not replayed.
3 Low  set-aside copy is fully written, fsync'd and verified before truncation.
4 Low  journal_status() reports unapplied_total / unapplied_omitted;
       journal_unapplied() returns all retained dispositions.
5 Low  MAX_HIVE_PLANS overall admission cap (fail-closed).
"""
import copy
import json
import os

import pytest

import hive.reducer as hr
from tests.test_astra7160 import PLAN, ho
from tests.test_astra7519 import INCL
from tests.test_astra7638 import BASE, run

S = BASE + [PLAN("p", "i", 1)]


def _fail_journal_fsync_and_rollback(monkeypatch, jp):
    real = os.fsync

    def jfsync(fd):
        if os.readlink(f"/proc/self/fd/{fd}") == os.path.realpath(jp):
            raise OSError("EIO")
        return real(fd)

    def boom(*a):
        raise OSError("EIO")
    monkeypatch.setattr(os, "fsync", jfsync)
    monkeypatch.setattr(os, "ftruncate", boom)


# ------------------------------------------------ 1 durable fence
def test_fence_survives_restart_and_blocks_replay(tmp_path, monkeypatch):
    # Astra 7678: no marker file; the uncertain pending record has no commit
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    _fail_journal_fsync_and_rollback(monkeypatch, jp)
    assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    monkeypatch.undo()
    assert not os.path.exists(jp + ".fence")
    st = h.journal_status()
    assert st["healthy"] is False and st["fence"]["applied"] is False
    assert '"incident_id": "i"' in open(jp).read()     # the uncertain line survived
    assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    # restart: Astra's witness -- the refused rebind must NOT apply itself
    h2 = run(S, journal=jp)
    assert h2._plan_owner.get("a1:p") is None and h2.owner_rebinds == []
    assert ho(h2) == ["i", "j"] and h2.quarantined_plans() == ["a1:p"]
    assert "no commit" in h2.journal_status()["unapplied"][0]["why"]
    with pytest.raises(ValueError):
        h.clear_journal_fence(actor="", reason="x")
    assert h.clear_journal_fence(actor="op", reason="inspected")
    assert h.journal_status()["healthy"] is True
    h3 = run(S, journal=jp)
    assert h3._plan_owner.get("a1:p") is None and h3.journal_status()["healthy"]
    # re-issued rebind works and replays
    assert h3.rebind_plan_owner("a1", "p", "i", actor="op", reason="reissue")
    h4 = run(S, journal=jp)
    assert h4._plan_owner.get("a1:p") == "i"
    assert h4.owner_rebinds[-1]["reason"] == "reissue"
    assert not h4.clear_journal_fence(actor="op", reason="nothing")


def test_crash_between_pending_and_commit_not_replayed(tmp_path):
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    assert h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    lines = open(jp).read().splitlines(keepends=True)
    assert len(lines) == 2
    open(jp, "w").write(lines[0])                      # crash before the commit
    h2 = run(S, journal=jp)
    assert h2._plan_owner.get("a1:p") is None
    assert h2.journal_status()["healthy"] is True      # a clean prefix
    assert "no commit" in h2.journal_status()["unapplied"][0]["why"]
    assert h2.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")


def test_legacy_fence_marker_fences_everything(tmp_path):
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    assert h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    open(jp + ".fence", "wb").write(b"\x00garbage")
    h2 = run(S, journal=jp)
    assert h2._plan_owner.get("a1:p") is None
    assert h2.journal_status()["fence"]["kind"] == "legacy_marker"
    assert h2.clear_journal_fence(actor="op", reason="inspected")
    assert not os.path.exists(jp + ".fence")
    h3 = run(S, journal=jp)                            # nothing re-journaled
    assert h3._plan_owner.get("a1:p") is None and h3.journal_status()["healthy"]


def test_stale_tmp_marker_is_ignored(tmp_path):
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    assert h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    open(jp + ".fence.tmp", "w").write("{}")           # never renamed into place
    h2 = run(S, journal=jp)
    assert h2._plan_owner.get("a1:p") == "i"


def test_clean_refusal_leaves_no_fence(tmp_path, monkeypatch):
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    real, n = os.fsync, []

    def jfsync(fd):
        # fail only the FIRST journal fsync (the append); the rollback's
        # truncate+fsync succeeds -> clean refusal, marker removed
        if os.readlink(f"/proc/self/fd/{fd}") == os.path.realpath(jp):
            n.append(fd)
            if len(n) == 1:
                raise OSError("EIO")
        return real(fd)
    monkeypatch.setattr(os, "fsync", jfsync)
    assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    monkeypatch.undo()
    assert not os.path.exists(jp + ".fence")
    assert h.journal_status()["healthy"] is True
    assert os.path.getsize(jp) == 0                    # rolled back
    assert len(n) == 2                                 # append fsync + rollback fsync
    assert h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    h2 = run(S, journal=jp)
    assert h2._plan_owner.get("a1:p") == "i" and len(h2.owner_rebinds) == 1


# ------------------------------------------------ 2 content tamper detection
def test_edited_journal_entry_not_replayed(tmp_path):
    jp = tmp_path / "rebinds.jsonl"
    h = run(S, journal=str(jp))
    assert h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    lines = jp.read_text().splitlines()
    e = json.loads(lines[0])
    e["incident_id"] = "j"                             # ids/position kept
    lines[0] = json.dumps(e)
    jp.write_text("\n".join(lines) + "\n")
    h2 = run(S, journal=str(jp))
    assert h2._plan_owner.get("a1:p") is None
    st = h2.journal_status()
    assert st["healthy"] is False
    assert "hash mismatch" in st["corrupt_records"][0]["why"]


def test_edited_event_content_with_same_ids_not_replayed(tmp_path):
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    assert h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    s2 = list(S)
    ev = copy.deepcopy(s2[1])                          # same event id
    ev.payload["symptom"] = "edited"
    s2[1] = ev
    h2 = run(s2, journal=jp)
    assert h2._plan_owner.get("a1:p") is None
    assert "differs" in h2.journal_status()["unapplied"][0]["why"]


# ------------------------------------------------ 3 set-aside verified
def test_torn_journal_is_never_trimmed(tmp_path):
    # Astra 7678 replaces the set-aside/truncate path: bytes are never removed
    jp = tmp_path / "rebinds.jsonl"
    h = run(S, journal=str(jp))
    jp.write_bytes(b'{"torn":')
    assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    assert jp.read_bytes() == b'{"torn":'              # no bytes lost
    assert h.journal_status()["fence"]["kind"] == "changed"
    h2 = run(S, journal=str(jp))
    assert "torn" in h2.journal_status()["fence"]["error"]
    assert jp.read_bytes() == b'{"torn":'


# ------------------------------------------------ 4 unapplied accounting
def test_unapplied_total_and_omitted_reported(tmp_path):
    jp = tmp_path / "rebinds.jsonl"
    tip = ""
    with open(jp, "w") as f:
        for k in range(201):                           # pending, never committed
            r = {"v": hr.JOURNAL_VERSION, "op": "rebind_pending", "op_id": f"o{k}",
                 "agent_id": "a1", "plan_id": "p", "incident_id": "i",
                 "actor": "op", "reason": "t", "seq": 0, "stream_digest": "",
                 "prev": tip}
            r["rec_hash"] = tip = hr.HiveReducer._rec_hash(r)
            f.write(json.dumps(r) + "\n")
    h = run(BASE, journal=str(jp))
    st = h.journal_status()
    assert st["healthy"] is True
    assert len(st["unapplied"]) == 200
    assert st["unapplied_total"] == 201 and st["unapplied_omitted"] == 1
    assert len(h.journal_unapplied()) == 201


# ------------------------------------------------ 5 overall plan cap
def test_overall_plan_cap_refuses_new_plans_fail_closed(monkeypatch):
    monkeypatch.setattr(hr, "MAX_HIVE_PLANS", 2)
    s = []
    for k in range(3):
        s += [INCL(f"i{k}"), PLAN(f"p{k}", f"i{k}", 1)]
    h = run(s)
    assert h.plans_refused_cap == 1
    assert len(h._plan_steps) == 2 and "a1:p2" not in h._plan_steps
    assert "i2" in ho(h)                               # its incident stays open
