"""Additional read-only/stat/close/directory-open I/O boundaries beyond retained matrix."""
import os,json,sys,traceback,builtins
from pathlib import Path
from unittest.mock import patch
E=Path(__file__).resolve().parent
src=(E/'intent_final7727.py').read_text();src=src[:src.index('\nout={}\n')]
src=src.replace("['open','write','fsync','replace','unlink']","['open','write','fsync','replace','unlink','fstat','close']")
src=src.replace(" and (kind!='open' or bool(args[1]&os.O_CREAT))",'')
src=src.replace("ns['T']=E/'intent-final-cases'","ns['T']=E/'extra-io-cases'")
ns={'__file__':str(E/'intent_final7727.py'),'__name__':'defs'};exec(compile(src,str(E/'intent_final7727.py'),'exec'),ns)
out={}
try:
 base=ns['action_case']('extra-base','reset');rows=[]
 for t in base['trace']:
  if t['op'] not in ['fstat','close'] and not (t['op']=='open' and t['path']==str(ns['ns']['T'])):continue
  for side in ['before','after']:
   rows.append(ns['action_case']('extra-'+str(t['index'])+'-'+side,'reset',t['index'],side))
 out['extra_boundaries']=dict(total_traced_operations=len(base['trace']),additional_injections=len(rows),cases=rows,passed=True)
except Exception as ex:out['extra_boundaries']=dict(passed=False,error=repr(ex),traceback=traceback.format_exc())
try:
 rows=[]
 for stage in ['open','read']:
  for side in ['before','after']:
   p,s,h=ns['restored']('anchor-read-'+stage+'-'+side);oldopen=builtins.open
   class ReadWrapper:
    def __init__(self,f):self.f=f
    def __enter__(self):return self
    def __exit__(self,*a):self.f.close()
    def read(self,*a,**kw):
     if side=='before':raise OSError('anchor read before')
     self.f.read(*a,**kw);raise OSError('anchor read after')
   def opening(path,*a,**kw):
    if str(path)!=str(ns['anchor'](p)):return oldopen(path,*a,**kw)
    if stage=='open' and side=='before':raise OSError('anchor open before')
    f=oldopen(path,*a,**kw)
    if stage=='open':f.close();raise OSError('anchor open after')
    return ReadWrapper(f)
   with patch.object(builtins,'open',opening):
    try:h.reset_journal('op','anchor read fail')
    except OSError:pass
    else:raise AssertionError('error not raised')
   st=ns['state'](h);assert not st['status']['healthy'] and st['pending']==0
   assert not h.verify_journal();assert h.clear_journal_fence('op','recover anchor read failure')
   assert h.journal_fence_clearances[-1]['rebinds_rejournaled']==0
   ns['held'](ns['hfeed'](h,s));z=ns['hfeed'](ns['hnew'](p),s);ns['held'](z)
   rows.append(dict(stage=stage,side=side,failed=st,restart=ns['state'](z)))
 out['anchor_reads']=dict(cases=rows,passed=True)
except Exception as ex:out['anchor_reads']=dict(passed=False,error=repr(ex),traceback=traceback.format_exc())
(E/'extra-io7727.json').write_text(json.dumps(out,indent=2,default=str)+'\n')
for k,v in out.items():print(k,v['passed'],v.get('error',''),v.get('additional_injections',''))
sys.exit(not all(v['passed'] for v in out.values()))
