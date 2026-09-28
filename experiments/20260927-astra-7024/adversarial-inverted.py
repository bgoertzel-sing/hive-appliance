import pathlib,sys,json
E=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(E.parent.parent/'repos/hive-astra-7024'))
from schemas.types import Event,EventKind
from controller.reducer import Reducer
from hive.reducer import HiveReducer
from hive.types import HiveEvent
O={}
def run(name,seq):
 l=Reducer();h=HiveReducer();h.register_agent('a');counts=[]
 for k,p in seq:
  e=Event(kind=k,payload=p);l.reduce(e);h.reduce(HiveEvent(source_agent='a',original_event=e));counts.append([len(l.open_incidents()),len(h._open_agent_incidents('a'))])
 O[name]={'counts_local_hive':counts,'local_failed':{k:list(v) for k,v in l._plan_failed_steps.items()},'hive_failed':{k:list(v) for k,v in h._plan_failed.items()}}
 return counts
I=(EventKind.INCIDENT,dict(id='i',symptom='s',severity='critical'))
P=(EventKind.PLAN,dict(id='p',incident_id='i',steps=[{},{}]))
def R(rid,idx,ok=True):return EventKind.RECEIPT,dict(id=rid,plan_id='p',step_index=idx,verified=ok)
a=run('buffered_failure_after_verified',[I,R('0',0),R('1',1),R('f',0,False),P]);assert a[-1]==[1,1]
b=run('buffered_failure_then_retry',[I,R('0',0),R('1',1),R('f',0,False),P,R('retry',0)]);assert b[-1]==[0,0]
# identity mismatch should not count evidence for another incident
P2=(EventKind.PLAN,dict(id='q',incident_id='other',steps=[{}]))
J=(EventKind.INCIDENT,dict(id='other',symptom='s',severity='critical'))
bad=(EventKind.RECEIPT,dict(id='bad',plan_id='p',incident_id='other',step_index=1,verified=True))
c=run('contradictory_incident_identity',[I,J,P,P2,R('0',0),bad]);assert c[-1]==[2,2]
(E/'adversarial-inverted.json').write_text(json.dumps(O,indent=2));print(json.dumps(O,indent=2))
