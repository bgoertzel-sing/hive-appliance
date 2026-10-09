"""Astra 7638 (docs/ASTRA_REVIEW_7638.md, ff692b9):
1 High  F-unregister-escape: unregister/re-register keeps the hold, provenance
        and receipt dedup; only the audited rebind can give the plan an owner.
2 High  F-journal-order: a journaled rebind is re-applied exactly at its
        original event-stream position (seq + stream hash chain), never earlier.
3 Med   F-journal-refused-fsync: a refused rebind is rolled back and never
        applied after restart; failed rollback = indeterminate + fenced.
4 Med   F-journal-tail: a torn last line is set aside before any new write.
5 Med   HiveAppliance refuses rebinds without a journal (opt-out explicit);
  Low   caps on candidate keys and journal size.
"""
import json
import os

import pytest

import hive.reducer as hr
from hive.appliance import HiveAppliance
from hive.reducer import HiveReducer
from hive.types import HiveEvent
from tests.test_astra7160 import PLAN, RC, ho
from tests.test_astra7519 import INCL


def run(stream, journal=None, **kw):
    h = HiveReducer(rebind_journal=journal, **kw)
    h.register_agent("a1")
    feed(h, stream)
    return h


def feed(h, stream):
    for e in stream:
        h.reduce(HiveEvent(source_agent="a1", original_event=e))


# ------------------------------------------------ 1 F-unregister-escape
def test_unregister_reregister_keeps_hold_and_provenance():
    h = run([INCL("j", "p"), PLAN("p", "", 1), RC("x", "p", 0, incident_id="j")])
    assert h.quarantined_plans() == ["a1:p"]
    h.unregister_agent("a1")
    h.register_agent("a1")
    assert h.quarantined_plans() == ["a1:p"]          # hold survives
    feed(h, [INCL("k"), PLAN("p", "k", 1)])
    assert h._plan_owner.get("a1:p") is None          # no unaudited owner
    assert ho(h) == ["k"]                             # j's evidence closed nothing
    assert h.owner_candidates == {"a1:p": ["k"]}
    assert h.owner_rebinds == []
    pv = h.preview_rebind("a1", "p", "k")
    assert pv["allowed"] and pv["would_close"] == [] and pv["foreign_steps_discarded"] == [0]
    assert h.rebind_plan_owner("a1", "p", "k", actor="op", reason="t")
    assert ho(h) == ["k"]
    feed(h, [RC("x", "p", 0, incident_id="j")])       # dedup'd old receipt
    assert ho(h) == ["k"]
    feed(h, [RC("xk", "p", 0, incident_id="k")])
    assert ho(h) == []


def test_unregister_escape_via_appliance_reducer():
    a = HiveAppliance(volatile_rebinds=True)
    r = a.reducer
    r.register_agent("a1")
    feed(r, [INCL("j", "p"), PLAN("p", "", 1), RC("x", "p", 0, incident_id="j")])
    a.unregister_agent("a1")
    r.register_agent("a1")
    feed(r, [INCL("k"), PLAN("p", "k", 1)])
    assert r._plan_owner.get("a1:p") is None and ho(r) == ["k"]
    assert r.quarantined_plans() == ["a1:p"]


# ------------------------------------------------ 2 F-journal-order
BASE = [INCL("i", "p"), INCL("j", "p"), PLAN("p", "", 1)]
VARIANTS = {
    "target_success_then_failure": [RC("yes", "p", 0, incident_id="i"),
                                    RC("no", "p", 0, ok=False, incident_id="i")],
    "plan_only_success_then_failure": [RC("yes", "p", 0),
                                       RC("no", "p", 0, ok=False)],
    "target_success_then_foreign_failure": [RC("yes", "p", 0, incident_id="i"),
                                            RC("no", "p", 0, ok=False, incident_id="j")],
}


def _state(h):
    return (ho(h), h._plan_owner.get("a1:p"), h.quarantined_plans(),
            sorted(h._plan_verified_steps.get("a1:p", set())),
            [(r["incident_id"], r["actor"], r["reason"], r["foreign_steps_discarded"])
             for r in h.owner_rebinds])


@pytest.mark.parametrize("name", sorted(VARIANTS))
def test_journal_rebind_replayed_at_original_position(tmp_path, name):
    jp = str(tmp_path / "rebinds.jsonl")
    s = BASE + VARIANTS[name] + [PLAN("p", "i", 1)]
    h = run(s, journal=jp)
    assert h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t",
                               allow_non_candidate=True)
    orig = _state(h)
    assert "i" in orig[0]                             # i correctly still open
    h2 = run(s, journal=jp)                           # restart
    assert _state(h2) == orig
    assert h2.owner_rebinds[-1]["replayed"] is True
    assert h2.journal_pending() == [] and h2.journal_status()["unapplied"] == []


def test_journal_entry_with_later_events_after_restart(tmp_path):
    jp = str(tmp_path / "rebinds.jsonl")
    s = BASE + [RC("a", "p", 0, incident_id="i"), PLAN("p", "i", 1)]
    h = run(s, journal=jp)
    assert h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    later = [INCL("z")]
    feed(h, later)
    h2 = run(s + later, journal=jp)
    assert _state(h2) == _state(h)


def test_journal_not_applied_on_a_different_stream(tmp_path):
    jp = str(tmp_path / "rebinds.jsonl")
    s = BASE + [PLAN("p", "i", 1)]
    h = run(s, journal=jp)
    assert h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    other = [INCL("i", "p"), INCL("x"), INCL("j", "p"), PLAN("p", "", 1)]
    h2 = run(other, journal=jp)
    assert h2._plan_owner.get("a1:p") is None
    un = h2.journal_status()["unapplied"]
    assert len(un) == 1 and "differs" in un[0]["why"]


def test_legacy_v1_entry_without_position_is_not_replayed(tmp_path):
    jp = tmp_path / "rebinds.jsonl"
    jp.write_text(json.dumps({"v": 1, "op": "owner_rebind", "agent_id": "a1",
                              "plan_id": "p", "incident_id": "i", "actor": "op",
                              "reason": "t"}) + "\n")
    h = run(BASE, journal=str(jp))
    assert h._plan_owner.get("a1:p") is None
    st = h.journal_status()                      # Astra 7678: fences the journal
    assert st["healthy"] is False and "legacy" in st["fence"]["error"]


# ------------------------------------------------ 3 F-journal-refused-fsync
def test_refused_fsync_rebind_never_applied_after_restart(tmp_path, monkeypatch):
    jp = str(tmp_path / "rebinds.jsonl")
    s = BASE + [PLAN("p", "i", 1)]
    h = run(s, journal=jp)
    real, calls = os.fsync, []

    def bad_once(fd):
        # Astra 7656: fence marker is fsync'd first; fail the journal's append fsync
        if os.readlink(f"/proc/self/fd/{fd}") == os.path.realpath(jp):
            calls.append(fd)
            if len(calls) == 1:
                raise OSError("EIO")
        return real(fd)
    monkeypatch.setattr(os, "fsync", bad_once)
    assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    monkeypatch.setattr(os, "fsync", real)
    assert os.path.getsize(jp) == 0                   # rolled back
    assert not os.path.exists(jp + ".fence")          # clean refusal: no fence
    assert h._plan_owner.get("a1:p") is None
    h2 = run(s, journal=jp)
    assert h2._plan_owner.get("a1:p") is None and h2.owner_rebinds == []
    assert h2.quarantined_plans() == ["a1:p"]


def test_failed_rollback_is_indeterminate_and_fences(tmp_path, monkeypatch):
    jp = str(tmp_path / "rebinds.jsonl")
    h = run(BASE + [PLAN("p", "i", 1)], journal=jp)

    real_fsync = os.fsync

    def journal_fsync(fd):
        # Astra 7656: the fence marker is made durable first; fail only the
        # journal's own fsync (and its rollback) so the outcome is uncertain.
        if os.readlink(f"/proc/self/fd/{fd}") == os.path.realpath(jp):
            raise OSError("EIO")
        return real_fsync(fd)

    def boom(*a):
        raise OSError("EIO")
    monkeypatch.setattr(os, "fsync", journal_fsync)
    monkeypatch.setattr(os, "ftruncate", boom)
    assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    monkeypatch.undo()
    st = h.journal_status()
    assert st["healthy"] is False and st["fence"]["kind"] == "write_failure"
    assert st["fence"]["applied"] is False
    assert h._plan_owner.get("a1:p") is None
    # fenced: even a healthy journal refuses further rebinds until inspected
    assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")


def test_short_or_failed_write_is_clean_refusal(tmp_path):
    h = run(BASE + [PLAN("p", "i", 1)], journal=str(tmp_path / "j.jsonl"))
    h._journal_path = str(tmp_path)                   # a directory
    assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    assert h.journal_status()["healthy"] is True


# ------------------------------------------------ 4 F-journal-tail
S_HELD = BASE + [PLAN("p", "i", 1)]


def test_torn_tail_at_startup_fences_whole_journal(tmp_path):
    # Astra 7678: a torn tail is never trimmed; it fences the whole journal
    jp = tmp_path / "rebinds.jsonl"
    jp.write_bytes(b'{"op": "owner_reb')
    h = run(S_HELD, journal=str(jp))
    st = h.journal_status()
    assert st["healthy"] is False and "torn" in st["fence"]["error"]
    assert jp.read_bytes() == b'{"op": "owner_reb'
    assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    assert h.clear_journal_fence(actor="op", reason="inspected")
    arch = h.journal_status()["fence_clearances"][-1]["archived"]
    assert open(arch, "rb").read() == b'{"op": "owner_reb'
    assert h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    h2 = run(S_HELD, journal=str(jp))                 # restart: rebind survives
    assert h2._plan_owner.get("a1:p") == "i"
    assert ho(h2) == ["i", "j"]                       # no receipts yet: nothing closed
    assert h2.journal_status()["healthy"] is True
    assert h2.owner_rebinds and h2.owner_rebinds[-1]["replayed"] is True


def test_torn_tail_appearing_at_runtime_fences(tmp_path):
    jp = tmp_path / "rebinds.jsonl"
    s = [INCL("i", "p"), INCL("j", "p"), PLAN("p", "", 1),
         INCL("k", "q"), PLAN("q", "", 1), PLAN("p", "i", 1), PLAN("q", "k", 1)]
    h = run(s, journal=str(jp))
    assert h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    good = jp.read_bytes()
    with open(jp, "ab") as f:
        f.write(b'{"torn":')
    assert not h.rebind_plan_owner("a1", "q", "k", actor="op", reason="t")
    assert jp.read_bytes() == good + b'{"torn":'      # nothing written or trimmed
    assert h.journal_status()["fence"]["kind"] == "changed"
    h2 = run(s, journal=str(jp))
    assert h2.journal_status()["healthy"] is False
    assert h2._plan_owner.get("a1:p") is None and h2.owner_rebinds == []


# ------------------------------------------------ 5 defaults and caps
def test_appliance_refuses_rebind_without_journal(monkeypatch):
    monkeypatch.delenv("HIVE_REBIND_JOURNAL", raising=False)
    a = HiveAppliance()
    a.reducer.register_agent("a1")
    feed(a.reducer, S_HELD)
    assert a.reducer.journal_status()["durable"] is False
    assert not a.reducer.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    assert a.reducer.quarantined_plans() == ["a1:p"]


def test_appliance_uses_env_journal(monkeypatch, tmp_path):
    jp = tmp_path / "rebinds.jsonl"
    monkeypatch.setenv("HIVE_REBIND_JOURNAL", str(jp))
    a = HiveAppliance()
    a.reducer.register_agent("a1")
    feed(a.reducer, S_HELD)
    assert a.reducer.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    assert jp.read_text().count("\n") == 2            # pending + commit


def test_appliance_explicit_volatile_opt_out(monkeypatch):
    monkeypatch.delenv("HIVE_REBIND_JOURNAL", raising=False)
    a = HiveAppliance(volatile_rebinds=True)
    a.reducer.register_agent("a1")
    feed(a.reducer, S_HELD)
    assert a.reducer.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")


def test_candidate_keys_capped_hold_kept(monkeypatch):
    monkeypatch.setattr(hr, "MAX_HIVE_CANDIDATE_KEYS", 2)
    s = []
    for k in range(3):
        s += [INCL(f"i{k}", f"p{k}"), PLAN(f"p{k}", "", 1),
              INCL(f"c{k}"), PLAN(f"p{k}", f"c{k}", 1)]
    h = run(s)
    assert len(h.owner_candidates) == 2 and h.owner_candidates_dropped >= 1
    assert len(h.quarantined_plans()) == 3
    assert h.rebind_plan_owner("a1", "p2", "c2", actor="op", reason="t",
                               allow_non_candidate=True)


def test_journal_size_cap_refuses_cleanly(monkeypatch, tmp_path):
    jp = tmp_path / "rebinds.jsonl"
    h = run(S_HELD, journal=str(jp))
    monkeypatch.setattr(hr, "MAX_HIVE_JOURNAL_BYTES", 10)
    assert not h.rebind_plan_owner("a1", "p", "i", actor="op", reason="t")
    assert jp.read_bytes() == b"" and h._plan_owner.get("a1:p") is None
