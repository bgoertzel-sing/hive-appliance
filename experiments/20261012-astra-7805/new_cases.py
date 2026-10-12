"""Independent ordered-stream probes. Failures are retained while all cases run.
No production edits. Assertions compare identity, counts, progress and health after every event.
"""
import itertools,json,pathlib,sys,traceback
E=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(pathlib.Path(__import__('os').environ.get('HIVE_SRC', str(E.parent.parent)))))
from schemas.types import Event,EventKind
from controller.reducer import Reducer
from hive.reducer import HiveReducer
from hive.types import HiveEvent

def I(i='i'):
 return Event(kind=EventKind.INCIDENT,payload=dict(id=i,component='svc',symptom='s',severity='critical'))
def P(p='p',i='i',n=2):
 return Event(kind=EventKind.PLAN,payload=dict(id=p,incident_id=i,steps=[{} for _ in range(n)]))
def R(r,idx=0,ok=True,p='p',i=''):
 d=dict(id=r,step_index=idx,verified=ok)
 if p:d['plan_id']=p
 if i:d['incident_id']=i
 return Event(kind=EventKind.RECEIPT,payload=d)
O={}
def run(name,seq,expect=None,restore_at=None):
 l=Reducer();h=HiveReducer();h.register_agent('a');log=[];errors=[]
 for j,e in enumerate(seq):
  l.reduce(e);h.reduce(HiveEvent(source_agent='a',original_event=e))
  if j==restore_at:
   snap=json.loads(json.dumps(l.snapshot()));l=Reducer();l.restore_snapshot(snap)
   assert l.snapshot()==snap
  lo=sorted(i.id for i in l.open_incidents());hi=sorted(i['incident_id'] for i in h._open_agent_incidents('a'))
  lv={k:sorted(v) for k,v in l._plan_verified.items()};hv={k[2:]:sorted(v) for k,v in h._plan_verified_steps.items()}
  lf={k:sorted(v) for k,v in l._plan_failed_steps.items()};hf={k[2:]:sorted(v) for k,v in h._plan_failed.items()}
  row=dict(event=j,kind=e.kind.value,payload=e.payload,local_open=lo,hive_open=hi,local_verified=lv,hive_verified=hv,local_failed=lf,hive_failed=hf,hive_health=h.state.agents['a'].health.value)
  log.append(row)
  try:
   assert lo==hi,('open incident identity mismatch',lo,hi)
   assert len(hi)==h.state.agents['a'].open_incidents
   assert lv==hv,('verified step mismatch',lv,hv)
   assert lf==hf,('failed step mismatch',lf,hf)
   if expect is not None:
    assert len(lo)==len(hi)==expect[j],('expected count',expect[j],len(lo),len(hi))
  except AssertionError as ex:errors.append(dict(event=j,error=str(ex)))
 O[name]=dict(passed=not errors,errors=errors,events=log,restore_at=restore_at)

run('failure_success_buffer',[I(),R('f',0,False),R('r',0),R('1',1),P()],[1,1,1,1,0])
run('multiple_failures_retry_after',[I(),R('0',0),R('1',1),R('f0',0,False),R('f1',1,False),P(),R('r0',0),R('r0',0),P(),R('r1',1),P()],[1]*9+[0,0])
run('retry_before_plan_duplicate_failure',[I(),R('f0',0,False),R('f1',1,False),R('r0',0),R('r1',1),R('f0',0,False),R('r0',0),P(),P()],[1]*7+[0,0])
run('neither_identity',[I(),P(),R('x',0,p=''),R('y',1,p='')],[1]*4)
run('two_plans_one_incident',[I(),R('p0'),R('q0',p='q'),R('q1',1,p='q'),P('q'),P(),R('p1',1),P('q')],[1,1,1,1,0,0,0,0])
run('two_plans_one_incident_failure',[I(),R('p0'),R('q0',p='q'),R('qf',1,False,p='q'),P('q'),P(),R('p1',1),R('qretry',1,p='q'),P()],[1]*6+[0,0,0])
run('incident_only_then_other_plan',[I(),I('other'),R('a',p='',i='i'),P('p','other',1),P('q','i',1)],[1,2,2,2,1])
run('incident_only_then_other_plan_restore',[I(),I('other'),R('a',p='',i='i'),P('p','other',1),P('q','i',1)],[1,2,2,2,1],restore_at=2)
run('contradiction_created_while_buffered',[I(),I('other'),R('a',0,i='other'),R('b',1),P('q','other',1),P(),R('clean',0)],[1,2,2,2,2,2,1])
run('contradiction_created_buffer_restored',[I(),I('other'),R('a',0,i='other'),R('b',1),P('q','other',1),P(),R('clean',0)],[1,2,2,2,2,2,1],restore_at=3)
run('buffered_failure_snapshot',[I(),R('0'),R('1',1),R('f',0,False),P(),R('retry')],[1,1,1,1,1,0],restore_at=3)
# Split addressing modes: receipt order must survive combining buffers.
run('mixed_early_incident_success_late_plan_failure',[I(),R('is',p='',i='i'),R('pf',ok=False),R('1',1),P(),R('retry')],[1,1,1,1,1,0])
run('mixed_early_incident_failure_late_plan_success',[I(),R('if',ok=False,p='',i='i'),R('ps'),R('1',1),P(),R('retry')],[1,1,1,1,0,0])
run('mixed_success_failure_snapshot',[I(),R('is',p='',i='i'),R('pf',ok=False),R('1',1),P(),R('retry')],[1,1,1,1,1,0],restore_at=3)
# Exhaust all orderings of two successes and two failures, with varying addressing.
for mask in range(16):
 vals=[(0,True),(0,False),(1,True),(1,False)]
 for order in itertools.permutations(range(4)):
  seq=[I()];latest={}
  for k in order:
   idx,ok=vals[k];latest[idx]=ok
   seq.append(R('r'+str(k),idx,ok,p='' if mask&(1<<k) else 'p',i='i' if mask&(1<<k) else ''))
  seq.append(P())
  expected=[1]*5+[0 if all(latest.values()) else 1]
  run('permutation_mask_%02d_order_%s'%(mask,''.join(map(str,order))),seq,expected)
(E/'new-cases.json').write_text(json.dumps(O,indent=2))
summary={'total':len(O),'pass':sum(v['passed'] for v in O.values()),'fail':sum(not v['passed'] for v in O.values()),'failed_names':[k for k,v in O.items() if not v['passed']]}
(E/'new-cases-summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2));sys.exit(bool(summary['fail']))
