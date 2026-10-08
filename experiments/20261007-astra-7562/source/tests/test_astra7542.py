"""Astra 7542 O-ownerless-hold, option (a) (Ben 2026-10-08: "(a) is best for
a first try"): a complete-but-ownerless plan linked to an open incident still
closes nothing, but is now VISIBLE (quarantine_reasons() -> ownerless_linked,
local + hive, survives restore), logs a warning, and has a documented repair:
a later PLAN that declares incident_id.  Ownership is never inferred.
"""
import json
import logging

from controller.reducer import Reducer
from tests.test_astra7160 import PLAN, RC, both, ho, lo
from tests.test_astra7519 import INCL, WITNESS


def rt(r):
    r2 = Reducer()
    r2.restore_snapshot(json.loads(json.dumps(r.snapshot())))
    return r2


def test_witness_reported_ownerless_linked_both_reducers():
    loc, hive = both(WITNESS)
    assert lo(loc) == ["i", "j"] and ho(hive) == ["i", "j"]
    assert loc.quarantine_reasons() == {"p": "ownerless_linked"}
    assert hive.quarantine_reasons() == {"a1:p": "ownerless_linked"}
    assert loc.quarantined_plans() == []          # rebind list unchanged


def test_reason_survives_restore_after_every_event():
    r = Reducer()
    for e in WITNESS:
        r.reduce(e)
        r = rt(r)
    assert lo(r) == ["i", "j"]
    assert r.quarantine_reasons() == {"p": "ownerless_linked"}


def test_warning_logged_when_complete_ownerless_linked(caplog):
    with caplog.at_level(logging.WARNING):
        both(WITNESS)
    msgs = [r.getMessage() for r in caplog.records
            if "no proven owner" in r.getMessage()]
    assert any("Plan p" in m for m in msgs)               # local
    assert any("Agent a1 plan p" in m for m in msgs)      # hive
    assert all("'i'" in m and "'j'" in m for m in msgs)


def test_no_warning_or_reason_for_unlinked_ownerless_plan(caplog):
    with caplog.at_level(logging.WARNING):
        loc, hive = both([INCL("i"), PLAN("p", "", 1), RC("x", "p", 0)])
    assert lo(loc) == ["i"]
    assert loc.quarantine_reasons() == {} and hive.quarantine_reasons() == {}
    assert not [r for r in caplog.records if "no proven owner" in r.getMessage()]


def test_owned_plan_never_reported():
    loc, hive = both([INCL("i", "p"), PLAN("p", "i", 2), RC("x", "p", 0)])
    assert lo(loc) == ["i"]                               # incomplete, owned
    assert loc.quarantine_reasons() == {} and hive.quarantine_reasons() == {}


def test_documented_repair_later_owner_declaring_plan():
    stream = WITNESS + [PLAN("p", "i", 1)]
    loc, hive = both(stream)
    assert lo(loc) == ["j"] and ho(hive) == ["j"]         # owner closed only
    assert loc._plan_owner["p"] == "i" and hive._plan_owner["a1:p"] == "i"
    assert loc.quarantine_reasons() == {} and hive.quarantine_reasons() == {}
    r = Reducer()
    for e in stream:
        r.reduce(e)
        r = rt(r)
    assert lo(r) == ["j"] and r.quarantine_reasons() == {}


def test_owner_unproven_reason_still_reported():
    r = Reducer()
    r._owner_unproven.add("legacy")
    assert r.quarantine_reasons() == {"legacy": "owner_unproven"}
    assert r.quarantined_plans() == ["legacy"]
