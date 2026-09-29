"""Recheck only six intermediate owner records affected by recorder aliasing.

This does not rerun pytest or ordering sweeps and preserves the initial evidence.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys

E = Path(__file__).resolve().parent
sys.path.insert(0, os.environ["HIVE_SRC"])
from controller.reducer import Reducer
from schemas.types import Event

initial = json.loads((E / "authentic-old-ownership.json").read_text())
corrected = []
for row in initial:
    ref = row["source_ref"]
    spec = importlib.util.spec_from_file_location("old_" + ref, E / ("legacy-reducer-" + ref + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    old = mod.Reducer()
    for event in row["events_before"]:
        old.reduce(Event.from_dict(event))
    assert old.snapshot() == row["snapshot"]
    l = Reducer()
    l.restore_snapshot(json.loads(json.dumps(old.snapshot())))
    l.restore_snapshot(json.loads(json.dumps(l.snapshot(), sort_keys=True)))
    restored = copy.deepcopy(l.snapshot())
    for event in row["events_after"]:
        l.reduce(Event.from_dict(event))
    final = copy.deepcopy(l.snapshot())
    assert final["plan_owner"] == row["final"]["owner"]
    assert sorted(i.id for i in l.open_incidents()) == row["final"]["open"]
    corrected.append(dict(name=row["name"], initial_semantic_passed=row["passed"],
        restored_snapshot=restored, final_snapshot=final,
        final_matches_original=True,
        intermediate_owner_record_corrected=restored["plan_owner"] != row["restored"]["owner"]))
with (E / "corrected-old-owner-traces.json").open("x") as f:
    json.dump(corrected, f, indent=2)
    f.write("\n")
print(json.dumps(dict(cases=len(corrected), intermediate_owner_corrections=sum(
    r["intermediate_owner_record_corrected"] for r in corrected), all_final_results_unchanged=True)))
