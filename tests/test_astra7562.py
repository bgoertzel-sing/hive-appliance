"""Astra 7562 follow-ups that do not depend on the pending option decision:
O-retention (hive never prunes OPEN incidents, so ownerless_linked holds never
vanish at capacity) and late-link WARNING (incident linking to an already
complete ownerless plan logs like the in-order case, closes nothing).
"""
import logging

from hive import reducer as hr
from tests.test_astra7160 import PLAN, RC, both, ho, lo
from tests.test_astra7519 import INCL


def _held(n):
    s = []
    for k in range(n):
        s += [INCL(f"i{k}", f"p{k}"), PLAN(f"p{k}", "", 1)]
    return s


def test_hive_retains_all_open_incidents_past_cap():
    from hive.reducer import HiveReducer
    from hive.types import HiveEvent
    n = hr.MAX_AGENT_INCIDENTS + 100
    hive = HiveReducer()
    hive.register_agent("a1")
    for e in _held(n):
        hive.reduce(HiveEvent(source_agent="a1", original_event=e))
    reasons = hive.quarantine_reasons()
    assert len(reasons) == n
    assert reasons["a1:p0"] == "ownerless_linked"          # oldest kept
    assert len(ho(hive)) == n


def test_hive_still_trims_resolved_history_at_cap():
    from hive.reducer import HiveReducer
    from hive.types import HiveEvent
    cap = hr.MAX_AGENT_INCIDENTS
    hive = HiveReducer()
    hive.register_agent("a1")
    for k in range(cap + 50):
        hive.reduce(HiveEvent(source_agent="a1",
                              original_event=INCL(f"r{k}", "", resolved=True)))
    hive.reduce(HiveEvent(source_agent="a1", original_event=INCL("open")))
    assert len(hive._agent_incidents["a1"]) == cap
    assert ho(hive) == ["open"]


def _warn(caplog):
    return [r.getMessage() for r in caplog.records
            if "no proven owner" in r.getMessage()]


def test_late_link_warning_both_reducers(caplog):
    stream = [PLAN("p", "", 1), RC("x", "p", 0), INCL("i", "p"), INCL("j", "p")]
    with caplog.at_level(logging.WARNING):
        loc, hive = both(stream)
    assert lo(loc) == ["i", "j"] and ho(hive) == ["i", "j"]   # closes nothing
    msgs = _warn(caplog)
    assert any(m.startswith("Plan p") for m in msgs)
    assert any(m.startswith("Agent a1 plan p") for m in msgs)
    assert loc.quarantine_reasons() == {"p": "ownerless_linked"}
    assert hive.quarantine_reasons() == {"a1:p": "ownerless_linked"}


def test_no_late_link_warning_for_incomplete_plan(caplog):
    with caplog.at_level(logging.WARNING):
        loc, hive = both([PLAN("p", "", 2), RC("x", "p", 0), INCL("i", "p")])
    assert lo(loc) == ["i"] and not _warn(caplog)


def test_late_link_to_owned_plan_unchanged():
    loc, hive = both([PLAN("p", "i", 1), RC("x", "p", 0), INCL("i", "p"),
                      INCL("j", "p")])
    assert lo(loc) == ["j"] and ho(hive) == ["j"]           # owner only
