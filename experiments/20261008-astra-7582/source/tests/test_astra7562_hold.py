"""Astra 7562 D-option-conformance: the RECORDED decision (Ben, Telegram msg
7547, option (a)) for a registered OWNERLESS plan linked to an open incident:
HOLD it in quarantined_plans() (local + hive), let a re-sent owner-declaring
PLAN record only an owner CANDIDATE, and repair through the side-effect-free
preview_rebind() and the audited rebind_plan_owner().  Both reducers.
"""
import json

import pytest

from controller.reducer import Reducer
from tests.test_astra7160 import PLAN, RC, both, ho, lo
from tests.test_astra7519 import INCL, WITNESS

CAND = WITNESS + [PLAN("p", "i", 1)]          # i proposed as owner candidate


def rt(r):
    r2 = Reducer()
    r2.restore_snapshot(json.loads(json.dumps(r.snapshot())))
    return r2


def _state(loc, hive):
    return (json.dumps(loc.snapshot(), sort_keys=True, default=str),
            lo(loc), ho(hive), dict(hive._plan_owner),
            json.dumps(hive.owner_candidates, sort_keys=True),
            list(hive.owner_rebinds))


def test_held_in_quarantined_plans_both_reducers():
    loc, hive = both(WITNESS)
    assert loc.quarantined_plans() == ["p"]
    assert hive.quarantined_plans() == ["a1:p"]
    assert rt(loc).quarantined_plans() == ["p"]


def test_preview_is_side_effect_free_and_reports_hold():
    loc, hive = both(CAND)
    before = _state(loc, hive)
    pv = loc.preview_rebind("p", "i")
    hv = hive.preview_rebind("a1", "p", "i")
    assert _state(loc, hive) == before
    for v in (pv, hv):
        assert v["allowed"] and v["refusal"] == ""
        assert v["hold_reason"] == "ownerless_linked"
        assert v["is_candidate"] and v["candidates"] == ["i"]
        assert v["would_close"] == ["i"]


def test_rebind_closes_owner_only_with_audit_both_reducers():
    loc, hive = both(CAND)
    assert loc.rebind_plan_owner("p", "i", actor="op", reason="7562 test")
    assert hive.rebind_plan_owner("a1", "p", "i", actor="op", reason="7562 test")
    assert lo(loc) == ["j"] and ho(hive) == ["j"]
    assert loc._plan_owner["p"] == "i" and hive._plan_owner["a1:p"] == "i"
    assert loc.quarantined_plans() == [] and hive.quarantined_plans() == []
    la = loc.migration_diagnostics["owner_rebinds"][-1]
    ha = hive.owner_rebinds[-1]
    for a in (la, ha):
        assert a["actor"] == "op" and a["reason"] == "7562 test"
        assert a["candidate"] is True and a["hold_reason"] == "ownerless_linked"
    assert ha["closed"] == ["i"] and hive.owner_rebinds_total == 1
    r = rt(loc)
    assert lo(r) == ["j"] and r.quarantined_plans() == []


def test_non_candidate_refused_unless_explicit():
    loc, hive = both(WITNESS)                      # no candidate recorded
    assert not loc.rebind_plan_owner("p", "i", actor="op", reason="r")
    assert not hive.rebind_plan_owner("a1", "p", "i", actor="op", reason="r")
    assert lo(loc) == ["i", "j"] and ho(hive) == ["i", "j"]
    assert "not a recorded owner candidate" in loc.preview_rebind("p", "i")["refusal"]
    assert "not a recorded owner candidate" in hive.preview_rebind("a1", "p", "i")["refusal"]
    assert loc.rebind_plan_owner("p", "j", actor="op", reason="r",
                                 allow_non_candidate=True)
    assert hive.rebind_plan_owner("a1", "p", "j", actor="op", reason="r",
                                  allow_non_candidate=True)
    assert lo(loc) == ["i"] and ho(hive) == ["i"]
    assert hive.owner_rebinds[-1]["candidate"] is False


def test_actor_and_reason_required():
    loc, hive = both(CAND)
    for kw in ({"actor": "", "reason": "r"}, {"actor": "op", "reason": " "}):
        with pytest.raises(ValueError):
            loc.rebind_plan_owner("p", "i", **kw)
        with pytest.raises(ValueError):
            hive.rebind_plan_owner("a1", "p", "i", **kw)
    assert lo(loc) == ["i", "j"] and ho(hive) == ["i", "j"]


def test_refusals_unknown_resolved_and_other_plan_targets():
    stream = CAND + [INCL("k", "q"), PLAN("q", "", 2)]
    loc, hive = both(stream, plans=("p", "q"))
    for tgt in ("nope", "k"):
        assert not loc.rebind_plan_owner("p", tgt, actor="op", reason="r",
                                         allow_non_candidate=True)
        assert not hive.rebind_plan_owner("a1", "p", tgt, actor="op", reason="r",
                                          allow_non_candidate=True)
    assert lo(loc) == ["i", "j", "k"] and ho(hive) == ["i", "j", "k"]


def test_owned_or_unlinked_plan_is_not_held_or_rebindable():
    loc, hive = both([INCL("i", "p"), PLAN("p", "i", 2), RC("x", "p", 0)])
    assert loc.quarantined_plans() == [] and hive.quarantined_plans() == []
    assert loc.preview_rebind("p", "i")["refusal"] == "plan is not quarantined"
    assert hive.preview_rebind("a1", "p", "i")["refusal"] == "plan is not quarantined"
    loc, hive = both([INCL("i"), PLAN("p", "", 1), RC("x", "p", 0)])
    assert loc.quarantined_plans() == [] and hive.quarantined_plans() == []


def test_second_resend_does_not_rebind_and_candidates_dedupe():
    loc, hive = both(CAND + [PLAN("p", "i", 1), PLAN("p", "j", 1)])
    assert lo(loc) == ["i", "j"] and ho(hive) == ["i", "j"]
    assert loc.migration_diagnostics["owner_candidates"]["p"] == ["i", "j"]
    assert hive.owner_candidates["a1:p"] == ["i", "j"]
