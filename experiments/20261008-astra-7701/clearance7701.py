"""Systematically stop before/after each clearance mutation/durability operation."""
import os,json,copy,sys,traceback
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
E=Path(__file__).resolve().parent
ns={'__file__':str(E/'focused7701.py'),'__name__':'defs'}
src=(E/'focused7701.py').read_text();exec(compile(src[:src.index('\nout={}\n')],str(E/'focused7701.py'),'exec'),ns)
for k in ['fresh','two','hb','bindq','fpath','records','hfeed','hnew','snapshot','anchor','Crash']:globals()[k]=ns[k]
def case(name,target=None,side='before',error=Crash):
 p,s,h=fresh('clear7701-'+name,two());assert hb(h)
 write=os.write
 def refuse(fd,data):
  if fpath(fd)==str(p) and b'"rebind_commit"' in data:raise OSError('refused q commit')
  return write(fd,data)
 with patch.object(os,'write',refuse):assert bindq(h).status=='refused'
 assert len(records(p))==4
 h._set_fence('review_fault','inspect pending-only suffix')
 old=p.read_bytes();oldid=anchor(p).read_bytes();oldowner=copy.deepcopy(h._plan_owner);trace=[];triggered=False
 real={k:getattr(os,k) for k in ['open','write','fsync','replace','unlink']}
 def wrapper(kind):
  def call(*args,**kw):
   nonlocal triggered
   path=str(args[0]) if kind in ['open','replace','unlink'] else fpath(args[0])
   relevant=path.startswith(str(p)) or path==str(p.parent)
   # O_RDONLY directory opens do not mutate storage; fsync still instrumented.
   relevant=relevant and (kind!='open' or bool(args[1] & os.O_CREAT))
   if not relevant:return real[kind](*args,**kw)
   n=len(trace);trace.append(dict(index=n,op=kind,path=path,destination=str(args[1]) if kind=='replace' else None))
   if n==target and side=='before':triggered=True;raise error(name)
   result=real[kind](*args,**kw)
   if n==target and side=='after':triggered=True;raise error(name)
   return result
  return call
 caught=None;result=None
 with ExitStack() as stack:
  for k in real:stack.enter_context(patch.object(os,k,wrapper(k)))
  try:result=h.clear_journal_fence('reviewer-clear','retain applied only')
  except (Crash,OSError) as ex:caught=type(ex).__name__
 if target is not None:assert triggered and caught
 else:assert result
 assert h._plan_owner==oldowner=={'a1:p':'i'}
 if caught:assert not h.journal_status()['healthy'] and not h.journal_status()['fence_clearances']
 else:
  assert h.journal_status()['healthy'];audit=h.journal_status()['fence_clearances'][-1]
  assert Path(audit['archived']).read_bytes()==old and audit['rebinds_rejournaled']==1
  assert [r['op'] for r in records(p)]==['journal_header','journal_reset','rebind_pending','rebind_commit']
 rs=[hfeed(hnew(p),s) for _ in range(2)]
 for z in rs:
  assert 'a1:q' not in z._plan_owner and 'a1:q' in z.quarantined_plans()
  if z.journal_status()['healthy']:assert z._plan_owner==oldowner
  else:assert not z._plan_owner
 return dict(name=name,target=target,side=side,caught=caught,trace=trace,old_bytes_unchanged=p.read_bytes()==old,old_anchor_unchanged=anchor(p).read_bytes()==oldid,live=snapshot(h),restarts=[snapshot(z) for z in rs])
base=case('success');rows=[base]
for t in base['trace']:
 for side in ['before','after']:
  for error in [Crash,OSError]:
   rows.append(case(str(t['index'])+'-'+side+'-'+error.__name__,t['index'],side,error))
(E/'clearance7701.json').write_text(json.dumps(dict(cases=rows,operations=len(base['trace']),injections=len(rows)-1,scope='Injected abrupt BaseException/OSError, not physical power loss. Healthy restart retains only applied p; id-mismatch restart fences all.'),indent=2,default=str)+'\n')
print(json.dumps(dict(operations=len(base['trace']),injections=len(rows)-1,passed=True)))
