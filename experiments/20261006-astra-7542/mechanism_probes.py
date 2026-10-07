"""Independent ef18db3 mechanism probes; outputs observations, not universal assertions."""
import os,sys,json,copy,importlib.util,logging
from pathlib import Path
E=Path(__file__).resolve().parent;sys.path.insert(0,os.environ['HIVE_SRC'])
from controller.reducer import Reducer
from hive.reducer import HiveReducer
from hive.types import HiveEvent
from schemas.types import Event,EventKind
from recovery.checkpoint import CheckpointManager
spec=importlib.util.spec_from_file_location('legacy',E/'legacy-reducer-e6afe16.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
def I(i='i',p='',resolved=False):return Event(kind=EventKind.INCIDENT,payload=dict(id=i,component='svc',symptom='down',severity='critical',plan_id=p,resolved=resolved))
def P(p='p',i='i',n=2):return Event(kind=EventKind.PLAN,payload=dict(id=p,incident_id=i,steps=[{}]*n))
def R(r,k=0,ok=True,p='p',i=''):return Event(kind=EventKind.RECEIPT,payload=dict(id=r,step_index=k,verified=ok,plan_id=p,incident_id=i))
def state(l):return dict(open=sorted(i.id for i in l.open_incidents()),verified={p:sorted(v) for p,v in l._plan_verified.items()},failed={p:sorted(v) for p,v in l._plan_failed_steps.items()},pending=copy.deepcopy(l._pending_receipts),owners=l._plan_owner.copy(),quarantine=sorted(l._owner_unproven),diagnostics=copy.deepcopy(l.migration_diagnostics))
def restore(l):r=Reducer();r.restore_snapshot(json.loads(json.dumps(l.snapshot())));return r
def lost(resolved=False,foreignlink=''):
 x=old.Reducer()
 for e in [P(),I(resolved=resolved),I('other',foreignlink)]:x.reduce(e)
 l=Reducer();l.restore_snapshot(x.snapshot());return l
out={};rows=[]
# Authentic disk fixtures: six linked/unlinked x repeated current/legacy restores.
for linked in [False,True]:
 for mode in ['direct','current_twice','legacy_twice']:
  x=old.Reducer()
  for e in [P(),R('old0'),R('old-failure',ok=False,p='',i='i'),I(p='p' if linked else '')]:x.reduce(e)
  m=CheckpointManager(E/'mechanism-checkpoints'/(( 'linked' if linked else 'unlinked')+'-'+mode));ck=m.create(x.snapshot(),label='linked' if linked else 'unlinked');s=m.load(ck.id).appliance_state
  l=Reducer();l.restore_snapshot(s)
  if mode=='current_twice':l=restore(restore(l))
  if mode=='legacy_twice':l.restore_snapshot(s)
  l.reduce(P());l.reduce(R('fresh1',1));before=state(l)
  rebound=l.rebind_plan_owner('p','i', actor='review7173', reason='legacy witness', allow_non_candidate=True) if not linked else None
  l.reduce(R('fresh0'));after=state(l)
  rows.append(dict(linked=linked,mode=mode,checkpoint=ck.id,before=before,rebound=rebound,after=after,passed=before['open']==['i'] and after['open']==[]))
out['disk_recovery']=rows
# rebind policy: outside quarantine, missing/foreign link, resolved and unlinked foreign targets.
rows=[]
for case in ['outside','missing','foreign_link','resolved','foreign_unlinked','twice','held_successes','held_failure']:
 l=lost(resolved=case=='resolved',foreignlink='q' if case=='foreign_link' else '')
 if case=='outside':l=Reducer();l.reduce(I());l.reduce(P())
 if case in ['held_successes','held_failure']:
  l.reduce(R('new0'));l.reduce(R('new1',1))
  if case=='held_failure':l.reduce(R('newerfail',0,False))
 before=state(l);target='missing' if case=='missing' else ('other' if case.startswith('foreign') else 'i')
 accepted=l.rebind_plan_owner('p',target, actor='review7173', reason='legacy witness', allow_non_candidate=True);second=l.rebind_plan_owner('p','other', actor='review7173', reason='legacy witness', allow_non_candidate=True);after=state(l);l=restore(restore(l))
 rows.append(dict(case=case,before=before,target=target,accepted=accepted,second=second,after=after,persisted=state(l)==after))
out['rebind']=rows
# Snapshot and audit bound: per-plan candidates cap eight; number plans and audit entries uncapped.
l=lost()
for j in range(32):l.reduce(P(i='candidate'+str(j)))
out['candidate_cap']=dict(count=len(l.migration_diagnostics['owner_candidates']['p']),state=state(l),restore_equal=state(restore(l))==state(l))
s=dict(state={},incidents=[I('i'+str(k)).payload for k in range(128)],plan_step_counts={'p'+str(k):1 for k in range(128)},plan_receipts={},plan_failed_steps={},pending_receipts={},seen_receipt_ids=[])
l=Reducer();l.restore_snapshot(s)
for k in range(128):l.reduce(P('p'+str(k),'i'+str(k),1))
candidates=len(l.migration_diagnostics['owner_candidates'])
for k in range(128):assert l.rebind_plan_owner('p'+str(k),'i'+str(k), actor='review7173', reason='recorded candidate')
out['global_bounds']=dict(plans=128,candidate_plan_keys=candidates,rebind_entries=len(l.migration_diagnostics['owner_rebinds']),legacy_ids=len(l.migration_diagnostics['legacy_ownerless_plans']),open=len(l.open_incidents()),restored_equal=state(restore(l))==state(l))
# Live pending/namespace controls: compare open IDs and step sets after EVERY event.
sequences={
'invalid_index':[I(),R('bad',None,p='',i='i'),P(),R('a'),R('b',1)],
'unknown_unrelated_plan':[I(),P(),R('stale',p='unknown'),R('a'),R('b',1)],
'foreign_dual':[I(),P(),R('bad',p='p',i='other'),R('a'),R('b',1)],
'foreign_agent':[I(),P(),R('a'),R('b',1)],
'multiple_owned_ambiguous':[P(),P('q'),R('fail',ok=False,p='',i='i'),R('a'),R('b',1),I()],
'late_incident_complete':[P(),R('a'),R('b',1),I()],
}
rows=[]
for name,seq in sequences.items():
 l=Reducer();h=HiveReducer();h.register_agent('a');h.register_agent('b');tr=[]
 if name=='foreign_agent':h.reduce(HiveEvent(source_agent='b',original_event=R('stale',ok=False,p='p',i='i')))
 def feed(e):
  l.reduce(e);h.reduce(HiveEvent(source_agent='a',original_event=e));a=state(l);b=dict(open=sorted(i['incident_id'] for i in h._open_agent_incidents('a')),verified={k[2:]:sorted(v) for k,v in h._plan_verified_steps.items() if k.startswith('a:')},failed={k[2:]:sorted(v) for k,v in h._plan_failed.items() if k.startswith('a:')},health=h.state.agents['a'].health.value,displayed_open=h.state.agents['a'].open_incidents)
  tr.append(dict(event=e.to_dict(),local=a,hive=b,agreement=all(a[k]==b[k] for k in ['open','verified','failed']) and len(a['open'])==b['displayed_open']))
 for e in seq:feed(e)
 initial=state(l)
 if name in ['multiple_owned_ambiguous','late_incident_complete']:
  feed(P());feed(R('fresh0'));feed(R('fresh1',1))
 rows.append(dict(case=name,initial=initial,final=state(l),trace=tr,agreement_every_event=all(t['agreement'] for t in tr)))
out['pending_liveness']=rows
# Full public rejection state, serialize every field safely to preserve evidence.
l=Reducer();h=HiveReducer();h.register_agent('a')
for e in [I(),I('other'),P(),R('waiting',p='',i='missing')]:l.reduce(e);h.reduce(HiveEvent(source_agent='a',original_event=e))
def serial(x):
 if isinstance(x,dict):return {str(k):serial(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,set)):return [serial(v) for v in x]
 if hasattr(x,'to_dict'):return x.to_dict()
 if hasattr(x,'__dict__'):return serial(vars(x))
 return x
before=copy.deepcopy([vars(l),vars(h)]);e=P(i='other');e.subject='svc';l.reduce(e);h.reduce(HiveEvent(source_agent='a',original_event=e));after=[vars(l),vars(h)]
out['rejected_full_state']=dict(before=serial(before),after=serial(after),changed=[[k for k in b if b[k]!=a[k]] for b,a in zip(before,after)])
(E/'mechanism-probes.json').write_text(json.dumps(out,indent=2,default=str));print(json.dumps({k:len(v) if isinstance(v,list) else v for k,v in out.items() if k not in ['rejected_full_state','candidate_cap']},default=str)[:4000])
