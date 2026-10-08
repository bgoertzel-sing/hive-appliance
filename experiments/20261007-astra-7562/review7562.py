"""Independent scope/authority/retention probes. No production edits."""
import copy, hashlib, inspect, io, itertools, json, logging, os, sys, textwrap, traceback
from pathlib import Path
from unittest.mock import patch
E=Path(__file__).resolve().parent
sys.path.insert(0,os.environ['HIVE_SRC'])
raw=(E/'review7542.py').read_text();defs=raw[:raw.index('\nout={}\n')]
a={'__file__':str(E/'review7542.py'),'__name__':'retained7542'}
exec(compile(defs,str(E/'review7542.py'),'exec'),a)
Reducer,HiveReducer,HiveEvent,Event,I,P,R,rt,new,replay,opens=[a[k] for k in ['Reducer','HiveReducer','HiveEvent','Event','I','P','R','rt','new','replay','opens']]
(E/'extractions7562.json').write_text(json.dumps(dict(source='review7542.py',selection='prefix before newline out={} newline',sha256=hashlib.sha256(defs.encode()).hexdigest(),groups=['ownerless','owned_positive','health_boundaries'],nested_source='review7519.py',nested_groups=['quarantine','schedules','foreign','health']),indent=2))

def bothreduce(l,h,e):l.reduce(e);h.reduce(HiveEvent(source_agent='a1',original_event=e))
def snapshots(l,h):return dict(local=l.snapshot(),hive_owners=copy.deepcopy(h._plan_owner),local_reasons=l.quarantine_reasons(),hive_reasons=h.quarantine_reasons(),open=opens(l,h))
class Capture(logging.Handler):
 def __init__(self):super().__init__();self.records=[]
 def emit(self,r):self.records.append(dict(level=r.levelname,name=r.name,message=r.getMessage()))

def visibility(row):
 results=[]
 for links in [1,2]:
  events={'I':I('i','p'),'P':P('p','',1),'R':R()}
  if links==2:events['J']=I('j','p')
  for order in itertools.permutations(events):
   for restart in [False,True]:
    l,h=new();hist=[];seen=set();trace=[]
    for key in list(order)+['R','P','I']:
     e=events[key];hist.append(e);seen.add(key);bothreduce(l,h,e)
     if restart:l=rt(l);h=replay(hist)
     expected=sorted(('i' if k=='I' else 'j') for k in seen if k in ['I','J'])
     reason=bool(expected) and 'P' in seen
     assert opens(l,h)==(expected,expected)
     assert l.quarantine_reasons()==({'p':'ownerless_linked'} if reason else {})
     assert h.quarantine_reasons()==({'a1:p':'ownerless_linked'} if reason else {})
     assert not l._plan_owner and not h._plan_owner
     detached=l.quarantine_reasons();detached.clear();assert bool(l.quarantine_reasons())==reason
     trace.append(dict(event=key,open=expected,visible=reason))
    e=P('p','i',1);hist.append(e);bothreduce(l,h,e)
    if restart:l=rt(l);h=replay(hist)
    expected=['j'] if links==2 else []
    assert opens(l,h)==(expected,expected)
    assert not l.quarantine_reasons() and not h.quarantine_reasons()
    results.append(dict(links=links,order=order,restart=restart,trace=trace,repaired_open=expected))
 (E/'visibility-schedules.json').write_text(json.dumps(results,indent=2))
 row.update(schedules=len(results),per_event_checks=sum(len(x['trace']) for x in results),repairs=len(results))
 # Distinct clearing: another owned plan closes every incident linked to p,
 # while p itself remains ownerless. No sticky reason after the last closes.
 l,h=new();hist=[];states=[]
 for e in [I('i','p'),I('j','p'),P('p','',1),R(),P('q','i',1),R('q0','q'),P('s','j',1),R('s0','s')]:
  hist.append(e);bothreduce(l,h,e);l=rt(l);h=replay(hist);states.append(snapshots(l,h))
 assert not l._plan_owner.get('p') and not h._plan_owner.get('a1:p')
 assert states[5]['local_reasons']=={'p':'ownerless_linked'}
 assert not states[-1]['local_reasons'] and not states[-1]['hive_reasons']
 assert opens(l,h)==([],[])
 row['other_owned_plan_closure']=states
 # Genuine unlinked and owned controls, complete and incomplete.
 controls=[]
 for owner,linked,n in [('',False,1),('i',True,2),('i',True,1)]:
  l,h=new()
  for e in [I('i','p' if linked else ''),P('p',owner,n),R()]:bothreduce(l,h,e)
  assert not l.quarantine_reasons() and not h.quarantine_reasons()
  controls.append(dict(owner=owner,linked=linked,steps=n,open=opens(l,h)))
 row['controls']=controls

def warning_and_repair(row):
 handler=Capture();logs=[logging.getLogger(n) for n in ['controller.reducer','hive.reducer']];levels=[x.level for x in logs]
 for log in logs:log.setLevel(logging.WARNING);log.addHandler(handler)
 try:
  l,h=new();hist=[];states=[]
  for e in [I('i','p'),I('j','p'),P('p','',1),R()]:
   hist.append(e);bothreduce(l,h,e);l=rt(l);h=replay(hist);states.append(snapshots(l,h))
  msgs=copy.deepcopy(handler.records)
  for name in ['controller.reducer','hive.reducer']:
   assert any(x['name']==name and x['level']=='WARNING' and "'i'" in x['message'] and "'j'" in x['message'] and 'no proven owner' in x['message'] for x in msgs)
  refusals=[]
  for override in [False,True]:
   before=copy.deepcopy(l.snapshot());pv=l.preview_rebind('p','i',allow_non_candidate=override)
   assert not pv['allowed'] and pv['refusal']=='plan is not quarantined'
   assert not l.rebind_plan_owner('p','i',actor='Astra-7562',reason='isolated fixture',allow_non_candidate=override)
   assert l.snapshot()==before;refusals.append(pv)
  handler.records.clear();e=P('p','i',1);bothreduce(l,h,e);hist.append(e);l=rt(l)
  assert opens(l,h)==(['j'],['j']);assert not l.migration_diagnostics.get('owner_rebinds')
  assert not handler.records
  row.update(witness=states,warnings=msgs,previews=refusals,repair=snapshots(l,h),repair_warning_or_audit_records=handler.records,hive_has_rebind=hasattr(h,'rebind_plan_owner'))
  handler.records.clear();l,h=new()
  for e in [P('p','',1),R(),I('i','p'),I('j','p')]:bothreduce(l,h,e)
  assert not handler.records and l.quarantine_reasons()=={'p':'ownerless_linked'} and h.quarantine_reasons()=={'a1:p':'ownerless_linked'}
  row['completion_before_links']=dict(visible=True,warnings=handler.records,qualification='No completion trigger after late links; accessor still reports them')
 finally:
  for log,lev in zip(logs,levels):log.removeHandler(handler);log.setLevel(lev)

def authority(row):
 controls=[]
 for source in ['', 'untrusted-other-agent']:
  l,h=new()
  for e in [I('i','p'),I('j','p'),P('p','',1),R()]:bothreduce(l,h,e)
  e=P('p','i',1);e.source=source;bothreduce(l,h,e)
  assert opens(l,h)==(['j'],['j']) and not l.migration_diagnostics
  controls.append(dict(event_source=source,assigned_hive_namespace='a1',open=opens(l,h),audit=l.migration_diagnostics))
 row['ordinary_event_sources']=controls
 # A differently namespaced agent cannot set the original agent's owner.
 from hive.event_bus import HiveEventBus
 class Adapter:
  def __init__(self,event):self.event=event
  def events_since(self,cursor):return [self.event], '1'
 l,h=new()
 for e in [I('i','p'),P('p','',1),R()]:bothreduce(l,h,e)
 bus=HiveEventBus();e=P('p','i',1);e.source='a1';bus.register_adapter('a2',Adapter(e));ev=bus.poll_agent('a2')[0];h.reduce(ev)
 assert ev.source_agent=='a2' and not h._plan_owner.get('a1:p') and h._plan_owner['a2:p']=='i'
 assert opens(l,h)==(['i'],['i'])
 row['bus_namespace_control']=dict(envelope=ev.source_agent,claimed_event_source=e.source,hive_owners=h._plan_owner,original_agent_open=['i'])
 # Legacy contrast via real historical serializers, not hand-injected marker.
 old=a['prior']['Legacy']();old.reduce(P('p','i',1));old.reduce(I('i','p'))
 previous=a['prior']['Previous']();previous.restore_snapshot(json.loads(json.dumps(old.snapshot())))
 current=Reducer();current.restore_snapshot(json.loads(json.dumps(previous.snapshot())))
 current.reduce(R());current.reduce(P('p','i',1))
 assert current.quarantined_plans()==['p'] and not current._plan_owner
 assert current.migration_diagnostics['owner_candidates']['p']==['i']
 assert current.open_incidents()
 preview=current.preview_rebind('p','i');assert preview['allowed'] and preview['would_close']==['i']
 for actor,reason in [('', 'fixture'),('Astra-7562','')]:
  try:current.rebind_plan_owner('p','i',actor=actor,reason=reason)
  except ValueError:pass
  else:raise AssertionError('blank actor/reason accepted')
 assert current.rebind_plan_owner('p','i',actor='Astra-7562',reason='fixture ownership evidence')
 assert not current.open_incidents();assert current.migration_diagnostics['owner_rebinds'][0]['closed']==['i']
 row['legacy_contrast']=dict(preview=preview,audit=current.migration_diagnostics['owner_rebinds'],current_reasons=current.quarantine_reasons())
 # Ordinary appliance record_plan logs a PLAN but not an operator authorization.
 from controller.appliance import Appliance
 from schemas.types import Plan,IncidentReport,Receipt
 app=Appliance()
 for e in [I('i','p'),I('j','p'),P('p','',1),R()]:app.store.append(e);app.reducer.reduce(e)
 plan=Plan.from_dict(dict(id='p',incident_id='i',steps=[{}]));app.record_plan(plan)
 event=app.store.query(kind='plan')[-1]
 assert event.source=='planner' and [x.id for x in app.open_incidents()]==['j']
 assert not app.reducer.migration_diagnostics.get('owner_rebinds')
 row['event_store']=dict(last_plan=event.to_dict(),owner_rebinds=app.reducer.migration_diagnostics.get('owner_rebinds',[]),qualification='Ordinary event persistence exists; no operator actor/reason/preview/effect audit')
 app.close()

def caps(row):
 from hive.reducer import MAX_AGENT_INCIDENTS
 from controller.reducer import MAX_DIAG_ENTRIES
 l,h=new()
 for k in range(600):
  for e in [I('i'+str(k),'p'+str(k)),P('p'+str(k),'',1)]:bothreduce(l,h,e)
 assert len(l.quarantine_reasons())==600 and len(h.quarantine_reasons())==500
 assert 'p0' in l.quarantine_reasons() and 'a1:p0' not in h.quarantine_reasons()
 assert not h._plan_owner and len(h._plan_steps)==600
 local_before=l.quarantine_reasons();l=rt(l);assert l.quarantine_reasons()==local_before
 # Per-agent cap, not a global quarantine cap.
 h.register_agent('a2')
 for k in range(600):
  for e in [I('i'+str(k),'p'+str(k)),P('p'+str(k),'',1)]:h.reduce(HiveEvent(source_agent='a2',original_event=e))
 assert len(h.quarantine_reasons())==1000
 row.update(local_live=600,local_restored=600,hive_one_agent=500,hive_two_agents=1000,historical_diagnostic_cap=MAX_DIAG_ENTRIES,incident_history_cap_per_agent=MAX_AGENT_INCIDENTS,local_cap=None,hive_global_cap=None,missing_first_open='a1:p0',hive_missing_count_per_agent=100,old_plan_metadata_retained=True)
 # All retained entries clear through legitimate alternative owned closure.
 for k in range(600):
  for e in [P('q'+str(k),'i'+str(k),1),R('q'+str(k),'q'+str(k))]:bothreduce(l,h,e)
 assert not l.quarantine_reasons() and len(h.quarantine_reasons())==500
 h.unregister_agent('a2');assert not h.quarantine_reasons()
 row.update(after_a1_incidents_closed=dict(local=0,hive=500),after_a2_unregister=0)

def composite(row):
 import importlib.util
 spec=importlib.util.spec_from_file_location('p0',Path(os.environ['HIVE_SRC'])/'tests/test_p0_fixes.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 t=m.TestF7CompositeReceipt();names=['test_single_receipt_does_not_resolve','test_partial_failure_does_not_resolve','test_all_receipts_resolve']
 for name in names:getattr(t,name)()
 raw=inspect.getsource(Reducer._maybe_resolve);old='        if len(self._plan_verified.get(plan_id, ())) != n:\n            return\n';assert raw.count(old)==1
 env={};exec(textwrap.dedent(raw.replace(old,'')),env)
 caught=[];survive=[]
 with patch.object(Reducer,'_maybe_resolve',env['_maybe_resolve']):
  for name in names:
   try:getattr(t,name)()
   except AssertionError:caught.append(name)
   else:survive.append(name)
 assert caught==names[:2] and survive==names[2:]
 row.update(unmutated_passed=names,identical_7542_mutant='remove only all-step cardinality return',caught=caught,survived=survive)

# Suppress routine warning volume for thousands of intentionally hostile fixtures.
logging.getLogger().setLevel(logging.CRITICAL)
out={}
groups=[('ownerless_safety',a['ownerless']),('owned_positive',a['owned_positive']),('visibility',visibility),('warning_and_repair',warning_and_repair),('authority',authority),('caps',caps),('F7_mutant',composite),('quarantine',a['prior']['quarantine']),('policy_schedules',a['prior']['schedules']),('foreign_owner',a['prior']['foreign']),('health_mutations',a['prior']['health']),('health_boundaries',a['health_boundaries'])]
for name,fn in groups:
 r={}
 try:fn(r);r['passed']=True
 except Exception as ex:r.update(passed=False,error=repr(ex),traceback=traceback.format_exc())
 out[name]=r;print(name,json.dumps(r),flush=True)
(E/'review7562.json').write_text(json.dumps(out,indent=2)+'\n')
sys.exit(not all(r['passed'] for r in out.values()))
