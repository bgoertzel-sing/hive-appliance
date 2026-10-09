"""Astra 7708 (docs/ASTRA_REVIEW_7708.md, 3ba9d6a) on 8945bdc.
F-joint-rollback-doc-scope: reset_journal(actor, reason) forces a fresh
journal + identity before replay, so a restored (healthy, self-consistent)
older pair cannot bring a discarded rebind back.
"""
import os

import pytest

import hive.reducer as hr
from tests.test_astra7638 import feed, run
from tests.test_astra7656 import S


class Crash(BaseException):
    pass


def _held(h):
    return h._plan_owner.get("a1:p") is None


def _restored_pair(tmp_path):
    """Astra recovery7708.restore_guidance: commit p, save journal+.id,
    corrupt tail, restart fenced, clear to discard p, restore both files."""
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(S, journal=jp)
    r = h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    assert r and r.status == "applied"
    saved = {f: open(f, "rb").read() for f in (jp, jp + ".id")}
    with open(jp, "ab") as f:
        f.write(b"garbage\n")
    h2 = run(S, journal=jp)
    assert h2.journal_status()["healthy"] is False and _held(h2)
    assert h2.clear_journal_fence(actor="op", reason="discard p")
    assert _held(run(S, journal=jp))                     # p discarded
    for f, b in saved.items():                           # joint rollback
        open(f, "wb").write(b)
    return jp


def test_clear_is_noop_on_restored_pair_but_reset_discards(tmp_path):
    jp = _restored_pair(tmp_path)
    h = hr.HiveReducer(rebind_journal=jp)                # before replay/serving
    h.register_agent("a1")
    assert h.journal_status()["healthy"] is True         # undetectable
    assert h.clear_journal_fence(actor="op", reason="x") is False  # Astra: no-op
    old_jid = h._journal_id
    info = h.reset_journal(actor="op", reason="restored from backup")
    assert info["rebinds_discarded"] == 1 and info["journal_id"] != old_jid
    for src, dst in info["archived"].items():            # kept for inspection
        assert os.path.exists(dst)
    feed(h, S)
    assert _held(h)                                      # p does not come back
    assert h.journal_status()["healthy"] is True
    for _ in range(2):                                   # nor after restarts
        h2 = run(S, journal=jp)
        assert _held(h2) and h2.journal_status()["healthy"] is True
    r = h2.rebind_plan_owner("a1", "p", "i", actor="op", reason="re-issued")
    assert r and r.status == "applied"                   # wanted ones re-issued
    assert run(S, journal=jp)._plan_owner.get("a1:p") == "i"


def test_without_reset_restored_pair_revives_p(tmp_path):
    # documents the limitation reset_journal exists for
    jp = _restored_pair(tmp_path)
    assert run(S, journal=jp)._plan_owner.get("a1:p") == "i"


def test_reset_refused_after_events_changes_nothing(tmp_path):
    jp = _restored_pair(tmp_path)
    before = {f: open(f, "rb").read() for f in (jp, jp + ".id")}
    h = run(S, journal=jp)
    with pytest.raises(RuntimeError):
        h.reset_journal(actor="op", reason="too late")
    assert {f: open(f, "rb").read() for f in (jp, jp + ".id")} == before
    with pytest.raises(ValueError):
        hr.HiveReducer(rebind_journal=jp).reset_journal(actor=" ", reason="r")


def test_reset_works_on_fenced_journal(tmp_path):
    jp = str(tmp_path / "rebinds.jsonl")
    run(S, journal=jp)
    open(jp + ".fence", "w").write("{}")                 # legacy marker
    h = hr.HiveReducer(rebind_journal=jp)
    assert h.journal_status()["fence"]["kind"] == "legacy"
    info = h.reset_journal(actor="op", reason="fresh start")
    assert info["was_fenced"] == "legacy" and not os.path.exists(jp + ".fence")
    assert run(S, journal=jp).journal_status()["healthy"] is True


def test_crash_between_new_anchor_and_new_journal_fences(tmp_path, monkeypatch):
    jp = _restored_pair(tmp_path)
    real = hr.HiveReducer._replace_durably

    def crash(self, path, data):
        if path == jp:
            raise Crash()
        return real(self, path, data)
    h = hr.HiveReducer(rebind_journal=jp)
    monkeypatch.setattr(hr.HiveReducer, "_replace_durably", crash)
    with pytest.raises(Crash):
        h.reset_journal(actor="op", reason="r")
    monkeypatch.undo()
    for _ in range(2):
        h2 = run(S, journal=jp)                          # old journal, new anchor
        assert h2.journal_status()["fence"]["kind"] == "identity" and _held(h2)
