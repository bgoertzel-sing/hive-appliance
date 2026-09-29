import os,sys,json,importlib.util
from pathlib import Path
E=Path(__file__).resolve().parent;sys.path.insert(0,os.environ['HIVE_SRC'])
from controller.reducer import Reducer
from schemas.types import Event,EventKind
spec=importlib.util.spec_from_file_location('old',E/'legacy-reducer-e6afe16.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
def ev(k,**p):return Event(kind=k,payload=p)
rows=[]
for ambiguous in [False,True]:
 x=old.Reducer()
 x.reduce(ev(EventKind.INCIDENT,id='i',component='svc',symptom='down'))
 x.reduce(ev(EventKind.PLAN,id='p',incident_id='i',steps=[{},{}]))
 for k in [0,1]:x.reduce(ev(EventKind.RECEIPT,id='r'+str(k),plan_id='p',step_index=k,verified=True))
 assert not x.open_incidents()
 if ambiguous:x.reduce(ev(EventKind.INCIDENT,id='other',component='svc',symptom='down',plan_id='p'))
 s=x.snapshot();l=Reducer();l.restore_snapshot(s);before=l.snapshot();got=l.rebind_plan_owner('p','i');rows.append(dict(ambiguous=ambiguous,real_completed_legacy_plan=True,snapshot=s,before=before,accepted=got,after=l.snapshot()))
(E/'resolved-plan-probe.json').write_text(json.dumps(rows,indent=2));print([(r['ambiguous'],r['accepted']) for r in rows])
