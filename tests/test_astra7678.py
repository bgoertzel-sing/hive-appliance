"""Astra 7678 (docs/ASTRA_REVIEW_7678.md, d1239f9): commit-record journal.
Each rebind is a hashed, chained "rebind_pending" record followed by a
"rebind_commit" record; only committed rebinds replay.  Any unverifiable
record fences the WHOLE journal (unhealthy, rebinds refused).
1 Med torn final newline of the record that decides the outcome
2 Med every durability step after the entry fails
3 Med reordered records
"""
import json
import os

import hive.reducer as hr
from tests.test_astra7160 import ho
from tests.test_astra7638 import run
from tests.test_astra7656 import S, _fail_journal_fsync_and_rollback


def _held(h):
    return h._plan_owner.get("a1:p") is None and h.owner_rebinds == []


def _lines(jp):
    return open(jp, "rb").read().splitlines(keepends=True)


# ------------------------------------------------ 1 torn final newline
def test_commit_record_missing_final_newline_fences_whole_journal(tmp_path):
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    assert h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    data = open(jp, "rb").read()
    open(jp, "wb").write(data[:-1])                    # drop only the final "\n"
    for _ in range(2):                                 # never trimmed: stays fenced
        h2 = run(S, journal=jp)
        st = h2.journal_status()
        assert _held(h2) and st["healthy"] is False
        assert "torn" in st["fence"]["error"]
        assert not h2.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    assert open(jp, "rb").read() == data[:-1]


def test_refused_rebind_with_torn_tail_never_revives(tmp_path, monkeypatch):
    # a cleanly refused rebind (commit rolled back) followed by a torn line
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    real, n = os.fsync, []

    def second_fails(fd):
        if os.readlink(f"/proc/self/fd/{fd}") == os.path.realpath(jp):
            n.append(fd)
            if len(n) == 2:                            # the commit's fsync
                raise OSError("EIO")
        return real(fd)
    monkeypatch.setattr(os, "fsync", second_fails)
    assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    monkeypatch.undo()
    assert h.journal_status()["healthy"] is True and _held(h)
    assert len(_lines(jp)) == 1                        # pending only, rolled back
    h2 = run(S, journal=jp)
    assert _held(h2) and "no commit" in h2.journal_status()["unapplied"][0]["why"]
    with open(jp, "ab") as f:
        f.write(_lines(jp)[0][:-1])                    # forged, torn copy
    assert _held(run(S, journal=jp))


# ------------------------------------------------ 2 all later steps fail
def test_pending_write_and_rollback_fail_refused_and_never_replayed(tmp_path, monkeypatch):
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    _fail_journal_fsync_and_rollback(monkeypatch, jp)
    assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    monkeypatch.undo()
    st = h.journal_status()
    assert st["healthy"] is False and st["fence"]["applied"] is False and _held(h)
    assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    assert _held(run(S, journal=jp))                   # no commit -> never replays
    # even a torn copy of the pending line cannot revive it
    d = open(jp, "rb").read()
    open(jp, "wb").write(d[:-5])
    assert _held(run(S, journal=jp))


def test_commit_write_and_rollback_fail_is_applied_not_refused(tmp_path, monkeypatch):
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    real, n = os.fsync, []

    def commit_fails(fd):
        if os.readlink(f"/proc/self/fd/{fd}") == os.path.realpath(jp):
            n.append(fd)
            if len(n) >= 2:
                raise OSError("EIO")
        return real(fd)

    def boom(*a):
        raise OSError("EIO")
    monkeypatch.setattr(os, "fsync", commit_fails)
    monkeypatch.setattr(os, "ftruncate", boom)
    # never a refusal that a restart could contradict
    assert h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    monkeypatch.undo()
    st = h.journal_status()
    assert h._plan_owner.get("a1:p") == "i"
    assert st["healthy"] is False and st["fence"]["kind"] == "commit_uncertain"
    assert st["fence"]["applied"] is True
    assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="again")
    data = open(jp, "rb").read()
    # restart outcome A: the commit survived -> replayed (matches live state)
    h2 = run(S, journal=jp)
    assert h2._plan_owner.get("a1:p") == "i" and h2.journal_status()["healthy"]
    # restart outcome B: the commit was lost -> plan held, never a phantom
    open(jp, "wb").write(data.splitlines(keepends=True)[0])
    assert _held(run(S, journal=jp))
    # outcome C: the commit was torn -> whole journal fenced
    open(jp, "wb").write(data[:-3])
    h3 = run(S, journal=jp)
    assert _held(h3) and h3.journal_status()["healthy"] is False
    # operator clears the LIVE process: its applied rebind is re-journaled
    open(jp, "wb").write(data)
    assert h.clear_journal_fence(actor="op", reason="inspected")
    h4 = run(S, journal=jp)
    assert h4._plan_owner.get("a1:p") == "i" and h4.journal_status()["healthy"]


def test_journal_changed_outside_process_fences_without_writing(tmp_path):
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    os.unlink(jp)
    assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    st = h.journal_status()
    assert st["healthy"] is False and st["fence"]["kind"] == "changed"
    assert not os.path.exists(jp)


def test_unwritable_journal_at_startup_is_unhealthy(tmp_path):
    d = tmp_path / "ro"
    d.mkdir()
    os.chmod(d, 0o500)
    try:
        h = run(S, journal=str(d / "rebinds.jsonl"))
        st = h.journal_status()
        if os.geteuid() != 0:
            assert st["healthy"] is False and st["fence"]["kind"] == "unwritable"
            assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    finally:
        os.chmod(d, 0o700)


# ------------------------------------------------ 3 reordered records
def test_commit_before_its_pending_fences_whole_journal(tmp_path):
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    assert h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    a, b = _lines(jp)
    open(jp, "wb").write(b + a)
    h2 = run(S, journal=jp)
    st = h2.journal_status()
    assert _held(h2) and st["healthy"] is False
    assert st["corrupt_records"][0]["line"] == 1


def test_reordered_rebinds_fence_whole_journal(tmp_path):
    from tests.test_astra7519 import INCL
    from tests.test_astra7160 import PLAN
    jp = str(tmp_path / "rebinds.jsonl")
    s = [INCL("i", "p"), INCL("j", "p"), PLAN("p", "", 1),
         INCL("k", "q"), PLAN("q", "", 1), PLAN("p", "i", 1), PLAN("q", "k", 1)]
    h = run(s, journal=jp)
    assert h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    assert h.rebind_plan_owner("a1", "q", "k", actor="op", reason="t")
    L = _lines(jp)
    assert len(L) == 4
    for bad in (L[2:] + L[:2], [L[0], L[2], L[1], L[3]], L[:1] + L[2:]):
        open(jp, "wb").write(b"".join(bad))
        h2 = run(s, journal=jp)
        assert h2.journal_status()["healthy"] is False
        assert h2.owner_rebinds == []
    open(jp, "wb").write(b"".join(L))                  # intact: both replay
    h3 = run(s, journal=jp)
    assert h3._plan_owner.get("a1:p") == "i" and h3._plan_owner.get("a1:q") == "k"


def test_rehashed_forged_commit_without_chain_fences(tmp_path, monkeypatch):
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    real, n = os.fsync, []

    def second_fails(fd):
        if os.readlink(f"/proc/self/fd/{fd}") == os.path.realpath(jp):
            n.append(fd)
            if len(n) == 2:
                raise OSError("EIO")
        return real(fd)
    monkeypatch.setattr(os, "fsync", second_fails)
    assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    monkeypatch.undo()
    p = json.loads(_lines(jp)[0])
    c = {"v": hr.JOURNAL_VERSION, "op": "rebind_commit", "op_id": p["op_id"],
         "pending_hash": p["rec_hash"], "ts": 0, "prev": "wrong"}
    c["rec_hash"] = hr.HiveReducer._rec_hash(c)
    with open(jp, "a") as f:
        f.write(json.dumps(c) + "\n")
    h2 = run(S, journal=jp)
    assert _held(h2) and "chain" in h2.journal_status()["corrupt_records"][0]["why"]


def test_garbage_line_fences_everything_including_later_rebinds(tmp_path):
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    assert h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    with open(jp, "a") as f:
        f.write('{"op": "rebind_commit"\n')
    h2 = run(S, journal=jp)
    assert _held(h2) and h2.journal_status()["healthy"] is False
    assert ho(h2) == ["i", "j"]


def test_appliance_status_reports_journal_health(tmp_path):
    from hive.appliance import HiveAppliance
    jp = tmp_path / "rebinds.jsonl"
    jp.write_bytes(b'{"torn":')
    assert HiveAppliance(rebind_journal=str(jp)).status()["rebind_journal_healthy"] is False
    jp2 = tmp_path / "ok.jsonl"
    assert HiveAppliance(rebind_journal=str(jp2)).status()["rebind_journal_healthy"] is True
