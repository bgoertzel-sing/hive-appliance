"""Initial creation durability trace and every before/after syscall crash point."""
import os,json
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
E=Path(__file__).resolve().parent
ns={'__file__':str(E/'focused7701.py'),'__name__':'defs'};src=(E/'focused7701.py').read_text();exec(compile(src[:src.index('\nout={}\n')],str(E/'focused7701.py'),'exec'),ns)
for k in ['hnew','hfeed','history','snapshot','anchor','Crash','fpath','hb']:globals()[k]=ns[k]
T=ns['T']
def case(name,target=None,side='before',error=Crash):
 stream=history();p=T/('initial7708-'+name+'.jsonl');real={k:getattr(os,k) for k in ['open','write','fsync','replace']};trace=[];triggered=False;caught=None
 def wrap(kind):
  def call(*a,**kw):
   nonlocal triggered
   path=str(a[0]) if kind in ['open','replace'] else fpath(a[0])
   relevant=(path.startswith(str(p)) or path==str(p.parent)) and (kind!='open' or bool(a[1]&os.O_CREAT))
   if not relevant:return real[kind](*a,**kw)
   n=len(trace);trace.append(dict(index=n,op=kind,path=path,destination=str(a[1]) if kind=='replace' else None))
   if n==target and side=='before':triggered=True;raise error(name)
   r=real[kind](*a,**kw)
   if n==target and side=='after':triggered=True;raise error(name)
   return r
  return call
 h=None
 with ExitStack() as stack:
  for k in real:stack.enter_context(patch.object(os,k,wrap(k)))
  try:h=hnew(p)
  except Crash:caught='Crash'
 if target is not None:assert triggered
 disk_before=dict(journal_exists=p.exists(),anchor_exists=anchor(p).exists(),journal=p.read_text() if p.exists() else None,anchor=anchor(p).read_text() if anchor(p).exists() else None)
 if h is not None and target is not None:assert not h.journal_status()['healthy']
 n=hfeed(hnew(p),stream);held_before=snapshot(n);r=hb(n)
 return dict(name=name,target=target,side=side,error_type=error.__name__,caught=caught,trace=trace,interrupted_live=snapshot(h) if h else None,before_restart=disk_before,restart=held_before,rebind=r.as_dict(),second_restart=snapshot(hfeed(hnew(p),stream)))
base=case('success');rows=[base]
for t in base['trace']:
 for side in ['before','after']:
  for error in [Crash,OSError]:rows.append(case(str(t['index'])+'-'+side+'-'+error.__name__,t['index'],side,error))
(E/'startup7708.json').write_text(json.dumps(dict(operations=len(base['trace']),injections=len(rows)-1,cases=rows,scope='OS/syscall simulation; creation retry/adoption is observed, NOT claimed to meet required persistent-fence gate.'),indent=2,default=str)+'\n')
print(json.dumps(dict(operations=len(base['trace']),injections=len(rows)-1)))
