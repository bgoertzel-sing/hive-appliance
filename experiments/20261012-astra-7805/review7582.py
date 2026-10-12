"""Independent 7582 event witnesses; observations explicitly separated from conformance checks."""
import copy, inspect, itertools, json, logging, os, sys, textwrap, traceback
from pathlib import Path
from unittest.mock import patch
E=Path(__file__).resolve().parent
sys.path.insert(0,os.environ['HIVE_SRC'])
from controller.reducer import Reducer
from hive.reducer import HiveReducer
from hive.types import HiveEvent
from schemas.types import Event, EventKind
logging.getLogger().setLevel(logging.CRITICAL)
def I(i='i',p='',resolved=False):return Event(kind=EventKind.INCIDENT,payload=dict(id=i,plan_id=p,resolved=resolved,component='svc',symptom='down',severity='critical'))
def P(p='p',i='',n=1):return Event(kind=EventKind.PLAN,payload=dict(id=p,incident_id=i,steps=[{} for _ in range(n)]))
def R(r='x',p='p',i='',k=0,ok=True):return Event(kind=EventKind.RECEIPT,payload=dict(id=r,plan_id=p,incident_id=i,step_index=k,verified=ok))
def new():
 l=Reducer();h=HiveReducer();h.register_agent('a1');return l,h

def feed(l,h,e):l.reduce(e);h.reduce(HiveEvent(source_agent='a1',original_event=e))
def rt(l):
 n=Reducer();n.restore_snapshot(json.loads(json.dumps(l.snapshot())));return n

def replay(hist):
 h=HiveReducer();h.register_agent('a1')
 for d in json.loads(json.dumps([e.to_dict() for e in hist])):h.reduce(HiveEvent(source_agent='a1',original_event=Event.from_dict(d)))
 return h

def opens(l,h):return [sorted(i.id for i in l.open_incidents()),sorted(i['incident_id'] for i in h._open_agent_incidents('a1'))]
def view(l,h):return dict(open=opens(l,h),holds=[l.quarantine_reasons(),h.quarantine_reasons()],owners=[dict(l._plan_owner),dict(h._plan_owner)],candidates=[copy.deepcopy(l.migration_diagnostics.get('owner_candidates',{})),copy.deepcopy(h.owner_candidates)],audits=[copy.deepcopy(l.migration_diagnostics.get('owner_rebinds',[])),copy.deepcopy(h.owner_rebinds)])
def preview(l,h,i='i',override=False):
 b=copy.deepcopy((vars(l),business(h)));pv=l.preview_rebind('p',i,allow_non_candidate=override);hv=h.preview_rebind('a1','p',i,allow_non_candidate=override)
 assert (vars(l),business(h))==b
 saved=copy.deepcopy((pv,hv));pv['candidates'].append('mutated');hv['held_receipts'].append({'id':'mutated'});assert (vars(l),business(h))==b
 return saved

def business(h):
 return {k:v for k,v in vars(h).items() if k not in ['last_rebind_result','_rebind_op_id']}

def rebind(l,h,i='i',override=False):
 return [l.rebind_plan_owner('p',i,actor='Astra-7582',reason='fixture authority',allow_non_candidate=override),bool(h.rebind_plan_owner('a1','p',i,actor='Astra-7582',reason='fixture authority',allow_non_candidate=override))]
def witness(row):
 hist=[I('i','p'),I('j','p'),P(),R(),P(i='i')];l,h=new();trace=[]
 for e in hist:feed(l,h,e);l=rt(l);h=replay(hist[:len(trace)+1]);trace.append(view(l,h))
 assert opens(l,h)==[['i','j'],['i','j']]
 pv,hv=preview(l,h);assert pv['hold_reason']==hv['hold_reason']=='ownerless_linked';assert pv['would_close']==hv['would_close']==['i'];assert pv['candidates']==hv['candidates']==['i'];assert pv['held_receipts']==hv['held_receipts']==[]
 assert rebind(l,h)==[True,True];assert opens(l,h)==[['j'],['j']];assert not l.quarantined_plans() and not h.quarantined_plans()
 assert l.migration_diagnostics['owner_rebinds'][-1]['closed']==h.owner_rebinds[-1]['closed']==['i']
 row.update(events=[e.to_dict() for e in hist],trace=trace,preview=[pv,hv],rebound=view(l,h),restored_local=view(rt(l),h),hive_event_replay_after_rebind=view(l,replay(hist)))
 assert replay(hist).quarantined_plans()==['a1:p'];assert replay(hist).owner_candidates=={'a1:p':['i']};assert not replay(hist).owner_rebinds
 row['restart_interpretation']='Fresh empty hive loses everything. Full serialized event replay re-derives holds and candidates but not operator rebind/audit (not events). Local snapshot retains rebind/audit.'

def schedules(row):
 rows=[]
 for address in ['plan','incident','dual']:
  for order in itertools.permutations(['I','J','P','R']):
   for restart in [False,True]:
    ev={'I':I('i','p'),'J':I('j','p'),'P':P(),'R':R(p='' if address=='incident' else 'p',i='i' if address!='plan' else '')};l,h=new();hist=[];seen=set()
    for key in list(order)+['P','R','I']:
     e=ev[key];hist.append(e);seen.add(key);feed(l,h,e)
     if restart:l=rt(l);h=replay(hist)
     expected=sorted(x.lower() for x in seen if x in ['I','J']);assert opens(l,h)==[expected,expected]
     held='P' in seen and bool(expected);assert l.quarantined_plans()==(['p'] if held else []);assert h.quarantined_plans()==(['a1:p'] if held else [])
    e=P(i='i');feed(l,h,e);hist.append(e)
    if restart:l=rt(l);h=replay(hist)
    assert opens(l,h)==[['i','j'],['i','j']];pv,hv=preview(l,h);assert pv['would_close']==hv['would_close']==['i'];assert rebind(l,h)==[True,True];assert opens(l,h)==[['j'],['j']]
    rows.append(dict(address=address,order=order,restart=restart))
 row.update(schedules=len(rows),per_event_checks=len(rows)*8,rows=rows)
 # Re-send ownership before any link exists is not HELD; later linkage does not unset proven owner.
 l,h=new()
 for e in [P(),R(),P(i='i'),I('i','p'),I('j','p')]:feed(l,h,e)
 assert opens(l,h)==[['j'],['j']];row['never_held_owner_before_late_link']=view(l,h)
 # No owner declared before linking: hold is derived when INCIDENT arrives.
 l,h=new()
 for e in [P(),R(),I('i','p'),P(i='i')]:feed(l,h,e)
 assert opens(l,h)==[['i'],['i']] and l.quarantined_plans()==['p'];row['late_link_then_resend']=view(l,h)

def refusals_and_pending(row):
 l,h=new()
 for e in [I('i','p'),I('j'),I('closed','',True),I('other','q'),P(),R(p='',i='j'),P(i='j')]:feed(l,h,e)
 pv,hv=preview(l,h,'j');assert [r['id'] for r in pv['held_receipts']]==[r['id'] for r in hv['held_receipts']]==['x'];assert pv['would_close']==hv['would_close']==['j']
 checks=[]
 for target,allow in [('missing',True),('closed',True),('other',True),('i',False)]:
  b=copy.deepcopy((vars(l),business(h)));p=preview(l,h,target,allow);assert not p[0]['allowed'] and not p[1]['allowed'];assert rebind(l,h,target,allow)==[False,False];assert (vars(l),business(h))==b;checks.append(p)
 for actor,reason in [('', 'r'),(' ','r'),('op',''),('op',None)]:
  for fn,args in [(l.rebind_plan_owner,('p','j')),(h.rebind_plan_owner,('a1','p','j'))]:
   try:fn(*args,actor=actor,reason=reason)
   except ValueError:pass
   else:raise AssertionError('invalid authority accepted')
 assert rebind(l,h,'j')==[True,True];assert opens(l,h)==[['i','other'],['i','other']]
 row.update(preview=[pv,hv],refusals=checks,rebound=view(l,h))
 # Receipt after rebind has normal owner isolation.
 l,h=new()
 for e in [I('i','p'),I('j','p'),P(n=2),P(i='i'),R(k=0)]:feed(l,h,e)
 assert rebind(l,h)==[True,True];feed(l,h,R('foreign',i='j',k=1));assert opens(l,h)==[['i','j'],['i','j']];feed(l,h,R('valid',i='i',k=1));assert opens(l,h)==[['j'],['j']]
 row['receipts_after_rebind']=view(l,h)

def foreign_progress(row):
 rows=[]
 for address in ['incident','dual']:
  for restart in [False,True]:
   l,h=new();hist=[I('i','p'),I('j','p'),P(),R(p='' if address=='incident' else 'p',i='j'),P(i='i')]
   for e in hist:feed(l,h,e)
   if restart:l=rt(l);h=replay(hist)
   pv,hv=preview(l,h);assert pv['held_receipts']==hv['held_receipts']==[]
   assert rebind(l,h)==[True,True]
   # This captures the defect, not desired acceptance behavior.
   assert opens(l,h)==[['j'],['j']]
   rows.append(dict(address=address,restart=restart,events=[e.to_dict() for e in hist],preview=[pv,hv],actual=view(l,h),expected_open=['i','j']))
 row.update(defect_reproduced=True,severity='High',cases=rows,interpretation='Receipt naming j before ownership was proven is irreversibly credited to p and then closes i on rebind; identical receipt after i ownership is rejected. Receipt identity lost in verified-index set, no revalidation.')

def unhold(row):
 l,h=new();trace=[];hist=[I('i','p'),P(),R(),P(i='i'),P('q','i'),R('q0','q'),I('k'),P(i='k')]
 for e in hist:feed(l,h,e);trace.append(view(l,h))
 assert trace[3]['holds']==[{'p':'ownerless_linked'},{'a1:p':'ownerless_linked'}]
 assert trace[5]['holds']==[{},{}] and trace[5]['owners'][0].get('p') is None
 assert opens(l,h)==[[],[]] and l._plan_owner['p']==h._plan_owner['a1:p']=='k';assert not l.migration_diagnostics.get('owner_rebinds') and not h.owner_rebinds
 row.update(events=[e.to_dict() for e in hist],trace=trace,severity='Medium',interpretation='Derived current hold evaporates after last linked incident legitimately resolves through owned sibling q. Formerly HELD p then accepts ordinary PLAN owner k and old receipt closes new k without audit. Explicit persistent-ever-held contract absent; document or retain latch.')
 # Existing hive INCIDENT resolution path clears hold without local counterpart.
 l,h=new()
 for e in [I('i','p'),P(),R(),P(i='i'),I('i','p',True),I('k'),P(i='k')]:feed(l,h,e)
 row['resolved_incident_update']=view(l,h);assert opens(l,h)==[['i','k'],[]]

def isolation_and_caps(row):
 l,h=new();h.register_agent('a2')
 for a in ['a1','a2']:
  for e in [I('i','p'),I('j','p'),P(),R(),P(i='i' if a=='a1' else 'j')]:h.reduce(HiveEvent(source_agent=a,original_event=e))
 assert h.owner_candidates=={'a1:p':['i'],'a2:p':['j']};assert not h.rebind_plan_owner('a2','p','i',actor='op',reason='fixture')
 assert h.rebind_plan_owner('a1','p','i',actor='op',reason='fixture');assert h.quarantined_plans()==['a2:p'];assert sorted(i['incident_id'] for i in h._open_agent_incidents('a2'))==['i','j'];assert h.owner_candidates=={'a2:p':['j']}
 row['per_agent']=dict(candidates=h.owner_candidates,audit=h.owner_rebinds,holds=h.quarantined_plans())
 l,h=new()
 for k in range(600):
  for e in [I('i'+str(k),'p'+str(k)),P('p'+str(k)),P('p'+str(k),'i'+str(k))]:feed(l,h,e)
 assert len(l.quarantined_plans())==len(h.quarantined_plans())==600
 assert len(l.migration_diagnostics['owner_candidates'])==256 and l.migration_diagnostics['owner_candidates_dropped']==344 and len(h.owner_candidates)==600
 l=rt(l);assert len(l.quarantined_plans())==600
 row['capacity']=dict(local_holds=600,hive_holds=600,local_candidate_keys=256,hive_candidate_keys=600,local_candidate_drop_count=344,restored_local_holds=len(l.quarantined_plans()),hive_open=len(h._open_agent_incidents('a1')))
 assert not l.preview_rebind('p599','i599')['allowed'];assert h.preview_rebind('a1','p599','i599')['allowed'];assert l.preview_rebind('p599','i599',True)['allowed']
 for k in range(270):
  assert l.rebind_plan_owner('p'+str(k),'i'+str(k),actor='op',reason='cap fixture',allow_non_candidate=True)
  assert h.rebind_plan_owner('a1','p'+str(k),'i'+str(k),actor='op',reason='cap fixture',allow_non_candidate=True)
 assert len(l.migration_diagnostics['owner_rebinds'])==256 and len(h.owner_rebinds)==200
 assert l.migration_diagnostics['owner_rebinds_total']==h.owner_rebinds_total==270
 assert len(l.quarantined_plans())==len(h.quarantined_plans())==330
 row['audit_caps']=dict(local=256,hive=200,total=270,current_holds=330)
 for k in range(12):
  feed(l,h,P('p599','candidate'+str(k)))
 assert len(l.migration_diagnostics['owner_candidates']['p599'])==len(h.owner_candidates['a1:p599'])==8
 row['candidates_per_plan_cap']=8
 # Resolved history trimming on insertion (not immediately upon receipt closure).
 h=HiveReducer();h.register_agent('a1')
 for k in range(550):h.reduce(HiveEvent(source_agent='a1',original_event=I('r'+str(k),resolved=True)))
 h.reduce(HiveEvent(source_agent='a1',original_event=I('open')));assert len(h._agent_incidents['a1'])==500
 row['resolved_retained_with_one_open']=500

def warnings(row):
 records=[]
 class Capture(logging.Handler):
  def emit(self,r):records.append(dict(name=r.name,level=r.levelname,message=r.getMessage()))
 handler=Capture();logs=[logging.getLogger(n) for n in ['controller.reducer','hive.reducer']]
 for log in logs:log.setLevel(logging.WARNING);log.addHandler(handler)
 try:
  l,h=new()
  for e in [P(),R(),I('i','p'),I('j','p')]:feed(l,h,e)
  assert opens(l,h)==[['i','j'],['i','j']]
  assert any(x['name']=='controller.reducer' and 'no proven owner' in x['message'] for x in records);assert any(x['name']=='hive.reducer' and 'no proven owner' in x['message'] for x in records)
  for k in range(500):h.reduce(HiveEvent(source_agent='a1',original_event=I('overflow'+str(k))))
  assert any('retained past the cap' in x['message'] for x in records)
  row['warnings']=records
 finally:
  for log in logs:log.removeHandler(handler);log.setLevel(logging.NOTSET)

def retained(row):
 raw=(E/'review7542.py').read_text();defs=raw[:raw.index('\nout={}\n')];a={'__file__':str(E/'review7542.py'),'__name__':'retained7542'};exec(compile(defs,str(E/'review7542.py'),'exec'),a)
 for name,fn in [('P3-ownerless',a['ownerless']),('owned_positive',a['owned_positive']),('legacy_300',a['prior']['quarantine']),('owned_1440',a['prior']['schedules']),('foreign_owned',a['prior']['foreign']),('H-oracle_mutants',a['prior']['health']),('health_boundaries',a['health_boundaries'])]:
  result={};fn(result);row[name]=result
 # F7 mutants independently remove completeness and failure guard, one at a time.
 import importlib.util
 spec=importlib.util.spec_from_file_location('p0',Path(os.environ['HIVE_SRC'])/'tests/test_p0_fixes.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);t=m.TestF7CompositeReceipt();names=['test_single_receipt_does_not_resolve','test_partial_failure_does_not_resolve','test_all_receipts_resolve']
 for name in names:getattr(t,name)()
 raw=inspect.getsource(Reducer._maybe_resolve);mutants={'completeness':raw.replace('        if len(self._plan_verified.get(plan_id, ())) != n:\n            return\n',''),'failure':raw.replace('if not n or self._plan_failed_steps.get(plan_id):','if not n:')}
 results={}
 for label,src in mutants.items():
  env={};exec(textwrap.dedent(src),env);caught=[]
  with patch.object(Reducer,'_maybe_resolve',env['_maybe_resolve']):
   for name in names:
    try:getattr(t,name)()
    except AssertionError:caught.append(name)
  results[label]=caught
 assert results['completeness']==names[:2]
 row['F7_mutants']=results

out={}
for name,fn in [('witness_and_restart',witness),('hold_schedules',schedules),('refusals_pending',refusals_and_pending),('foreign_progress_defect',foreign_progress),('non_audited_unhold',unhold),('isolation_and_caps',isolation_and_caps),('late_link_and_capacity_warnings',warnings),('retained_regressions',retained)]:
 r={}
 try:fn(r);r['passed']=True
 except Exception as ex:r.update(passed=False,error=repr(ex),traceback=traceback.format_exc())
 out[name]=r;print(name,r['passed'],r.get('error',''),flush=True)
(E/'review7582.json').write_text(json.dumps(out,indent=2,default=str)+'\n')
sys.exit(not all(r['passed'] for r in out.values()))
