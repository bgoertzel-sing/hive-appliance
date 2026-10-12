"""Independent review 7542; literal/event-derived expectations and operability probes."""
import copy, hashlib, importlib.util, io, itertools, json, logging, os, sys, traceback
from pathlib import Path
from unittest.mock import patch
E=Path(__file__).resolve().parent
sys.path.insert(0,os.environ['HIVE_SRC'])
from controller.reducer import Reducer
from hive.reducer import HiveReducer
from hive.types import HiveEvent, AgentHealth
from schemas.types import Event, EventKind
# Execute only definitions from unchanged prior helper. Its old defect assertions
# are intentionally NOT invoked. Raw retained file + extraction hash are evidence.
raw=(E/'review7519.py').read_text();defs=raw[:raw.index('\nout={}\n')]
prior={'__file__':str(E/'review7519.py'),'__name__':'retained7519'}
exec(compile(defs,str(E/'review7519.py'),'exec'),prior)
(E/'retained-extraction.json').write_text(json.dumps(dict(source='review7519.py',selection='prefix before newline out={} newline',sha256=hashlib.sha256(defs.encode()).hexdigest(),groups=['quarantine','schedules','foreign','health']),indent=2))
I,P,R,rt,A=[prior[k] for k in ['I','P','R','rt','A']]
def opens(l,h):return sorted(i.id for i in l.open_incidents()),sorted(i['incident_id'] for i in h._open_agent_incidents('a1'))
def new():
 l=Reducer();h=HiveReducer();h.register_agent('a1');return l,h
def replay(history):
 h=HiveReducer();h.register_agent('a1')
 for e in history:h.reduce(HiveEvent(source_agent='a1',original_event=Event.from_dict(json.loads(json.dumps(e.to_dict())))))
 return h

def ownerless(row):
 rows=[]
 for addressing in ['plan','incident','dual']:
  for links in [1,2]:
   events={'I':I('i','p'),'P':P('p','',1),'R':R('x','' if addressing=='incident' else 'p',i='i' if addressing!='plan' else '')}
   if links==2:events['J']=I('j','p')
   for order in itertools.permutations(events):
    for restart in [False,True]:
     l,h=new();history=[];seen=set();trace=[]
     for key in list(order)+['R','P','I']:
      e=events[key];history.append(e);seen.add(key)
      expected=sorted(('i' if k=='I' else 'j') for k in seen if k in ['I','J'])
      l.reduce(e);h.reduce(HiveEvent(source_agent='a1',original_event=e))
      before=opens(l,h);assert before==(expected,expected),(addressing,order,key,before)
      if restart:l=rt(l);h=replay(history)
      assert opens(l,h)==(expected,expected)
      assert not l._plan_owner and not h._plan_owner
      assert h.state.agents['a1'].health.value==('failed' if expected else 'unknown')
      trace.append(dict(event=key,open=expected,local_restored=restart,hive_prefix_replayed=restart))
     rows.append(dict(addressing=addressing,links=links,order=order,restart=restart,trace=trace))
 (E/'ownerless-schedules.json').write_text(json.dumps(rows,indent=2))
 # The exact 7519 witness including restore after every event.
 l,h=new();hist=[];w=[]
 for e in [I('i','p'),I('j','p'),P('p','',1),R()]:
  hist.append(e);l.reduce(e);h.reduce(HiveEvent(source_agent='a1',original_event=e));l=rt(l);h=replay(hist)
  w.append(dict(event=e.to_dict(),local_open=opens(l,h)[0],hive_open=opens(l,h)[1],local_snapshot=l.snapshot()))
 assert opens(l,h)==(['i','j'],['i','j'])
 (E/'ownerless-witness.json').write_text(json.dumps(w,indent=2))
 row.update(schedules=len(rows),per_event_checks=sum(len(x['trace']) for x in rows),exact_witness_open=['i','j'],hive_has_snapshot_api=hasattr(h,'snapshot'))

def owned_positive(row):
 results=[]
 for addressing in ['plan','incident','dual']:
  for restart in [False,True]:
   l,h=new();hist=[]
   seq=[I('i','p'),I('j','p'),P('p','i',2),R('a','' if addressing=='incident' else 'p',i='i' if addressing!='plan' else ''),R('b','' if addressing=='incident' else 'p',k=1,i='i' if addressing!='plan' else '')]
   for k,e in enumerate(seq):
    hist.append(e);l.reduce(e);h.reduce(HiveEvent(source_agent='a1',original_event=e))
    if restart:l=rt(l);h=replay(hist)
    expected=['i'] if k==0 else (['j'] if k==4 else ['i','j'])
    assert opens(l,h)==(expected,expected)
   results.append(dict(addressing=addressing,restart=restart,open=['j']))
 row['controls']=results

def operability(row):
 captured=[]
 class Handler(logging.Handler):
  def emit(self,r):captured.append(dict(level=r.levelname,name=r.name,message=r.getMessage()))
 logs=[logging.getLogger(n) for n in ['controller.reducer','hive.reducer']];handler=Handler();levels=[x.level for x in logs]
 for log in logs:log.setLevel(logging.DEBUG);log.addHandler(handler)
 try:
  l,h=new();hist=[]
  for e in [I('i','p'),I('j','p'),P('p','',1),R()]:
   hist.append(e);l.reduce(e);h.reduce(HiveEvent(source_agent='a1',original_event=e));l=rt(l);h=replay(hist)
  normal_logs=copy.deepcopy(captured)
  assert not [x for x in normal_logs if x['level'] in ['WARNING','ERROR','CRITICAL']]
  assert l.quarantined_plans()==[] and not l._owner_unproven and not l.migration_diagnostics
  assert not l._pending_receipts and not h._pending_receipts.get('a1',{})
  assert l._plan_verified['p']=={0} and h._plan_verified_steps['a1:p']=={0}
  previews=[]
  for override in [False,True]:
   before=l.snapshot();pv=l.preview_rebind('p','i',allow_non_candidate=override)
   assert not pv['allowed'] and pv['refusal']=='plan is not quarantined'
   assert not l.rebind_plan_owner('p','i',actor='Astra-7542',reason='fixture repair probe',allow_non_candidate=override)
   assert before==l.snapshot();previews.append(dict(override=override,preview=pv))
  row.update(current_snapshot=l.snapshot(),hive_owner_map=h._plan_owner.copy(),hive_verified={'a1:p':sorted(h._plan_verified_steps['a1:p'])},normal_logs=normal_logs,previews=previews,hive_rebind_api=hasattr(h,'rebind_plan_owner'),hive_quarantine_api=hasattr(h,'quarantined_plans'))
  # Not permanently unrecoverable: ordinary first NONEMPTY owner PLAN works.
  e=P('p','i',1);l.reduce(e);h.reduce(HiveEvent(source_agent='a1',original_event=e));l=rt(l)
  assert opens(l,h)==(['j'],['j']) and l._plan_owner=={'p':'i'}
  assert not l.migration_diagnostics.get('owner_rebinds')
  row['ordinary_plan_repair']=dict(open=['j'],local_owner=l._plan_owner,hive_owner=h._plan_owner,local_audit=l.migration_diagnostics,uses_old_progress=True)
  # Known linked ownerless plans consume receipts, not an unbounded pending hold.
  growth=[]
  for addressing in ['plan','incident','dual']:
   l,h=new()
   for e in [I('i','p'),P('p','',1)]:l.reduce(e);h.reduce(HiveEvent(source_agent='a1',original_event=e))
   for k in range(1024):
    e=R('bulk'+str(k),'' if addressing=='incident' else 'p',i='i' if addressing!='plan' else '')
    l.reduce(e);h.reduce(HiveEvent(source_agent='a1',original_event=e))
   l=rt(l)
   assert opens(l,h)==(['i'],['i']) and not l._pending_receipts and not h._pending_receipts.get('a1',{})
   assert len(l._seen_receipt_ids)==1024 and len(h._seen_receipts)==1024
   growth.append(dict(addressing=addressing,unique_receipts=1024,pending_local=0,pending_hive=0,seen_ids_local=1024,seen_ids_hive=1024))
  l,h=new()
  for e in [I('i','p')]+[R('late'+str(k)) for k in range(1024)]:l.reduce(e);h.reduce(HiveEvent(source_agent='a1',original_event=e))
  assert len(l._pending_receipts)==1024==len(h._pending_receipts['a1'])
  l=rt(l);e=P('p','',1);l.reduce(e);h.reduce(HiveEvent(source_agent='a1',original_event=e))
  assert not l._pending_receipts and not h._pending_receipts['a1'] and opens(l,h)==(['i'],['i'])
  row['pending_growth_controls']=growth;row['late_plan_pending_before_after']=[1024,0]
  row['all_logs']=captured
 finally:
  for log,level in zip(logs,levels):log.removeHandler(handler);log.setLevel(level)

def health_boundaries(row):
 cases=[('first_resolved',[I(resolved=True)],'unknown'),('two_resolved',[I(resolved=True),I('j',resolved=True)],'unknown'),('same_event_open_close',[P(n=1),R(),I(sev='warn')],'healthy'),('resolved_then_open',[I(resolved=True),I('w',sev='warn')],'degraded')]
 results=[]
 for name,stream,expected in cases:
  l,h=A.both(stream);assert h.state.agents['a1'].health.value==expected
  results.append(dict(name=name,health=expected))
 row['boundaries']=results
 # Explicit no-hive-input oracle check: same local state/expected previous health
 # produces same answer irrespective of poisoning all hive health values.
 l,h=new();e=I(resolved=True);l.reduce(e);h.reduce(HiveEvent(source_agent='a1',original_event=e))
 for forced in AgentHealth:
  h.state.agents['a1'].health=forced
  assert A.expected_health(l,AgentHealth.UNKNOWN,False)==AgentHealth.UNKNOWN
 row['poisoned_hive_health_values_independent']=4

def composite(row):
 spec=importlib.util.spec_from_file_location('p0',Path(os.environ['HIVE_SRC'])/'tests/test_p0_fixes.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 test=m.TestF7CompositeReceipt();names=['test_single_receipt_does_not_resolve','test_all_receipts_resolve','test_partial_failure_does_not_resolve']
 for name in names:getattr(test,name)()
 # Mutation skips only the all-step cardinality guard, preserving ownership.
 # Recompile one function in memory, no source change.
 import inspect,textwrap
 raw=inspect.getsource(Reducer._maybe_resolve)
 old='        if len(self._plan_verified.get(plan_id, ())) != n:\n            return\n'
 assert raw.count(old)==1
 env={};exec(textwrap.dedent(raw.replace(old,'')),env)
 surviving=[]
 with patch.object(Reducer,'_maybe_resolve',env['_maybe_resolve']):
  for name in names:getattr(test,name)();surviving.append(name)
  l=Reducer()
  for e in [I(),P(n=2),R()]:l.reduce(e)
  assert not l.open_incidents() # Independent owned partial-plan control detects mutant.
 row.update(unmutated_passed=names,skip_all_steps_guard_mutant_survives=surviving,independent_owned_partial_control_detects_mutant=True)

out={}
for name,fn in [('ownerless',ownerless),('owned_positive',owned_positive),('quarantine',prior['quarantine']),('policy_schedules',prior['schedules']),('foreign_owner',prior['foreign']),('health_mutations',prior['health']),('health_boundaries',health_boundaries),('operability',operability),('composite',composite)]:
 row={}
 try:fn(row);row['passed']=True
 except Exception as ex:row.update(passed=False,error=repr(ex),traceback=traceback.format_exc())
 out[name]=row;print(name,json.dumps(row),flush=True)
(E/'review7542.json').write_text(json.dumps(out,indent=2)+'\n')
sys.exit(not all(x['passed'] for x in out.values()))
