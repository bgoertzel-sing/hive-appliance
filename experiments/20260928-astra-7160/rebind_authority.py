import os,sys,json,importlib.util
from pathlib import Path
E=Path(__file__).resolve().parent;sys.path.insert(0,os.environ['HIVE_SRC'])
from controller.reducer import Reducer
from schemas.types import Event,EventKind
spec=importlib.util.spec_from_file_location('old',E/'legacy-reducer-e6afe16.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
def e(k,p):return Event(kind=k,payload=p)
x=old.Reducer();x.reduce(e(EventKind.PLAN,dict(id='p',incident_id='historical',steps=[{},{}])))
for i in ['historical','unrelated']:x.reduce(e(EventKind.INCIDENT,dict(id=i,component='svc',symptom='down',severity='critical')))
rows=[]
for with_evidence in [False,True]:
 l=Reducer();l.restore_snapshot(x.snapshot())
 if with_evidence:
  for k in [0,1]:l.reduce(e(EventKind.RECEIPT,dict(id='fresh'+str(k),plan_id='p',step_index=k,verified=True)))
 before=l.snapshot();accepted=l.rebind_plan_owner('p','unrelated');after=l.snapshot()
 for _ in range(20):r=Reducer();r.restore_snapshot(json.loads(json.dumps(l.snapshot())));l=r
 rows.append(dict(fresh_post_migration_evidence=with_evidence,before=before,accepted=accepted,after=after,open=sorted(i.id for i in l.open_incidents()),diagnostics_stable=l.migration_diagnostics==after['migration_diagnostics'],rebind_log_entries=len(l.migration_diagnostics.get('owner_rebinds',[]))))
(E/'rebind-authority.json').write_text(json.dumps(rows,indent=2));print([(r['fresh_post_migration_evidence'],r['open'],r['diagnostics_stable']) for r in rows])
