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
resolved=[I(),I('other'),P(),P('q','other',1),R('q0',p='q'),R('good0'),R('bad1',1,i='other')]
unlinked=[I(),I('other'),P(),R('good0'),R('bad1',1,i='other')]
for label,seq,want,boundary in [('resolved',resolved,['i'],4),('unlinked',unlinked,['i','other'],2)]:
    check(label+'_current',seq,want)
    check(label+'_snapshot',seq,want,restore_at=boundary)
    check(label+'_old_snapshot',seq,want,restore_at=boundary,drop_owner=True)
    check(label+'_baseline',seq,want,baseline=True)
check('foreign_owner', [I(),I('other'),P(),P('q','other',1),R('good0'),R('bad1',1,i='other')],['i','other'])
check('incident_only_owner',[I(),P(),R('r0',0,p='',i='i'),R('r1',1,p='',i='i')],[])
check('incident_only_unlinked',[I(),I('other'),P(),R('r0'),R('r1',1,p='',i='other')],['i','other'])
repeat=[I(),I('other'),P(),P('p','other',2)]
check('reregister_plan_only',repeat+[R('r0'),R('r1',1)],['other'])
check('reregister_incident_only',repeat+[R('r0',p='',i='other'),R('r1',1,p='',i='other')],['i','other'])
check('reregister_dual_address',repeat+[R('r0',i='other'),R('r1',1,i='other')],['i','other'])
check('reregister_after_complete',[I(),I('other'),P(),R('r0'),R('r1',1),P('p','other',2)],['other'])
check('reregister_snapshot',repeat+[R('r0'),R('r1',1)],['other'],restore_at=3)
# Restore an ownerless legacy snapshot whose PLAN preceded INCIDENT: no durable link to reconstruct.
check('old_snapshot_plan_before_incident',[P(),I(),I('other'),R('r0'),R('r1',1,i='other')],['i','other'],restore_at=2,drop_owner=True)
# Empty first PLAN owner is not frozen: ownership is first nonempty incident, not literally first PLAN.
check('first_plan_empty_owner',[I(),I('other'),P('p','',2),P('p','other',2),R('r0'),R('r1',1)],['i'])
# Exhaustive legacy fail-closed oracle, then new uniquely identified post-restore evidence.
vals=[(0,True),(0,False),(1,True),(1,False)];rows=[]
for order in itertools.permutations(range(4)):
 for mask in range(16):
  old=legacy.Reducer();old.reduce(I())
  for j in order:
   idx,ok=vals[j];old.reduce(R('r'+str(j),idx,ok,p='' if mask&(1<<j) else 'p',i='i' if mask&(1<<j) else ''))
  l=Reducer();l.restore_snapshot(json.loads(json.dumps(old.snapshot())));l.reduce(P());before=state(l)
  l.reduce(R('fresh0'));middle=state(l);l.reduce(R('fresh1',1));after=state(l)
  rows.append(dict(order=order,mask=mask,before=before,middle=middle,after=after,discarded=l.legacy_pending_discarded,
    passed=before['open']==['i'] and before['verified'].get('p',[])==[] and before['failed'].get('p',[])==[] and middle['open']==['i'] and after['open']==[]))
side=[]
for label,receipts in [('single_bucket',[R('a'),R('b',1)]),('one_per_step_mixed',[R('a'),R('b',1,p='',i='i')])]:
 old=legacy.Reducer();old.reduce(I())
 for r in receipts:old.reduce(r)
 l=Reducer();l.restore_snapshot(old.snapshot());l.reduce(P());snap=l.snapshot();l2=Reducer();l2.restore_snapshot(snap)
 side.append(dict(case=label,state=state(l),discarded=l.legacy_pending_discarded,
   counter_in_snapshot='legacy_pending_discarded' in snap,counter_after_second_restore=l2.legacy_pending_discarded))
out=dict(lifecycle=cases,legacy=dict(total=len(rows),passed=sum(r['passed'] for r in rows),closed_without_fresh=sum(not r['before']['open'] for r in rows)),discard_side_effects=side)
(E/'expanded-results.json').write_text(json.dumps(out,indent=2)+'\n')
(E/'legacy-fail-closed-cases.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(dict(lifecycle={k:{x:v[x] for x in ('passed','agreement_every_event')} for k,v in cases.items()},legacy=out['legacy'],discard_side_effects=side),indent=2))
sys.exit(int(any(not v['passed'] for k,v in cases.items() if not k.endswith('_baseline')) or not all(r['passed'] for r in rows)))
