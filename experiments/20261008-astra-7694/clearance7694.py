"""Additional clearance durability witnesses; reuse definitions, not prior executions."""
import os,json,copy,traceback
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
E=Path(__file__).resolve().parent
ns={'__file__':str(E/'followup7694.py'),'__name__':'defs'}
source=(E/'followup7694.py').read_text()
exec(compile(source[:source.index('\nout={}\n')],str(E/'followup7694.py'),'exec'),ns)
globals().update({k:ns[k] for k in ['fresh','two','hb','bindq','fpath','records','hfeed','hnew','v']})
rows=[]
modes=['archive_write','archive_file_fsync','archive_dir_fsync','new_create','new_file_fsync','new_dir_fsync','rename','post_rename_dir_fsync','success']
for mode in modes:
 p,s,h=fresh('clearance-'+mode,two())
 assert hb(h)
 real={k:getattr(os,k) for k in ['open','write','fsync','replace']}
 # Leave a genuine pending-only refused q beside the applied p, then fence.
 def refuse(fd,data):
  if fpath(fd)==str(p) and b'"rebind_commit"' in data:raise OSError('refused q commit')
  return real['write'](fd,data)
 with patch.object(os,'write',refuse):assert not bindq(h)
 assert len(records(p))==3
 h._set_fence('review_fault','inspect pending-only suffix')
 old=p.read_bytes();owners=copy.deepcopy(h._plan_owner);clearances=copy.deepcopy(h.journal_status()['fence_clearances'])
 trace=[];stage='';triggered=False
 def opened(path,*args,**kw):
  global stage,triggered
  path=str(path)
  if '.fenced-' in path:stage='archive'
  elif '.new-' in path:
   stage='new'
   if mode=='new_create':triggered=True;raise OSError(mode)
  return real['open'](path,*args,**kw)
 def write(fd,data):
  global triggered
  path=fpath(fd);trace.append(['write',path,len(data)])
  if '.fenced-' in path and mode=='archive_write':triggered=True;raise OSError(mode)
  return real['write'](fd,data)
 def sync(fd):
  global triggered
  path=fpath(fd);trace.append(['fsync',path,stage])
  target=(('.fenced-' in path and mode=='archive_file_fsync') or
          ('.new-' in path and mode=='new_file_fsync') or
          (path==str(p.parent) and mode==stage+'_dir_fsync'))
  if target:triggered=True;raise OSError(mode)
  return real['fsync'](fd)
 def replace(a,b):
  global stage,triggered
  trace.append(['rename',str(a),str(b)])
  if mode=='rename':triggered=True;raise OSError(mode)
  result=real['replace'](a,b);stage='post_rename';return result
 error=None
 with ExitStack() as stack:
  for k,fn in [('open',opened),('write',write),('fsync',sync),('replace',replace)]:stack.enter_context(patch.object(os,k,fn))
  try:result=h.clear_journal_fence('reviewer-clear','retain applied only')
  except OSError as ex:error=str(ex)
 assert h._plan_owner==owners=={'a1:p':'i'}
 if mode!='success':
  assert triggered and error and h.journal_status()['fence'] is not None
  assert h.journal_status()['fence_clearances']==clearances
  if mode!='post_rename_dir_fsync':assert p.read_bytes()==old
  else:assert p.read_bytes()!=old
 else:
  assert result and h.journal_status()['healthy']
  audit=h.journal_status()['fence_clearances'][-1]
  assert audit['actor']=='reviewer-clear' and audit['reason']=='retain applied only' and audit['rebinds_rejournaled']==1
  assert Path(audit['archived']).read_bytes()==old
  rr=records(p)
  assert [r['op'] for r in rr]==['journal_reset','rebind_pending','rebind_commit']
  assert rr[0]['actor']=='reviewer-clear' and rr[0]['reason']=='retain applied only' and rr[0]['archived']==audit['archived']
  assert rr[1]['plan_id']=='p'
 rest=hfeed(hnew(p),s)
 assert rest._plan_owner==owners and 'a1:q' in rest.quarantined_plans()
 rows.append(dict(mode=mode,error=error,old_bytes_unchanged=p.read_bytes()==old,live=v(h),restart=v(rest),trace=trace))
out=json.loads((E/'followup7694.json').read_text())
out['clearance_fault_matrix']=dict(passed=True,cases=rows,interpretation='Seven pre-rename durability failures preserve old bytes, live fence and audit; success archives exact bytes and carries applied p only. Extra post-rename dir-fsync failure raises with live fence/audit unchanged but disk already replaced: old-byte-preservation is not promised after rename; both disk states retain applied p and exclude refused pending-only q.')
(E/'followup7694.json').write_text(json.dumps(out,indent=2,default=str)+'\n')
(E/'followup7694-summary.json').write_text(json.dumps(dict(groups=len(out),passed=sum(r['passed'] for r in out.values()),failed=[k for k,r in out.items() if not r['passed']],note='Defect assertions are not safety approvals'),indent=2)+'\n')
print(json.dumps(dict(group='clearance_fault_matrix',passed=True,modes=len(rows)),indent=2))
