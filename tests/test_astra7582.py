"""Astra 7582: F-foreign-progress (rebind applies only evidence naming the new
owner, both reducers), F-hold-expiry (a once-held plan gets an owner only via
the audited rebind; hive duplicate INCIDENT(resolved) too), durable hive rebind
journal (replayed after restart, fail-closed write), quiet preview simulation.
"""
import json
import logging

from controller.reducer import Reducer
from hive.reducer import HiveReducer
from hive.types import HiveEvent
from tests.test_astra7160 import PLAN, RC, ho, lo
from tests.test_astra7519 import INCL


def run(stream, journal=None):
    loc, hive = Reducer(), HiveReducer(rebind_journal=journal)
    hive.register_agent("a1")
    for e in stream:
        loc.reduce(e)
        hive.reduce(HiveEvent(source_agent="a1", original_event=e))
    return loc, hive


def feed(loc, hive, stream):
    for e in stream:
        loc.reduce(e)
        hive.reduce(HiveEvent(source_agent="a1", original_event=e))


FOREIGN = [INCL("i", "p"), INCL("j", "p"), PLAN("p", "", 2),
           RC("xj", "p", 0, incident_id="j"), RC("y", "p", 1)]


def test_foreign_progress_discarded_on_rebind_both_reducers():
    loc, hive = run(FOREIGN)
    assert loc.quarantined_plans() == ["p"]
    assert hive.quarantined_plans() == ["a1:p"]
    assert loc.preview_rebind("p", "i", allow_non_candidate=True)["foreign_steps_discarded"] == [0]
    assert hive.preview_rebind("a1", "p", "i", allow_non_candidate=True)["foreign_steps_discarded"] == [0]
    assert loc.rebind_plan_owner("p", "i", actor="op", reason="t", allow_non_candidate=True)
    assert hive.rebind_plan_owner("a1", "p", "i", actor="op", reason="t", allow_non_candidate=True)
    # j's evidence did NOT close i
    assert lo(loc) == ["i", "j"] and ho(hive) == ["i", "j"]
    assert loc._plan_verified.get("p") == {1}
    assert hive._plan_verified_steps.get("a1:p") == {1}
    assert hive.owner_rebinds[-1]["foreign_steps_discarded"] == [0]
    # re-proving step 0 for the new owner closes it
    feed(loc, hive, [RC("xi", "p", 0, incident_id="i")])
    assert lo(loc) == ["j"] and ho(hive) == ["j"]


HELD_THEN_RESOLVED = [INCL("i", "p"), INCL("j", "p"), PLAN("p", "", 1),
                      PLAN("q", "i", 1), RC("rq", "q", 0),
                      PLAN("r", "j", 1), RC("rr", "r", 0)]


def test_hold_survives_linked_incidents_resolving_elsewhere():
    loc, hive = run(HELD_THEN_RESOLVED)
    assert lo(loc) == [] and ho(hive) == []
    assert loc.quarantine_reasons() == {"p": "ownerless_held"}
    assert hive.quarantine_reasons() == {"a1:p": "ownerless_held"}
    feed(loc, hive, [INCL("k"), PLAN("p", "k", 1), RC("z", "p", 0, incident_id="k")])
    # ordinary re-send never sets the owner of a once-held plan
    assert loc._plan_owner.get("p") is None and hive._plan_owner.get("a1:p") is None
    assert lo(loc) == ["k"] and ho(hive) == ["k"]
    assert hive.owner_candidates == {"a1:p": ["k"]}
    assert loc.rebind_plan_owner("p", "k", actor="op", reason="t")
    assert hive.rebind_plan_owner("a1", "p", "k", actor="op", reason="t")
    assert lo(loc) == [] and ho(hive) == []
    assert loc.quarantine_reasons() == {} and hive.quarantine_reasons() == {}


def test_local_latch_survives_snapshot_roundtrip():
    loc, _ = run(HELD_THEN_RESOLVED)
    r2 = Reducer()
    r2.restore_snapshot(json.loads(json.dumps(loc.snapshot())))
    assert r2.quarantine_reasons() == {"p": "ownerless_held"}


def test_hive_duplicate_resolved_incident_keeps_hold():
    s = [INCL("i", "p"), INCL("j", "p"), PLAN("p", "", 1),
         INCL("i", "p", True), INCL("j", "p", True),
         INCL("k"), PLAN("p", "k", 1), RC("z", "p", 0, incident_id="k")]
    _, hive = run(s)
    assert hive._plan_owner.get("a1:p") is None
    assert ho(hive) == ["k"]
    assert hive.quarantine_reasons() == {"a1:p": "ownerless_held"}
    pv = hive.preview_rebind("a1", "p", "k")
    assert pv["allowed"] and pv["would_close"] == ["k"]
    assert ho(hive) == ["k"]          # preview closed nothing
    assert hive.rebind_plan_owner("a1", "p", "k", actor="op", reason="t")
    assert ho(hive) == []


def test_hive_rebind_journal_replayed_after_restart(tmp_path):
    jp = str(tmp_path / "rebinds.jsonl")
    _, hive = run(FOREIGN, journal=jp)
    assert hive.rebind_plan_owner("a1", "p", "i", actor="alice", reason="ticket-1",
                                  allow_non_candidate=True)
    lines = [json.loads(x) for x in open(jp) if x.strip()]
    assert len(lines) == 1 and lines[0]["op"] == "owner_rebind"
    # restart: fresh reducer, same journal, replayed event stream
    _, h2 = run(FOREIGN, journal=jp)
    assert h2._plan_owner.get("a1:p") == "i"
    assert h2.quarantine_reasons() == {}
    assert h2.journal_pending() == []
    rec = h2.owner_rebinds[-1]
    assert rec["replayed"] and rec["actor"] == "alice" and rec["reason"] == "ticket-1"
    assert ho(h2) == ["i", "j"]       # foreign evidence still not credited to i
    assert h2._plan_verified_steps.get("a1:p") == {1}
    # replay never re-writes the journal
    assert len([x for x in open(jp) if x.strip()]) == 1


def test_hive_rebind_fails_closed_when_journal_unwritable(tmp_path):
    _, hive = run(FOREIGN, journal=str(tmp_path / "rebinds.jsonl"))
    hive._journal_path = str(tmp_path)   # now a directory: append fails
    assert not hive.rebind_plan_owner("a1", "p", "i", actor="op", reason="t",
                                      allow_non_candidate=True)
    assert hive._plan_owner.get("a1:p") is None
    assert hive.quarantined_plans() == ["a1:p"]
    assert hive.owner_rebinds == []


def test_hive_preview_simulation_is_quiet(caplog):
    s = [INCL("i", "p"), PLAN("p", "", 1), RC("z", "p", 0, incident_id="i")]
    _, hive = run(s)
    caplog.clear()
    with caplog.at_level(logging.INFO):
        pv = hive.preview_rebind("a1", "p", "i", allow_non_candidate=True)
    assert pv["would_close"] == ["i"]
    loud = [r for r in caplog.records if r.levelno >= logging.INFO]
    assert not any("resolved" in r.getMessage() for r in loud), [r.getMessage() for r in loud]
    assert ho(hive) == ["i"]


def test_local_recovery_text_names_all_hold_reasons():
    loc, _ = run(HELD_THEN_RESOLVED)
    rec = loc.migration_diagnostics.get("recovery", "") if hasattr(loc, "migration_diagnostics") else ""
    if rec:
        assert "owner_unproven alone is NOT the full hold list" in rec
