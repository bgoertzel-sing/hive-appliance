"""Causal baseline controls and late-event probes, separate from the first sweep.

All trace state is copied at capture time. The first sweep's local owner-map
trace references can reflect later map insertions; its final-state tests are
unaffected. Use this file's traces for intermediate ownership interpretation.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

E = Path(__file__).resolve().parent
SRC = Path(os.environ["HIVE_SRC"])
sys.path.insert(0, str(SRC))
from controller.reducer import Reducer
from hive.reducer import HiveReducer
from hive.types import HiveEvent
from schemas.types import Event, EventKind

def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

old_local = {ref: module(E / ("legacy-reducer-" + ref + ".py"), "local_" + ref).Reducer
             for ref in ("e6afe16", "5de0d53")}
old_hive = {}
for ref in old_local:
    path = E / ("legacy-hive-" + ref + ".py")
    with path.open("xb") as f:
        f.write(subprocess.check_output(["git", "show", ref + ":hive/reducer.py"], cwd=SRC))
    old_hive[ref] = module(path, "hive._review_" + ref).HiveReducer

def I(i="i", p=""):
    return Event(kind=EventKind.INCIDENT, ts=1700000000., payload=dict(id=i, ts=1700000000.,
        component="svc", symptom="down", severity="critical", plan_id=p))

def P(p="p", i="i", n=2):
    return Event(kind=EventKind.PLAN, payload=dict(id=p, incident_id=i, steps=[{} for _ in range(n)]))

def R(r, idx=0, ok=True, p="p", i=""):
    return Event(kind=EventKind.RECEIPT, payload=dict(id=r, step_index=idx, verified=ok, plan_id=p, incident_id=i))

def capture(l, h=None):
    out = dict(open=sorted(i.id for i in l.open_incidents()),
        verified={k: sorted(v) for k, v in l._plan_verified.items()},
        failed={k: sorted(v) for k, v in l._plan_failed_steps.items()},
        links={i.id: i.plan_id for i in l.incidents},
        owner=copy.deepcopy(getattr(l, "_plan_owner", {})),
        pending=copy.deepcopy(l._pending_receipts),
        discarded=getattr(l, "legacy_pending_discarded", None))
    if h:
        out["hive"] = dict(open=sorted(i["incident_id"] for i in h._open_agent_incidents("a")),
            verified={k: sorted(v) for k, v in h._plan_verified_steps.items()},
            failed={k: sorted(v) for k, v in h._plan_failed.items()},
            owner=copy.deepcopy(getattr(h, "_plan_owner", {})),
            pending=copy.deepcopy(h._pending_receipts),
            health=h.state.agents["a"].health.value,
            displayed_open=h.state.agents["a"].open_incidents)
    return out

rows = []
def run(name, seq, opened, cls=Reducer, hcls=HiveReducer, ref="623c92b", snapshot=None, boundary=None):
    l, h = cls(), hcls() if hcls else None
    if h:
        h.register_agent("a")
    if snapshot is not None:
        l.restore_snapshot(copy.deepcopy(snapshot))
    trace = [dict(event=None, state=capture(l, h))]
    for j, e in enumerate(seq):
        l.reduce(e)
        if h:
            h.reduce(HiveEvent(source_agent="a", original_event=e))
        if j == boundary:
            for _ in range(2):
                snap = json.loads(json.dumps(l.snapshot(), sort_keys=True))
                l = Reducer()
                l.restore_snapshot(snap)
        trace.append(dict(event=e.to_dict(), state=capture(l, h)))
    state = capture(l, h)
    passed = state["open"] == opened and (h is None or state["hive"]["open"] == opened)
    row = dict(name=name, ref=ref, passed=passed, expected_open=opened,
               snapshot=snapshot, boundary=boundary, final=state, trace=trace)
    rows.append(row)
    return row

stale_prefix = [P(), R("stale_success"), R("later_failure", ok=False, p="", i="i"), I()]
old = old_local["e6afe16"]()
for e in stale_prefix:
    old.reduce(e)
snapshot = old.snapshot()
for ref, cls in (("e6afe16", old_local["e6afe16"]), ("5de0d53", old_local["5de0d53"]), ("623c92b", Reducer)):
    run("stale_legacy_migration", [P(), R("fresh1", 1)], ["i"], cls, None, ref, snapshot)

rebound = [I(), I("other"), P(n=1), R("p0"), P("p", "other", 1)]
late_pending = stale_prefix + [R("fresh1", 1)]
late_pending_after = [P(), R("stale_success"), I(), R("later_failure", ok=False, p="", i="i"), R("fresh1", 1)]
late_incident_only = [P(), R("p0"), I(), R("p1", 1, p="", i="i")]
late_completed = [P(n=1), R("p0"), I()]
for ref, cls, hcls in (("e6afe16", old_local["e6afe16"], old_hive["e6afe16"]),
                       ("5de0d53", old_local["5de0d53"], old_hive["5de0d53"]),
                       ("623c92b", Reducer, HiveReducer)):
    for name, seq, opened in (("completed_plan_rebound", rebound, ["other"]),
            ("late_pending_failure", late_pending, ["i"]),
            ("late_pending_failure_after_incident", late_pending_after, ["i"]),
            ("late_incident_only_liveness", late_incident_only, []),
            ("late_incident_after_completion_liveness", late_completed, [])):
        run(name, seq, opened, cls, hcls, ref)

for boundary in range(len(late_pending)):
    run("late_pending_failure_current_boundary_" + str(boundary), late_pending,
        ["i"], boundary=boundary)
run("late_pending_failure_duplicate_plan_no_reopen", late_pending + [P()], ["i"])
run("late_pending_failure_duplicate_plan_before_success_control", stale_prefix + [P(), R("fresh1", 1)], ["i"])
run("late_pending_failure_fresh_retry_control", stale_prefix + [P(), R("fresh1", 1), R("fresh0")], [])

# The two formats genuinely omit first owner: both opposite histories yield the
# same serialized old snapshot, so choosing incident-list order cannot recover it.
ambiguous = []
for ref, cls in old_local.items():
    snaps = []
    for first, second in (("i", "other"), ("other", "i")):
        l = cls()
        for e in [I("other"), I(), P("p", first), P("p", second)]:
            l.reduce(e)
        snaps.append(l.snapshot())
    ambiguous.append(dict(ref=ref, equal_bytes=json.dumps(snaps[0], sort_keys=True) == json.dumps(snaps[1], sort_keys=True), snapshots=snaps))
assert all(r["equal_bytes"] for r in ambiguous)

out = dict(cases=rows, identical_old_owner_snapshots=ambiguous,
    summary={ref: dict(total=len(sub), passed=sum(r["passed"] for r in sub), failed=sum(not r["passed"] for r in sub))
        for ref in ("e6afe16", "5de0d53", "623c92b") for sub in [[r for r in rows if r["ref"] == ref]]})
with (E / "focused-witnesses.json").open("x") as f:
    json.dump(out, f, indent=2)
    f.write("\n")
print(json.dumps(out["summary"], indent=2))
sys.exit(int(any(not r["passed"] for r in rows if r["ref"] == "623c92b")))
