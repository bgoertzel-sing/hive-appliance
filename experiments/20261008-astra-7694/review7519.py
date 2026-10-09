"""Independent 7519 acceptance probes; event-derived expectations, no authored fixtures."""
import copy, importlib.util, itertools, json, os, sys, traceback
from pathlib import Path
from unittest.mock import patch
E=Path(__file__).resolve().parent
sys.path.insert(0,os.environ['HIVE_SRC'])
from controller.reducer import Reducer
from hive.reducer import HiveReducer
from hive.types import HiveEvent, AgentHealth
from schemas.types import Event, EventKind

def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
Legacy=load('old',E/'legacy-reducer-e6afe16.py').Reducer
Previous=load('previous',E/'legacy-reducer-ef18db3.py').Reducer
A=load('authored',Path(os.environ['HIVE_SRC'])/'tests/test_astra7160.py')
def I(i='i',p='',sev='critical',resolved=False):return Event(kind=EventKind.INCIDENT,payload=dict(id=i,plan_id=p,severity=sev,component='svc',symptom='down',resolved=resolved))
def P(p='p',i='i',n=2):return Event(kind=EventKind.PLAN,payload=dict(id=p,incident_id=i,steps=[{} for _ in range(n)]))
def R(r='x',p='p',k=0,ok=True,i=''):return Event(kind=EventKind.RECEIPT,payload=dict(id=r,plan_id=p,step_index=k,verified=ok,incident_id=i))
def rt(r):
 out=Reducer();out.restore_snapshot(json.loads(json.dumps(r.snapshot())));return out

def quarantine(row):
 old=Legacy()
 for k in range(300):
  old.reduce(P('p'+str(k),'i'+str(k),1));old.reduce(I('i'+str(k)))
 previous=Previous();previous.restore_snapshot(json.loads(json.dumps(old.snapshot())))
 for k in range(300):previous.reduce(P('p'+str(k),'i'+str(k),1))
 snap=json.loads(json.dumps(previous.snapshot()));(E/'authentic-300-before.json').write_text(json.dumps(snap,indent=2))
 assert 'legacy_ownerless_plans stay quarantined' in snap['migration_diagnostics']['recovery']
 r=Reducer();r.restore_snapshot(snap);remaining={'p'+str(k) for k in range(300)}
 stages=[]
 for limit in [0,149,300]:
  for k in range(0 if limit==0 else (0 if limit==149 else 149),limit):
   pid='p'+str(k);r.rebind_plan_owner(pid,'i'+str(k),actor='Astra-7519',reason='independently authorized fixture',allow_non_candidate=True);remaining.remove(pid)
  before=copy.deepcopy(r.snapshot())
  for _ in range(20):
   assert r.quarantined_plans()==sorted(remaining)
   detached=r.quarantined_plans();detached.clear();assert r.quarantined_plans()==sorted(remaining)
   d=r.migration_diagnostics
   assert len(d['legacy_ownerless_plans'])==256 and d['legacy_ownerless_total']==300
   assert 'authoritative CURRENT quarantine is owner_unproven' in d['recovery']
   assert 'HISTORICAL SAMPLE' in d['recovery'] and 'not updated by rebinds' in d['recovery']
   assert 'legacy_ownerless_plans stay quarantined' not in d['recovery']
   r=rt(r);assert r.snapshot()==before
  stages.append(dict(rebound=limit,current=len(remaining),historical=len(d['legacy_ownerless_plans']),roundtrips=20))
 row['stages']=stages

def schedules(row):
 # Abstract model: one independently sufficient two-step p; q fails. Pending
 # plan-only receipts become effective at PLAN, complete p closes on INCIDENT.
 results=[]
 for order in itertools.permutations(['I','P','Q','a','b','f']):
  for restart in [False,True]:
   l=Reducer();h=HiveReducer();h.register_agent('a1');history=[]
   events={'I':I(),'P':P(),'Q':P('q','i',1),'a':R('a'),'b':R('b',k=1),'f':R('f','q',ok=False)}
   seen=set();closed=False;trace=[]
   for key in list(order)+['f','a','I','Q','b']:
    e=events[key];seen.add(key);history.append(e)
    if {'I','P','a','b'}<=seen:closed=True
    expected=[] if closed or 'I' not in seen else ['i']
    health='healthy' if closed else ('failed' if 'I' in seen else 'unknown')
    l.reduce(e);h.reduce(HiveEvent(source_agent='a1',original_event=e))
    if restart:
     l=rt(l)
     # Hive has no snapshot API: reconstruct only via ordered event replay.
     h=HiveReducer();h.register_agent('a1')
     for prior in history:h.reduce(HiveEvent(source_agent='a1',original_event=prior))
    assert sorted(i.id for i in l.open_incidents())==expected,(order,key,'local')
    assert sorted(i['incident_id'] for i in h._open_agent_incidents('a1'))==expected,(order,key,'hive')
    assert h.state.agents['a1'].health.value==health,(order,key,'health')
    assert h.state.agents['a1'].open_incidents==len(expected)
    trace.append(dict(event=key,open=expected,health=health))
   assert l._plan_failed_steps['q']=={0} and h._plan_failed['a1:q']=={0}
   results.append(dict(order=order,restart=restart,trace=trace))
 (E/'policy-schedules.json').write_text(json.dumps(results,indent=2))
 row.update(schedules=len(results),per_event_checks=sum(len(x['trace']) for x in results))

def foreign(row):
 results=[]
 for late in [False,True]:
  for restart in [False,True]:
   l=Reducer();h=HiveReducer();h.register_agent('a1')
   seq=([P('p','j',1),R(),I('i','p'),I('j')] if late else [I('i','p'),I('j'),P('p','j',1),R()])
   seq += [R(),P('p','i',1),I('i','p'),R('foreign','p',i='i')]
   for e in seq:
    l.reduce(e);h.reduce(HiveEvent(source_agent='a1',original_event=e))
    if restart:l=rt(l)
   assert [i.id for i in l.open_incidents()]==['i']
   assert [i['incident_id'] for i in h._open_agent_incidents('a1')]==['i']
   assert l._plan_owner['p']=='j' and h._plan_owner['a1:p']=='j'
   results.append(dict(late=late,local_restore=restart,open=['i']))
 row['controls']=results

def health(row):
 stream=[P('p','w',1),I('w',sev='warn'),I('e',sev='error'),P('q','e',1),R('qe','q'),R('pw'),I('w2',sev='warn')]
 expected=['unknown','unknown','degraded','failed','failed','failed','healthy','degraded']
 l=Reducer();h=HiveReducer();h.register_agent('a1');got=[h.state.agents['a1'].health.value]
 for e in stream:l.reduce(e);h.reduce(HiveEvent(source_agent='a1',original_event=e));got.append(h.state.agents['a1'].health.value)
 assert got==expected;A.both(stream,plans=('p','q'))
 original=HiveReducer._recompute_agent_health;mutations=[]
 for forced in AgentHealth:
  def faulty(self,agent,forced=forced):
   original(self,agent);self.state.agents[agent].health=forced
  try:
   with patch.object(HiveReducer,'_recompute_agent_health',faulty):A.both(stream,plans=('p','q'))
  except AssertionError as ex:
   assert 'health' in str(ex);mutations.append(dict(forced=forced.value,detected=str(ex)))
  else:raise AssertionError('health mutation survived: '+str(forced))
 orig_reg=HiveReducer.register_agent
 def badreg(self,agent):orig_reg(self,agent);self.state.agents[agent].health=AgentHealth.HEALTHY
 with patch.object(HiveReducer,'register_agent',badreg):
  try:A.both([])
  except AssertionError as ex:assert 'health' in str(ex);mutations.append(dict(initial_unknown=str(ex)))
  else:raise AssertionError('UNKNOWN mutation survived')
 transitions=[]
 def spy(self,agent):original(self,agent);transitions.append(self.state.agents[agent].health.value)
 with patch.object(HiveReducer,'_recompute_agent_health',spy):
  A.both([P(n=1),R(),I(sev='warn')])
 assert transitions==['degraded','healthy'],transitions
 row.update(explicit_sequence=got,mutations=mutations,late_incident_transitions=transitions)

def new_boundaries(row):
 # Policy language requires ownership; distinguish genuinely ownerless current
 # plans from foreign-owner rejection and quarantined migrated plans.
 witnesses=[]
 for restore in [False,True]:
  l=Reducer();h=HiveReducer();h.register_agent('a1')
  for e in [I('i','p'),I('j','p'),P('p','',1),R()]:
   l.reduce(e);h.reduce(HiveEvent(source_agent='a1',original_event=e))
   if restore:l=rt(l)
  witnesses.append(dict(local_restore=restore,local_open=[i.id for i in l.open_incidents()],hive_open=[i['incident_id'] for i in h._open_agent_incidents('a1')],local_owners=l._plan_owner,hive_owners=h._plan_owner,quarantine=l.quarantined_plans()))
  assert not l._plan_owner and not h._plan_owner and not l.open_incidents() and not h._open_agent_incidents('a1')
 # An incident arriving already resolved has never been open. Contract says
 # UNKNOWN, but the new oracle interprets mere history as a prior open period.
 l=Reducer();h=HiveReducer();h.register_agent('a1');e=I(resolved=True)
 l.reduce(e);h.reduce(HiveEvent(source_agent='a1',original_event=e))
 assert h.state.agents['a1'].health==AgentHealth.UNKNOWN
 exp=A.expected_health(l,AgentHealth.UNKNOWN)
 assert exp==AgentHealth.HEALTHY
 try:A.both([e])
 except AssertionError as ex:message=str(ex);assert 'health' in message
 else:raise AssertionError('expected oracle mismatch not demonstrated')
 row.update(ownerless_policy_witnesses=witnesses,already_resolved_oracle=dict(actual='unknown',expected_by_authored=exp.value,assertion=message))

out={}
for name,fn in [('quarantine',quarantine),('policy_schedules',schedules),('foreign_owner',foreign),('health',health),('new_boundaries',new_boundaries)]:
 row={}
 try:fn(row);row['passed']=True
 except Exception as ex:row.update(passed=False,error=repr(ex),traceback=traceback.format_exc())
 out[name]=row;print(name,json.dumps(row),flush=True)
(E/'review7519.json').write_text(json.dumps(out,indent=2)+'\n')
sys.exit(not all(x['passed'] for x in out.values()))
