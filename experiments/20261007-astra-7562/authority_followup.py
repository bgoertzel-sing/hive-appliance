"""Correct only historical fixture construction; preserve original failure evidence."""
import ast,copy,json,logging,os,sys,traceback
from pathlib import Path
E=Path(__file__).resolve().parent
sys.path.insert(0,os.environ['HIVE_SRC'])
raw=(E/'review7542.py').read_text();prefix=raw[:raw.index('\nout={}\n')]
a={'__file__':str(E/'review7542.py'),'__name__':'retained7542'};exec(compile(prefix,str(E/'review7542.py'),'exec'),a)
Reducer,HiveReducer,HiveEvent,Event,I,P,R,rt,new,replay,opens=[a[k] for k in ['Reducer','HiveReducer','HiveEvent','Event','I','P','R','rt','new','replay','opens']]
def bothreduce(l,h,e):l.reduce(e);h.reduce(HiveEvent(source_agent='a1',original_event=e))
raw=(E/'review7562.py').read_text();tree=ast.parse(raw);node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='authority')
fn=ast.get_source_segment(raw,node)
assert fn.count("old.reduce(I('i','p'))")==1
fn=fn.replace("old.reduce(I('i','p'))","old.reduce(I('i'))")
exec(compile(fn,'authority_fixture_corrected','exec'))
row={'fixture_correction':'Original historical INCIDENT linked p, enabling genuine legacy owner reconstruction. Use authentic PLAN-before-unlinked-INCIDENT history, as retained 300-plan fixture does. No product change; original run/traceback preserved.'}
try:authority(row);row['passed']=True
except Exception as ex:row.update(passed=False,error=repr(ex),traceback=traceback.format_exc())
(E/'authority-followup.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row,indent=2))
sys.exit(not row['passed'])
