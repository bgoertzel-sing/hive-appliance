"""Isolate information loss using identical, fully specified incident records."""
import importlib.util
import json
import os
from pathlib import Path
import sys

E = Path(__file__).resolve().parent
sys.path.insert(0, os.environ["HIVE_SRC"])
from controller.reducer import Reducer
from schemas.types import Event, EventKind

spec = importlib.util.spec_from_file_location("legacy", E / "legacy-reducer-e6afe16.py")
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)

incident = Event(kind=EventKind.INCIDENT, payload=dict(id="i", ts=1700000000.0,
    component="svc", symptom="down", severity="critical"))
plan = Event(kind=EventKind.PLAN, payload=dict(id="p", incident_id="i", steps=[{}, {}]))
seed = Event(kind=EventKind.RECEIPT, payload=dict(id="seed1", plan_id="p", step_index=1, verified=True))
success = Event(kind=EventKind.RECEIPT, payload=dict(id="old_success", incident_id="i", step_index=0, verified=True))
failure = Event(kind=EventKind.RECEIPT, payload=dict(id="new_failure", plan_id="p", step_index=0, verified=False))

rows = []
snapshots = []
for label, stream, expected in (
    ("latest_failure", [incident, seed, success, failure], ["i"]),
    ("latest_success", [incident, seed, failure, success], []),
):
    old = legacy.Reducer()
    live = Reducer()
    for e in stream:
        old.reduce(e)
        live.reduce(e)
    snap = old.snapshot()
    snapshots.append(json.dumps(snap, indent=2))
    migrated = Reducer()
    migrated.restore_snapshot(json.loads(snapshots[-1]))
    migrated.reduce(plan)
    live.reduce(plan)
    rows.append(dict(label=label, expected_open=expected,
        live_open=[i.id for i in live.open_incidents()],
        migrated_open=[i.id for i in migrated.open_incidents()],
        migrated_verified=sorted(migrated._plan_verified["p"]),
        migrated_failed=sorted(migrated._plan_failed_steps["p"]),
        legacy_snapshot=snap))
assert snapshots[0] == snapshots[1], "Fixtures must show actual legacy information loss"
assert all(r["live_open"] == r["expected_open"] for r in rows)
out = dict(identical_legacy_snapshot_bytes=True, cases=rows,
    note="The first semantic run compared incidental generated incident timestamps too. This follow-up fixes ts explicitly; it does not overwrite the earlier observation.")
(E / "legacy-information-loss.json").write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out, indent=2))
sys.exit(int(any(r["migrated_open"] != r["expected_open"] for r in rows)))
