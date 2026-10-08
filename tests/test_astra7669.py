"""Astra 7669 (docs/ASTRA_REVIEW_7669.md, 7008f0a):
1 Med F-fence-remove-dir-fsync: committed entry whose marker removal is not
      durable gets a durable abort record (or a re-written marker) and the
      journal stays fenced in memory; a restart never applies it.
2 Med F-fence-content: fence marker carries marker_hash and must embed a valid
      entry naming the LAST journaled rebind; otherwise every rebind is fenced.
3 Med F-abort-content: abort records are hash-checked and must name an earlier
      rebind; a corrupt abort blocks replay of every earlier rebind.
"""
import json
import os

import hive.reducer as hr
from tests.test_astra7656 import S, _fail_journal_fsync_and_rollback
from tests.test_astra7638 import run


def _uncertain(tmp_path, monkeypatch):
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    _fail_journal_fsync_and_rollback(monkeypatch, jp)
    assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    monkeypatch.undo()
    assert os.path.exists(jp + ".fence")
    return jp, h


def _held(h):
    return h._plan_owner.get("a1:p") is None and h.owner_rebinds == []


# ------------------------------------------------ 1 unlink ok, dir fsync fails
def _fail_dir_fsync_after_fence_unlink(monkeypatch, jp, journal_too=False):
    st = {"s": ""}
    real_unlink, real_fsync = os.unlink, os.fsync
    real_dir = hr.HiveReducer._fsync_dir

    def unlink(p, *a, **k):
        real_unlink(p, *a, **k)
        if str(p) == jp + ".fence" and not st["s"]:
            st["s"] = "unlinked"

    def fsync_dir(p):
        if st["s"] == "unlinked":
            st["s"] = "after"
            raise OSError("EIO dir")
        return real_dir(p)

    def fsync(fd):
        if (journal_too and st["s"] == "after"
                and os.readlink(f"/proc/self/fd/{fd}") == os.path.realpath(jp)):
            raise OSError("EIO journal")
        return real_fsync(fd)

    def ftruncate(fd, n):
        raise OSError("EIO truncate")
    monkeypatch.setattr(os, "unlink", unlink)
    monkeypatch.setattr(hr.HiveReducer, "_fsync_dir", staticmethod(fsync_dir))
    if journal_too:
        monkeypatch.setattr(os, "fsync", fsync)
        monkeypatch.setattr(os, "ftruncate", ftruncate)
    return st


def test_marker_unlink_then_dir_fsync_failure_never_replays(tmp_path, monkeypatch):
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    st = _fail_dir_fsync_after_fence_unlink(monkeypatch, jp)
    assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    monkeypatch.undo()
    assert st["s"] == "after"
    ind = h.journal_status()["indeterminate"]
    assert ind is not None and ind["abort_durable"] is True
    assert _held(h)
    assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")  # fenced live
    # Astra's witness: restart must NOT apply the refused rebind
    h2 = run(S, journal=jp)
    assert _held(h2) and h2.journal_status()["indeterminate"] is None
    assert "aborted" in h2.journal_status()["unapplied"][0]["why"]
    assert h2.journal_status()["corrupt_records"] == []
    # operator clears the live fence; reissue works and replays
    assert h.clear_journal_fence(actor="op", reason="inspected")
    assert h.rebind_plan_owner("a1", "p", "i", actor="op", reason="reissue")
    h3 = run(S, journal=jp)
    assert h3._plan_owner.get("a1:p") == "i"
    assert h3.owner_rebinds[-1]["reason"] == "reissue"


def test_abort_also_fails_marker_rewritten_restart_fenced(tmp_path, monkeypatch):
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    _fail_dir_fsync_after_fence_unlink(monkeypatch, jp, journal_too=True)
    assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    monkeypatch.undo()
    ind = h.journal_status()["indeterminate"]
    assert ind["abort_durable"] is False and ind["marker_present"] is True
    assert os.path.exists(jp + ".fence")                 # marker re-written
    h2 = run(S, journal=jp)
    assert _held(h2)
    assert h2.journal_status()["indeterminate"]["found_at_startup"] is True


# ------------------------------------------------ 2 corrupt / mismatched fence marker
def test_marker_with_edited_op_id_fences_everything(tmp_path, monkeypatch):
    jp, _ = _uncertain(tmp_path, monkeypatch)
    m = json.loads(open(jp + ".fence").read())
    m["op_id"] = "someone-else"                          # hash NOT recomputed
    open(jp + ".fence", "w").write(json.dumps(m))
    h2 = run(S, journal=jp)
    assert _held(h2)
    ind = h2.journal_status()["indeterminate"]
    assert ind["marker_valid"] is False and "UNTRUSTED" in ind["error"]
    # marker holding only an unrelated op_id, no entry
    open(jp + ".fence", "w").write(json.dumps({"v": 2, "op_id": "x"}))
    assert _held(run(S, journal=jp))


def test_valid_marker_not_naming_last_entry_fences_everything(tmp_path, monkeypatch):
    jp, h = _uncertain(tmp_path, monkeypatch)
    fake = {"op": "owner_rebind", "op_id": "other", "agent_id": "a1",
            "plan_id": "p", "incident_id": "j", "actor": "op", "reason": "t"}
    fake["entry_hash"] = h._entry_hash(fake)
    open(jp + ".fence", "wb").write(h._marker_bytes(fake))   # self-consistent
    h2 = run(S, journal=jp)
    assert _held(h2)
    assert "last journaled rebind" in h2.journal_status()["indeterminate"]["error"]
    # clearing aborts the named op AND the last journaled rebind
    assert h2.clear_journal_fence(actor="op", reason="inspected")
    h3 = run(S, journal=jp)
    assert _held(h3) and h3.journal_status()["indeterminate"] is None
    assert h3.journal_status()["corrupt_records"] == []


def test_intact_marker_still_fences_only_its_entry(tmp_path, monkeypatch):
    jp, h = _uncertain(tmp_path, monkeypatch)
    h2 = run(S, journal=jp)
    ind = h2.journal_status()["indeterminate"]
    assert ind["marker_valid"] and ind["scope"] == "entry" and _held(h2)


# ------------------------------------------------ 3 corrupt abort record
def _cleared(tmp_path, monkeypatch):
    jp, h = _uncertain(tmp_path, monkeypatch)
    h2 = run(S, journal=jp)
    assert h2.clear_journal_fence(actor="op", reason="cancel")
    assert _held(run(S, journal=jp))
    return jp


def test_one_char_edit_of_abort_op_id_does_not_revive_entry(tmp_path, monkeypatch):
    jp = _cleared(tmp_path, monkeypatch)
    lines = open(jp).read().splitlines()
    ab = json.loads(lines[-1])
    assert ab["op"] == "abort_rebind"
    ab["op_id"] = ("0" if ab["op_id"][0] != "0" else "1") + ab["op_id"][1:]
    lines[-1] = json.dumps(ab, sort_keys=True)          # hash NOT recomputed
    open(jp, "w").write("\n".join(lines) + "\n")
    for _ in range(2):
        h = run(S, journal=jp)
        assert _held(h)
        assert h.journal_status()["corrupt_records"]
        assert h.journal_status()["unapplied_total"] >= 1


def test_rehashed_abort_naming_no_rebind_does_not_revive_entry(tmp_path, monkeypatch):
    jp = _cleared(tmp_path, monkeypatch)
    lines = open(jp).read().splitlines()
    ab = json.loads(lines[-1])
    ab["op_id"] = "nonexistent"
    ab["entry_hash"] = hr.HiveReducer._entry_hash(ab)    # self-consistent
    lines[-1] = json.dumps(ab, sort_keys=True)
    open(jp, "w").write("\n".join(lines) + "\n")
    h = run(S, journal=jp)
    assert _held(h)
    assert "names no earlier" in h.journal_status()["corrupt_records"][0]["why"]


def test_garbage_line_after_rebind_blocks_it_but_not_later_ones(tmp_path):
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    assert h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    with open(jp, "a") as f:
        f.write('{"op": "abort_rebind", "op_id": "zz"\n')   # unreadable line
    h2 = run(S, journal=jp)
    assert _held(h2)
    assert "may be its cancellation" in h2.journal_status()["unapplied"][0]["why"]
