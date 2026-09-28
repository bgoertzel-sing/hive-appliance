"""Independent semantic oracles, including authentic legacy snapshot migration.

Exit 1 means a semantic assertion failed; observations and traces are retained.
Agreement between reducers is recorded but is not the expected-behavior oracle.
"""
import importlib.util
import itertools
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
from recovery.checkpoint import CheckpointManager
from schemas.types import Event, EventKind

old_path = E / "legacy-reducer-e6afe16.py"
old_path.write_bytes(subprocess.check_output(["git", "show", "e6afe16:controller/reducer.py"], cwd=SRC))
spec = importlib.util.spec_from_file_location("legacy_reducer", old_path)
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)

def I(i="i", plan=""):
    return Event(kind=EventKind.INCIDENT, payload=dict(id=i, component="svc", symptom="down", severity="critical", plan_id=plan))

def P(p="p", i="i", n=2):
    return Event(kind=EventKind.PLAN, payload=dict(id=p, incident_id=i, steps=[{} for _ in range(n)]))

def R(r, idx=0, ok=True, p="p", i=""):
    return Event(kind=EventKind.RECEIPT, payload=dict(id=r, step_index=idx, verified=ok, plan_id=p, incident_id=i))

def state(l, h=None):
    out = dict(open=sorted(i.id for i in l.open_incidents()),
               verified={k: sorted(v) for k, v in l._plan_verified.items()},
               failed={k: sorted(v) for k, v in l._plan_failed_steps.items()})
    if h is not None:
        out["hive"] = dict(open=sorted(i["incident_id"] for i in h._open_agent_incidents("a")),
             verified={k[2:]: sorted(v) for k, v in h._plan_verified_steps.items()},
             failed={k[2:]: sorted(v) for k, v in h._plan_failed.items()},
             health=h.state.agents["a"].health.value,
             displayed_open=h.state.agents["a"].open_incidents)
    return out

def new_hive():
    h = HiveReducer()
    h.register_agent("a")
    return h

def feed(l, h, e):
    l.reduce(e)
    h.reduce(HiveEvent(source_agent="a", original_event=e))

def restored(l):
    snap = json.loads(json.dumps(l.snapshot(), sort_keys=True))
    other = Reducer()
    other.restore_snapshot(snap)
    return other

def matches(s, latest):
    return (s["open"] == ([] if all(latest.values()) else ["i"])
            and s["verified"].get("p", []) == sorted(k for k, v in latest.items() if v)
            and s["failed"].get("p", []) == sorted(k for k, v in latest.items() if not v))

current = []
migrated = []
vals = [(0, True), (0, False), (1, True), (1, False)]
for order in itertools.permutations(range(4)):
    for mask in range(16):
        stream = [I()]
        latest = {}
        for j in order:
            idx, ok = vals[j]
            latest[idx] = ok
            stream.append(R("r" + str(j), idx, ok, p="" if mask & (1 << j) else "p",
                            i="i" if mask & (1 << j) else ""))
        # Each prefix checkpoint precedes PLAN, including a checkpoint after INCIDENT.
        for boundary in range(5):
            l = Reducer()
            h = new_hive()
            prefix_ok = True
            for j, event in enumerate(stream):
                feed(l, h, event)
                if j == boundary:
                    l = restored(l)
                s = state(l, h)
                prefix_ok &= s["open"] == s["hive"]["open"] == ["i"]
                prefix_ok &= not s["verified"] and not s["failed"]
            feed(l, h, P())
            s = state(l, h)
            ok = prefix_ok and matches(s, latest) and matches(s["hive"], latest)
            current.append(dict(order=order, mask=mask, boundary=boundary, passed=ok, actual=s))
        old = legacy.Reducer()
        for event in stream:
            old.reduce(event)
        snap = json.loads(json.dumps(old.snapshot()))
        l = Reducer()
        l.restore_snapshot(snap)
        l.reduce(P())
        s = state(l)
        migrated.append(dict(order=order, mask=mask, passed=matches(s, latest),
            premature_resolution=bool(not s["open"] and not all(latest.values())),
            false_noncompletion=bool(s["open"] and all(latest.values())),
            expected_latest=latest, actual=s))

# A real legacy producer and real disk checkpoint preserve the counterexample.
prefix = [I(), R("seed1", 1), R("old_success", 0, p="", i="i"), R("new_failure", 0, False)]
old = legacy.Reducer()
l = Reducer()
h = new_hive()
for event in prefix:
    old.reduce(event)
    feed(l, h, event)
manager = CheckpointManager(str(E / "legacy-checkpoint"))
checkpoint = manager.create(old.snapshot(), label="old-producer-mixed-order")
loaded = manager.load(checkpoint.id)
m = Reducer()
m.restore_snapshot(loaded.appliance_state)
before = m.snapshot()
m.reduce(P())
feed(l, h, P())
legacy_witness = dict(events=[e.to_dict() for e in prefix] + [P().to_dict()],
    legacy_snapshot=loaded.appliance_state, migrated_before_plan=before,
    migrated_after_plan=state(m), uninterrupted_current=state(l, h),
    expected=dict(open=["i"], verified={"p": [1]}, failed={"p": [0]}))

# Distinct event interleavings can produce byte-identical legacy snapshots.
def legacy_snapshot(seq):
    r = legacy.Reducer()
    for event in seq:
        r.reduce(event)
    return r.snapshot()
alternate = [prefix[0], prefix[1], prefix[3], prefix[2]]
legacy_witness["opposite_latest_order_same_snapshot"] = legacy_snapshot(prefix) == legacy_snapshot(alternate)

cases = {}
def lifecycle(name, seq, expected, restore_at=None, cls=Reducer):
    l = cls()
    h = new_hive()
    trace = []
    for j, e in enumerate(seq):
        feed(l, h, e)
        if j == restore_at:
            l = restored(l)
        trace.append(dict(event=e.to_dict(), actual=state(l, h)))
    s = state(l, h)
    cases[name] = dict(passed=s["open"] == expected and s["hive"]["open"] == expected,
        expected_open=expected, restore_at=restore_at, trace=trace)

original_n4 = [I(), I("other"), R("bad", i="other"), R("good", 1),
               P("q", "other", 1), R("q0", p="q"), P()]
for boundary in range(len(original_n4)):
    lifecycle("original_n4_snapshot_" + str(boundary), original_n4, ["i"], boundary)

resolved_identity = [I(), I("other"), P(), P("q", "other", 1), R("q0", p="q"),
                     R("good0"), R("contradictory_after_resolution", 1, i="other")]
lifecycle("resolved_identity_current", resolved_identity, ["i"])
lifecycle("resolved_identity_snapshot", resolved_identity, ["i"], 4)
lifecycle("resolved_identity_baseline", resolved_identity, ["i"], cls=legacy.Reducer)
lifecycle("open_identity_control", [I(), I("other"), P(), P("q", "other", 1),
    R("good0"), R("contradictory_before_resolution", 1, i="other")], ["i", "other"])

# PLAN p explicitly names i; a dual-address receipt must not close unrelated other.
unlinked = [I(), I("other"), P(), R("good0"), R("bad1", 1, i="other")]
lifecycle("unlinked_identity_current", unlinked, ["i", "other"])
lifecycle("unlinked_identity_baseline", unlinked, ["i", "other"], cls=legacy.Reducer)

def summary(rows):
    return dict(total=len(rows), passed=sum(r["passed"] for r in rows), failed=sum(not r["passed"] for r in rows))
out = dict(current_snapshots=summary(current), legacy_migrations=summary(migrated),
    legacy_premature_resolution=sum(r["premature_resolution"] for r in migrated),
    legacy_false_noncompletion=sum(r["false_noncompletion"] for r in migrated),
    lifecycle=summary(list(cases.values())), lifecycle_failed=[k for k, v in cases.items() if not v["passed"]],
    legacy_witness=legacy_witness)
for name, value in (("semantic-current-snapshots.json", current), ("semantic-legacy-migrations.json", migrated),
                    ("semantic-lifecycle.json", cases), ("semantic-summary.json", out)):
    (E / name).write_text(json.dumps(value, indent=2) + "\n")
print(json.dumps(out, indent=2))
sys.exit(int(any(v["failed"] for v in (out["current_snapshots"], out["legacy_migrations"], out["lifecycle"]))))
