import copy, json, os, sys, importlib.util, logging
from pathlib import Path
E=Path(__file__).resolve().parent
sys.path.insert(0,os.environ['HIVE_SRC'])
from controller.reducer import Reducer
from hive.reducer import HiveReducer
from hive.types import HiveEvent
from schemas.types import Event,EventKind
spec=importlib.util.spec_from_file_location('old',E/'legacy-reducer-e6afe16.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
def I(i='i',p=''):return Event(kind=EventKind.INCIDENT,payload=dict(id=i,component='svc',symptom='down',severity='critical',plan_id=p))
def P(i='i',subject=''):return Event(kind=EventKind.PLAN,subject=subject,payload=dict(id='p',incident_id=i,steps=[{},{}]))
def R(r,k=0,ok=True,p='p',i=''):return Event(kind=EventKind.RECEIPT,payload=dict(id=r,step_index=k,verified=ok,plan_id=p,incident_id=i))
def state(l):return dict(open=sorted(i.id for i in l.open_incidents()),verified={p:sorted(v) for p,v in l._plan_verified.items()},pending=copy.deepcopy(l._pending_receipts),owner=l._plan_owner.copy(),quarantine=sorted(l._owner_unproven),diag=copy.deepcopy(l.migration_diagnostics))
def restore(l):r=Reducer();r.restore_snapshot(json.loads(json.dumps(l.snapshot())));return r
from recovery.checkpoint import CheckpointManager
out={}; rows=[]
for after in [False,True]:
 seq=[P(),R('s0'),I(),R('f0',ok=False,p='',i='i'),R('s1',1)] if after else [P(),R('s0'),R('f0',ok=False,p='',i='i'),I(),R('s1',1)]
 for boundary in [None,-1,0,1,2,3,4]:
  l=Reducer();h=HiveReducer();h.register_agent('a');trace=[]
  if boundary==-1:l=restore(restore(l))
  for j,e in enumerate(seq):
   l.reduce(e);h.reduce(HiveEvent(source_agent='a',original_event=e))
   if j==boundary:l=restore(restore(l))
   a=state(l);b=dict(open=sorted(i['incident_id'] for i in h._open_agent_incidents('a')),verified={k[2:]:sorted(v) for k,v in h._plan_verified_steps.items()},failed={k[2:]:sorted(v) for k,v in h._plan_failed.items()},pending=copy.deepcopy(h._pending_receipts),health=h.state.agents['a'].health.value)
   same=a['open']==b['open'] and a['verified']==b['verified'] and {k:sorted(v) for k,v in l._plan_failed_steps.items()}==b['failed']
   trace.append(dict(event=e.to_dict(),local=a,hive=b,agreement=same))
  rows.append(dict(failure_after_incident=after,boundary=boundary,passed=trace[-1]['local']['open']==['i'],agreement_every_event=all(t['agreement'] for t in trace),trace=trace))
out['n8']=rows
x=old.Reducer()
seq=[P(),R('old0'),R('failure',ok=False,p='',i='i'),I(p='p')]
for e in seq:x.reduce(e)
s=x.snapshot();m=CheckpointManager(E/'linked-stale-checkpoints');c=m.create(s,label='authentic-linked-stale');saved=m.load(c.id).appliance_state
l=Reducer();l.restore_snapshot(saved);l=restore(restore(l));baseline=old.Reducer();baseline.restore_snapshot(saved)
for e in [P(),R('fresh1',1)]:l.reduce(e);baseline.reduce(e)
out['linked_stale_disk_control']=dict(events=[e.to_dict() for e in seq],snapshot=s,checkpoint=c.id,current=state(l),baseline_open=sorted(i.id for i in baseline.open_incidents()),baseline_verified={k:sorted(v) for k,v in baseline._plan_verified.items()},baseline_failed={k:sorted(v) for k,v in baseline._plan_failed_steps.items()})
(E/'boundary-and-disk.json').write_text(json.dumps(out,indent=2));print(json.dumps(dict(n8_total=len(rows),n8_passed=sum(r['passed'] for r in rows),agreement=sum(r['agreement_every_event'] for r in rows),linked_stale=out['linked_stale_disk_control']),indent=2))
