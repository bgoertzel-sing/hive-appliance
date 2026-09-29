"""Independent declarative semantic oracles; failures are saved, not suppressed.

No old pending evidence is expected to equal uninterrupted history after discard.
Current-format ordered evidence is expected to retain its actual latest result.
An authoritative first owner cannot be expanded by a later PLAN or incident link.
"""
import importlib.util
import itertools
import json
import os
from pathlib import Path
import sys

E = Path(__file__).resolve().parent
sys.path.insert(0, os.environ["HIVE_SRC"])
from controller.reducer import Reducer
from hive.reducer import HiveReducer
from hive.types import HiveEvent
from recovery.checkpoint import CheckpointManager
from schemas.types import Event, EventKind

def load(ref):
    spec = importlib.util.spec_from_file_location("old_" + ref, E / ("legacy-reducer-" + ref + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.Reducer

Legacy = load("e6afe16")
Prior = load("5de0d53")

def I(i="i", p="", resolved=False):
    return Event(kind=EventKind.INCIDENT, ts=1700000000., payload=dict(id=i, ts=1700000000.,
        component="svc", symptom="down", severity="critical", plan_id=p, resolved=resolved))

def P(p="p", i="i", n=2):
    return Event(kind=EventKind.PLAN, payload=dict(id=p, incident_id=i, steps=[{} for _ in range(n)]))

def R(r, idx=0, ok=True, p="p", i=""):
    return Event(kind=EventKind.RECEIPT, payload=dict(id=r, step_index=idx, verified=ok, plan_id=p, incident_id=i))

def save(name, value):
    with (E / name).open("x") as f:
        json.dump(value, f, indent=2)
        f.write("\n")

def local(l):
    return dict(open=sorted(i.id for i in l.open_incidents()),
        verified={k: sorted(v) for k, v in l._plan_verified.items()},
        failed={k: sorted(v) for k, v in l._plan_failed_steps.items()},
        owner=getattr(l, "_plan_owner", {}),
        links={i.id: i.plan_id for i in l.incidents},
        discarded=getattr(l, "legacy_pending_discarded", None),
        pending=len(l._pending_receipts))

def hive(h, a="a"):
    prefix = a + ":"
    return dict(open=sorted(i["incident_id"] for i in h._open_agent_incidents(a)),
        verified={k[len(prefix):]: sorted(v) for k, v in h._plan_verified_steps.items() if k.startswith(prefix)},
        failed={k[len(prefix):]: sorted(v) for k, v in h._plan_failed.items() if k.startswith(prefix)},
        owner={k[len(prefix):]: v for k, v in h._plan_owner.items() if k.startswith(prefix)},
        links={i["incident_id"]: i.get("plan_id", "") for i in h._agent_incidents.get(a, [])},
        health=h.state.agents[a].health.value, displayed_open=h.state.agents[a].open_incidents)

def new_hive():
    h = HiveReducer()
    h.register_agent("a")
    return h

def feed(l, h, e):
    l.reduce(e)
    h.reduce(HiveEvent(source_agent="a", original_event=e))

def restore(l):
    s = json.loads(json.dumps(l.snapshot(), sort_keys=True))
    r = Reducer()
    r.restore_snapshot(s)
    return r

def expect(s, opened, verified=None, failed=None, owner=None):
    ok = s["open"] == sorted(opened)
    for field, wanted in (("verified", verified), ("failed", failed), ("owner", owner)):
        if wanted is not None:
            ok &= all(s[field].get(k, [] if field != "owner" else "") == v for k, v in wanted.items())
    if "displayed_open" in s:
        ok &= s["displayed_open"] == len(opened)
        ok &= s["health"] == ("failed" if opened else "healthy")
    return bool(ok)

def summary(rows):
    return dict(total=len(rows), passed=sum(r["passed"] for r in rows),
                failed=sum(not r["passed"] for r in rows))

current, ordered_old, migrated = [], [], []
vals = [(0, True), (0, False), (1, True), (1, False)]
for order in itertools.permutations(range(4)):
    for mask in range(16):
        latest = {}
        stream = [I()]
        for j in order:
            idx, ok = vals[j]
            latest[idx] = ok
            stream.append(R("r" + str(j), idx, ok,
                p="" if mask & (1 << j) else "p", i="i" if mask & (1 << j) else ""))
        stream += [P(), R("fresh0"), R("fresh1", 1)]
        for cls, dest in ((Reducer, current), (Prior, ordered_old)):
            for boundary in range(len(stream)):
                l, h = cls(), new_hive()
                passed, trace = True, []
                for j, e in enumerate(stream):
                    feed(l, h, e)
                    if j == boundary:
                        l = restore(restore(l))
                    expected = {} if j < 5 else dict(latest)
                    if j >= 6:
                        expected[0] = True
                    if j >= 7:
                        expected[1] = True
                    opened = [] if len(expected) == 2 and all(expected.values()) else ["i"]
                    v = {"p": sorted(k for k, x in expected.items() if x)}
                    f = {"p": sorted(k for k, x in expected.items() if not x)}
                    ls, hs = local(l), hive(h)
                    passed &= expect(ls, opened, v, f) and expect(hs, opened, v, f)
                    trace.append(dict(event=j, local=ls, hive=hs))
                dest.append(dict(order=order, mask=mask, boundary=boundary, passed=passed,
                                 trace=trace if not passed else None))
        old = Legacy()
        for e in stream[:5]:
            old.reduce(e)
        snap = json.loads(json.dumps(old.snapshot()))
        l = restore(old)
        discard = l.legacy_pending_discarded
        l = restore(restore(l))
        l.reduce(P())
        states = [local(l)]
        l.reduce(R("fresh0"))
        states.append(local(l))
        l.reduce(R("fresh1", 1))
        states.append(local(l))
        passed = discard == 4 and expect(states[0], ["i"], {"p": []}, {"p": []})
        passed &= expect(states[1], ["i"], {"p": [0]}) and expect(states[2], [], {"p": [0, 1]})
        migrated.append(dict(order=order, mask=mask, passed=bool(passed), discarded=discard, states=states))

save("current-format-sweep.json", current)
save("prior-ordered-format-sweep.json", ordered_old)
save("legacy-fail-closed-sweep.json", migrated)

# The original two indistinguishable histories, now judged by fail-closed policy.
inc, seed, success, failure = I(), R("seed1", 1), R("old_success", p="", i="i"), R("new_failure", ok=False)
witnesses, snapshots = [], []
manager = CheckpointManager(str(E / "legacy-checkpoint"))
for label, seq, live_open in (
    ("latest_failure", [inc, seed, success, failure], ["i"]),
    ("latest_success", [inc, seed, failure, success], []),
):
    old, live, h = Legacy(), Reducer(), new_hive()
    for e in seq:
        old.reduce(e)
        feed(live, h, e)
    snap = old.snapshot()
    snapshots.append(json.dumps(snap, sort_keys=True))
    ck = manager.create(snap, label=label)
    l = Reducer()
    l.restore_snapshot(manager.load(ck.id).appliance_state)
    discarded = l.legacy_pending_discarded
    l = restore(restore(l))
    l.reduce(P())
    feed(live, h, P())
    before = local(l)
    l.reduce(R("fresh0"))
    middle = local(l)
    l.reduce(R("fresh1", 1))
    final = local(l)
    passed = discarded == 3 and expect(before, ["i"], {"p": []}, {"p": []})
    passed &= expect(middle, ["i"]) and expect(final, [])
    passed &= expect(local(live), live_open) and expect(hive(h), live_open)
    witnesses.append(dict(name=label, passed=bool(passed), discarded=discarded,
        snapshot=snap, checkpoint_id=ck.id, before=before, after_fresh0=middle,
        after_fresh1=final, uninterrupted_local=local(live), uninterrupted_hive=hive(h)))
assert snapshots[0] == snapshots[1], "Actual legacy information-loss fixture must be byte-identical"
save("legacy-original-witnesses.json", dict(identical_snapshot_bytes=True, cases=witnesses))

# Authentic stale progress plus a later, not-yet-applicable failure for the same step.
# A later duplicate PLAN makes the pending incident receipt applicable without restore.
stale = []
for mode in ("direct", "roundtrip_twice", "legacy_twice"):
    seq = [P(), R("stale_success"), R("later_failure", ok=False, p="", i="i"), I()]
    old, live, h = Legacy(), Reducer(), new_hive()
    for e in seq:
        old.reduce(e)
        feed(live, h, e)
    snap = old.snapshot()
    ck = manager.create(snap, label="stale-progress-" + mode)
    l = Reducer()
    l.restore_snapshot(manager.load(ck.id).appliance_state)
    discarded = l.legacy_pending_discarded
    if mode == "roundtrip_twice":
        l = restore(restore(l))
    elif mode == "legacy_twice":
        l.restore_snapshot(snap)
    restored_state = local(l)
    l.reduce(P())
    feed(live, h, P())
    before = local(l)
    l.reduce(R("fresh1", 1))
    feed(live, h, R("fresh1", 1))
    partial = local(l)
    l.reduce(R("fresh0"))
    final = local(l)
    passed = discarded == 1 and expect(before, ["i"]) and expect(partial, ["i"])
    passed &= expect(final, []) and expect(local(live), ["i"], {"p": [1]}, {"p": [0]})
    stale.append(dict(name=mode, passed=bool(passed), events=[e.to_dict() for e in seq],
        legacy_snapshot=snap, checkpoint_id=ck.id, discarded=discarded,
        restored=restored_state, after_plan=before, after_fresh1=partial, after_fresh0=final,
        uninterrupted_local=local(live), uninterrupted_hive=hive(h),
        oracle="Discard cannot leave stale step-0 success sufficient to close after only fresh step 1."))
save("legacy-stale-progress.json", stale)

cases = []
def lifecycle(name, seq, opened, verified=None, owner=None, boundary=None, cls=Reducer, repeat=1):
    l, h = cls(), new_hive()
    trace = []
    for j, e in enumerate(seq):
        feed(l, h, e)
        if j == boundary:
            for _ in range(repeat):
                l = restore(l)
        trace.append(dict(event=e.to_dict(), local=local(l), hive=hive(h)))
    passed = expect(local(l), opened, verified, owner=owner)
    passed &= expect(hive(h), opened, verified, owner=owner)
    cases.append(dict(name=name, passed=bool(passed), producer=cls.__name__, boundary=boundary,
        repeat_restore=repeat, expected=dict(open=opened, verified=verified, owner=owner), trace=trace))

original_n4 = [I(), I("other"), R("bad", i="other"), R("good", 1), P("q", "other", 1), R("q0", p="q"), P()]
for boundary in range(len(original_n4)):
    lifecycle("original_n4_boundary_" + str(boundary), original_n4, ["i"], {"p": [1]}, boundary=boundary, repeat=2)

resolved = [I(), I("other"), P(), P("q", "other", 1), R("q0", p="q"), R("p0"), R("bad1", 1, i="other")]
unlinked = [I(), I("other"), P(), R("p0"), R("bad1", 1, i="other")]
for name, seq, opened in (("resolved", resolved, ["i"]), ("unlinked", unlinked, ["i", "other"])):
    lifecycle(name + "_live", seq, opened, {"p": [0]})
    for boundary in range(len(seq)):
        lifecycle(name + "_current_boundary_" + str(boundary), seq, opened, {"p": [0]}, boundary=boundary, repeat=2)
    # Real prior producer up to this point, not a new snapshot with one key deleted.
    lifecycle(name + "_authentic_old_snapshot", seq, opened, {"p": [0]}, boundary=3, cls=Prior, repeat=2)

base = [I(), I("other"), P()]
lifecycle("open_foreign_owner", base + [P("q", "other", 1), R("p0"), R("bad1", 1, i="other")], ["i", "other"], {"p": [0]})
lifecycle("missing_foreign_target", [I(), P(), R("p0"), R("bad1", 1, i="missing")], ["i"], {"p": [0]})
lifecycle("missing_correct_owner_then_incident", [P(), R("p0", i="i"), I(), R("p1", 1, i="i")], [], {"p": [0, 1]}, {"p": "i"})
lifecycle("contradiction_buffered_then_owner", [I(), I("other"), R("bad1", 1, i="other"), R("p0"), P()], ["i", "other"], {"p": [0]})
lifecycle("contradiction_then_fresh_recovery", [I(), I("other"), R("bad1", 1, i="other"), R("p0"), P(), R("fresh1", 1)], ["other"], {"p": [0, 1]})
lifecycle("duplicate_plan_same_owner", [I(), P(), R("p0"), P(), R("p1", 1), P()], [], {"p": [0, 1]}, {"p": "i"})
lifecycle("conflicting_plan_count_first_wins", [I(), P(), R("p0"), P(n=1)], ["i"], {"p": [0]}, {"p": "i"})
lifecycle("conflicting_plan_count_retry", [I(), P(), R("p0"), P(n=1), R("p1", 1)], [], {"p": [0, 1]}, {"p": "i"})
lifecycle("duplicate_receipt_conflicting_payload", [I(), P(), R("same"), R("same", 1), R("fresh1", 1)], [], {"p": [0, 1]})

rebound = base + [R("p0"), P("p", "other", 1), R("p1", 1)]
for boundary in [None] + list(range(len(rebound))):
    lifecycle("rebound_plan_boundary_" + str(boundary), rebound, ["other"], {"p": [0, 1]}, {"p": "i"}, boundary, repeat=2)
lifecycle("rebound_completed_plan_no_new_receipt", [I(), I("other"), P(n=1), R("p0"), P("p", "other", 1)], ["other"], {"p": [0]}, {"p": "i"})
lifecycle("rebound_missing_first_owner", [P(), I("other"), P("p", "other"), R("p0"), R("p1", 1)], ["other"], {"p": [0, 1]}, {"p": "i"})
lifecycle("rebound_foreign_incident_only_receipt", base + [P("p", "other"), R("bad0", p="", i="other"), R("p1", 1)], ["i", "other"], {"p": [1]}, {"p": "i"})
lifecycle("prelinked_foreign_incident", [I(), P(), I("other", p="p"), R("bad0", p="", i="other"), R("p1", 1)], ["i", "other"], {"p": [1]}, {"p": "i"})
lifecycle("prelinked_foreign_plan_only_receipts", [I(), P(), I("other", p="p"), R("p0"), R("p1", 1)], ["other"], {"p": [0, 1]}, {"p": "i"})

# Late INCIDENT does not yet have a forward incident->plan link. An incident-only
# receipt addressed to the known owner must be applied, or kept pending (safe delay).
lifecycle("late_incident_plan_only_fresh", [P(), R("p0"), I(), R("p1", 1)], [], {"p": [0, 1]}, {"p": "i"})
lifecycle("late_incident_only_fresh", [P(), R("p0"), I(), R("p1", 1, p="", i="i")], [], {"p": [0, 1]}, {"p": "i"})
lifecycle("late_incident_after_completed_plan", [P(n=1), R("p0"), I()], [], {"p": [0]}, {"p": "i"})
lifecycle("late_incident_duplicate_plan_drains", [P(), R("p0"), I(), R("p1", 1, p="", i="i"), P()], [], {"p": [0, 1]}, {"p": "i"})

save("ownership-lifecycle.json", cases)

# Authentic older snapshots where the owner was not representable, or ambiguous.
old_owners = []
for ref, cls in (("e6afe16", Legacy), ("5de0d53", Prior)):
    for name, prefix, suffix, wanted_open, wanted_owner in (
        ("owner_missing_incident", [P(), I("other")], [P("p", "other"), R("x0", i="other"), R("x1", 1, i="other")], ["other"], None),
        ("ambiguous_incident_order", [I("other"), I(), P(), P("p", "other")], [R("x0", i="other"), R("x1", 1, i="other")], ["i", "other"], None),
        ("resolved_link_control", resolved[:5], resolved[5:], ["i"], {"p": "i", "q": "other"}),
    ):
        old = cls()
        for e in prefix:
            old.reduce(e)
        snap = old.snapshot()
        l = restore(restore(old))
        start = local(l)
        for e in suffix:
            l.reduce(e)
        end = local(l)
        passed = expect(end, wanted_open, owner=wanted_owner)
        old_owners.append(dict(name=ref + "_" + name, passed=passed, source_ref=ref,
            events_before=[e.to_dict() for e in prefix], events_after=[e.to_dict() for e in suffix],
            snapshot=snap, restored=start, final=end, expected_open=wanted_open,
            oracle="Do not invent a different authoritative owner when the old format lost first-PLAN ownership."))
save("authentic-old-ownership.json", old_owners)

# Agent namespaces: same plan/receipt IDs in another agent must not contribute.
h = new_hive()
h.register_agent("b")
for a, seq in (("a", [I(), P(), R("shared")]), ("b", [I("other"), P("p", "other"), R("shared"), R("b1", 1)])):
    for e in seq:
        h.reduce(HiveEvent(source_agent=a, original_event=e))
agent_case = dict(name="agent_namespace_control", passed=expect(hive(h, "a"), ["i"], {"p": [0]}) and
                 expect(hive(h, "b"), [], {"p": [0, 1]}), a=hive(h, "a"), b=hive(h, "b"))
save("agent-namespace.json", agent_case)

groups = dict(current_format=summary(current), prior_ordered_format=summary(ordered_old),
    legacy_fail_closed=summary(migrated), original_witnesses=summary(witnesses),
    stale_progress=summary(stale), ownership_lifecycle=summary(cases),
    authentic_old_ownership=summary(old_owners), agent_namespace=summary([agent_case]))
groups["failed_lifecycle_names"] = [r["name"] for r in cases if not r["passed"]]
groups["failed_old_owner_names"] = [r["name"] for r in old_owners if not r["passed"]]
save("semantic-summary.json", groups)
print(json.dumps(groups, indent=2))
sys.exit(int(any(v["failed"] for v in groups.values() if isinstance(v, dict))))
