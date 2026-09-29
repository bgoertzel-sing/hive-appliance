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
out={}
# Public event entry points, including state/timestamps outside PLAN handler.
l=Reducer();h=HiveReducer();h.register_agent('a')
for e in [I(),I('other'),P(),R('waiting',i='missing',p='')]:l.reduce(e);h.reduce(HiveEvent(source_agent='a',original_event=e))
before=copy.deepcopy(l.__dict__);hb=copy.deepcopy(h.__dict__)
e=P('other','svc');l.reduce(e);h.reduce(HiveEvent(source_agent='a',original_event=e))
out['rejected_public_mutations']=dict(local_changed=[k for k in before if before[k]!=l.__dict__[k]],hive_changed=[k for k in hb if hb[k]!=h.__dict__[k]],local_before=before['state'],local_after=l.state,local_pending_unchanged=before['_pending_receipts']==l._pending_receipts,hive_pending_unchanged=hb['_pending_receipts']==h._pending_receipts)
# Authentic linked stale progress: INCIDENT supplies a durable link after buffering failure.
x=old.Reducer()
for e in [P(),R('old0'),R('failure',ok=False,p='',i='i'),I(p='p')]:x.reduce(e)
snap=x.snapshot();l=Reducer();l.restore_snapshot(snap);trace=[state(l)]
for e in [P(),R('fresh1',1)]:l.reduce(e);trace.append(state(l))
out['linked_stale_progress']=dict(snapshot=snap,trace=trace,passed=trace[-1]['open']==['i'])
# Quarantine legitimate recovery, including same-owner replay and repeated snapshots.
rows=[]
for mode in ['held_before_plan','fresh_after_plan','same_owner_replay']:
 x=old.Reducer();x.reduce(P());x.reduce(I());l=Reducer();l.restore_snapshot(x.snapshot());l=restore(restore(l));trace=[state(l)]
 seq=[R('new0'),R('new1',1),P()] if mode=='held_before_plan' else [P(),R('new0'),R('new1',1)]
 if mode=='same_owner_replay':seq=[P(),P(),R('new0'),P(),R('new1',1),P()]
 for e in seq:l.reduce(e);trace.append(state(l))
 rows.append(dict(mode=mode,passed=trace[-1]['open']==[],trace=trace))
out['quarantine_recovery']=rows
# Fresh receipts before any owner recovery stay held, never complete.
x=old.Reducer();x.reduce(P());x.reduce(I());l=Reducer();l.restore_snapshot(x.snapshot())
for e in [R('new0'),R('new1',1)]:l.reduce(e)
out['quarantine_without_plan']=state(l)
# Diagnostics no double count on current restores; cumulative new migration; logs.
l=Reducer();l.restore_snapshot(snap);first=copy.deepcopy(l.migration_diagnostics)
for _ in range(20):l=restore(l)
out['diagnostics_repeat']=dict(before=first,after=l.migration_diagnostics,equal=first==l.migration_diagnostics)
s=l.snapshot();s['pending_receipts']={'p':{'z':dict(id='z',plan_id='p',step_index=0,verified=False)}};l.restore_snapshot(s)
out['diagnostics_cumulative']=l.migration_diagnostics
# Size growth: ownerless-plan diagnostics have no cap (not multiplied by restores).
s=dict(state={},incidents=[],plan_step_counts={f'p{k}':1 for k in range(2048)},plan_receipts={},plan_failed_steps={},pending_receipts=[],seen_receipt_ids=[])
l=Reducer();l.restore_snapshot(s);out['diagnostics_bound']=dict(input_plans=2048,stored_plans=len(l.migration_diagnostics['legacy_ownerless_plans']),json_bytes=len(json.dumps(l.migration_diagnostics)))
(E/'new-risks.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
