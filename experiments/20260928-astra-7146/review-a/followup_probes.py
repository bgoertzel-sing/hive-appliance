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


# Independent 7133 contract checks; original semantic harness remains unchanged.
old_hive_path=E/'legacy-hive-e6afe16.py'
old_hive_path.write_bytes(subprocess.check_output(['git','show','e6afe16:hive/reducer.py'],cwd=SRC))
spec=importlib.util.spec_from_file_location('legacy_hive',old_hive_path)
old_hive=importlib.util.module_from_spec(spec);spec.loader.exec_module(old_hive)
cases={}
def check(name, seq, expected, restore_at=None, drop_owner=False, baseline=False):
    l=legacy.Reducer() if baseline else Reducer()
    h=old_hive.HiveReducer() if baseline else HiveReducer();h.register_agent('a')
    trace=[];agreement=True
    for j,e in enumerate(seq):
        feed(l,h,e)
        if j==restore_at:
            snap=json.loads(json.dumps(l.snapshot(),sort_keys=True))
            if drop_owner:snap.pop('plan_owner',None)
            l=Reducer();l.restore_snapshot(snap)
        s=state(l,h)
        same=all(s[k]==s['hive'][k] for k in ('open','verified','failed'))
        agreement &= same
        trace.append(dict(event=e.to_dict(),state=s,agreement=same,
          local_owner=getattr(l,'_plan_owner',{}).copy(),hive_owner=getattr(h,'_plan_owner',{}).copy(),
          links={i.id:i.plan_id for i in l.incidents}))
    cases[name]=dict(passed=s['open']==expected and s['hive']['open']==expected and agreement,
      expected_open=expected,agreement_every_event=agreement,trace=trace)

check('reregister_baseline',[I(),I('other'),P(),R('r0'),R('r1',1),P('p','other',2)],['other'],baseline=True)
# Authentic old producer snapshot, not merely deletion of a new field.
old=legacy.Reducer();h=new_hive();prefix=[P(),I(),I('other')]
for e in prefix:feed(old,h,e)
snap=json.loads(json.dumps(old.snapshot()));l=Reducer();l.restore_snapshot(snap)
trace=[]
for e in [R('r0'),R('bad1',1,i='other'),P()]:
 feed(l,h,e);trace.append(dict(event=e.to_dict(),state=state(l,h)))
out=dict(baseline=cases,authentic_ownerless=dict(snapshot=snap,trace=trace))
(E/'followup-results.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
