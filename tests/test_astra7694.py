"""Astra 7694 (docs/ASTRA_REVIEW_7694.md, 5535545) on cf6a060.
1 Med F-applied-without-durable-commit: an unknown-durability commit returns an
      explicit, falsy RebindResult("uncertain"), never a durable success.
2 Med F-journal-rollback-anchor: journal_header with a random journal_id
      starts the chain; the current id is kept in a separate fsync'd anchor
      file <journal>.id; a mismatch (old/archived journal swapped back) fences.
3 Low F-runtime-integrity-overclaim: before every write (and on
      verify_journal()) the anchor and a SHA-256 of the WHOLE file are checked.
"""
import json
import os

import hive.reducer as hr
from tests.test_astra7160 import ho
from tests.test_astra7638 import run
from tests.test_astra7656 import S


def _held(h):
    return h._plan_owner.get("a1:p") is None and h.owner_rebinds == []


def _fail_commit_and_rollback(monkeypatch, jp):
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


# ------------------------------------------------ 1 explicit UNCERTAIN
def test_result_applied_refused_uncertain(tmp_path, monkeypatch):
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    r = h.rebind_plan_owner("a1", "zz", "i", actor="op", reason="t")
    assert not r and r.status == "refused" and r.applied is False
    _fail_commit_and_rollback(monkeypatch, jp)
    r = h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    monkeypatch.undo()
    assert r.status == "uncertain" and not r            # falsy: not durable
    assert r.applied is True and r.durable is None and r.op_id
    assert h.last_rebind_result is r
    st = h.journal_status()
    assert st["fence"]["kind"] == "commit_uncertain"
    assert st["fence"]["applied"] is True and st["fence"]["durable"] is None
    assert r.as_dict()["status"] == "uncertain"
    # Astra's witness: no commit on disk -> restart holds the plan again,
    # which the caller was told was possible (not a durable success)
    lines = open(jp, "rb").read().splitlines(keepends=True)
    open(jp, "wb").write(b"".join(lines[:2]))
    assert _held(run(S, journal=jp))


def test_durable_success_is_applied_and_truthy(tmp_path):
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    r = h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    assert r and r.status == "applied" and r.applied and r.durable is True
    assert r.op_id in open(jp).read()
    assert run(S, journal=jp)._plan_owner.get("a1:p") == "i"


# ------------------------------------------------ 2 journal identity anchor
def test_archived_valid_journal_swapped_back_is_fenced(tmp_path):
    # Astra's archive_splice witness
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    assert h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    good = open(jp, "rb").read()                       # prior VALID journal
    with open(jp, "ab") as f:
        f.write(b'{"torn":')
    h2 = run(S, journal=jp)
    assert _held(h2) and h2.journal_status()["healthy"] is False
    assert h2.clear_journal_fence(actor="op", reason="discard old authorization")
    arch = h2.journal_status()["fence_clearances"][-1]["archived"]
    assert open(arch, "rb").read() == good + b'{"torn":'
    assert _held(run(S, journal=jp))                   # reset journal holds p
    for old in (good, open(arch, "rb").read()[:len(good)]):   # copy / clean prefix
        open(jp, "wb").write(old)
        h3 = run(S, journal=jp)
        st = h3.journal_status()
        assert _held(h3) and ho(h3) == ["i", "j"]       # p NOT closed again
        assert st["healthy"] is False and st["fence"]["kind"] == "identity"
        assert not h3.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")


def test_journal_and_anchor_ids_and_reset_chain(tmp_path):
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    first = json.loads(open(jp).readline())
    assert first["op"] == "journal_header" and first["prev"] == ""
    anchor = json.load(open(jp + ".id"))
    assert anchor["journal_id"] == first["journal_id"] == h.journal_status()["journal_id"]
    open(jp, "ab").write(b"x")
    h2 = run(S, journal=jp)
    assert h2.clear_journal_fence(actor="op", reason="r")
    new = json.loads(open(jp).readline())
    assert new["journal_id"] != first["journal_id"]     # fresh identity
    assert json.load(open(jp + ".id"))["journal_id"] == new["journal_id"]
    assert run(S, journal=jp).journal_status()["healthy"] is True


def test_missing_or_bad_anchor_or_journal_fences(tmp_path):
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    assert h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    data, anc = open(jp, "rb").read(), open(jp + ".id", "rb").read()
    os.unlink(jp + ".id")                               # anchor removed
    h2 = run(S, journal=jp)
    assert _held(h2) and h2.journal_status()["fence"]["kind"] == "identity"
    open(jp + ".id", "wb").write(b"\x00junk")          # anchor garbage
    assert run(S, journal=jp).journal_status()["fence"]["kind"] == "identity"
    open(jp + ".id", "wb").write(anc)
    os.unlink(jp)                                       # journal removed
    h3 = run(S, journal=jp)
    assert h3.journal_status()["fence"]["kind"] == "identity" and not os.path.exists(jp)
    open(jp, "wb").write(data)                          # both intact again
    assert run(S, journal=jp)._plan_owner.get("a1:p") == "i"


def test_header_only_journal_without_anchor_is_adopted(tmp_path):
    # crash between creating the journal and writing its anchor
    jp = str(tmp_path / "rebinds.jsonl")
    run(S, journal=jp)
    os.unlink(jp + ".id")
    h = run(S, journal=jp)
    assert h.journal_status()["healthy"] is True and os.path.exists(jp + ".id")
    assert h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")


def test_journal_without_header_is_fenced(tmp_path):
    jp = str(tmp_path / "rebinds.jsonl")
    run(S, journal=jp)
    lines = open(jp).read().splitlines(keepends=True)
    h = run(S, journal=jp)
    assert h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    lines = open(jp).read().splitlines(keepends=True)
    open(jp, "w").write("".join(lines[1:]))            # header dropped
    h2 = run(S, journal=jp)
    st = h2.journal_status()
    assert _held(h2) and st["healthy"] is False
    assert st["corrupt_records"][0]["line"] == 1        # chain must start at a header


def test_swap_at_runtime_refused_and_fenced(tmp_path):
    jp = str(tmp_path / "rebinds.jsonl")
    other = str(tmp_path / "other.jsonl")
    h = run(S, journal=jp)
    run(S, journal=other)
    os.replace(other, jp)                               # different valid journal
    assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    assert h.journal_status()["fence"]["kind"] == "changed" and _held(h)


# ------------------------------------------------ 3 runtime integrity
def test_same_length_edit_of_earlier_record_detected_at_runtime(tmp_path):
    # Astra's startup_external_health witness
    from tests.test_astra7519 import INCL
    from tests.test_astra7160 import PLAN
    jp = str(tmp_path / "rebinds.jsonl")
    s = [INCL("i", "p"), INCL("j", "p"), PLAN("p", "", 1),
         INCL("k", "q"), PLAN("q", "", 1), PLAN("p", "i", 1), PLAN("q", "k", 1)]
    h = run(s, journal=jp)
    assert h.rebind_plan_owner("a1", "p", "i", actor="op", reason="ticket-1")
    data = open(jp, "rb").read()
    bad = data.replace(b"ticket-1", b"ticket-2", 1)
    assert len(bad) == len(data) and bad.endswith(data[-200:])
    open(jp, "r+b").write(bad)
    r = h.rebind_plan_owner("a1", "q", "k", actor="op", reason="t")
    assert not r and r.status == "refused"
    st = h.journal_status()
    assert st["healthy"] is False and st["fence"]["kind"] == "changed"
    assert open(jp, "rb").read() == bad                 # nothing written


def test_verify_journal_on_demand(tmp_path):
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    assert h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    assert h.verify_journal() is True
    data = open(jp, "rb").read()
    open(jp, "r+b").write(data.replace(b'"op"', b'"oP"', 1))
    assert h.verify_journal() is False
    assert h.journal_status()["healthy"] is False
    assert run(S, journal=None).verify_journal() is True
