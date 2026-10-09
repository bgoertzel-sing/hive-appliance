"""Intent existence controls, retries and clearance interruptions; explicit durability witness."""
import os,sys,json,traceback,builtins
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
E=Path(__file__).resolve().parent
ns={'__file__':str(E/'reset7718.py'),'__name__':'defs'}
src=(E/'reset7718.py').read_text();exec(compile(src[:src.index('\nout={}\n')],str(E/'reset7718.py'),'exec'),ns)
for k in ['restored','hnew','hfeed','held','state','records','pair','disk','hr','Crash','fpath','anchor']:globals()[k]=ns[k]

ns['T']=E/'intent-final-cases';ns['T'].mkdir(exist_ok=True)
def inspect_disk(p):
 result={}
 for q in p.parent.glob(p.name+'*'):
  if q.is_symlink():result[q.name]={'symlink':str(q.readlink())}
  elif q.is_dir():result[q.name]={'directory':True}
  else:
   try:result[q.name]=q.read_bytes().hex()
   except PermissionError:result[q.name]={'unreadable':True,'size':q.stat().st_size,'mode':q.stat().st_mode}
 return result

def controls(row):
 rows=[]
 for marker in ['empty','partial','damaged','unreadable','directory','dangling_symlink']:
  for pairmode in ['healthy','markers','missing_anchor','missing_journal','mismatch','both_missing','legacy_leftovers']:
   p,s,_=restored('intent-'+marker+'-'+pairmode);ip=Path(str(p)+'.reset-intent')
   if pairmode=='markers':
    for suf in hr.HiveReducer.LEGACY_MARKER_SUFFIXES:Path(str(p)+suf).write_bytes(b'legacy')
   elif pairmode=='missing_anchor':anchor(p).unlink()
   elif pairmode=='missing_journal':p.unlink()
   elif pairmode=='mismatch':anchor(p).write_text('{"v":5,"journal_id":"wrong"}')
   elif pairmode=='both_missing':p.unlink();anchor(p).unlink()
   elif pairmode=='legacy_leftovers':
    Path(str(p)+'.reset-123').write_bytes(p.read_bytes());Path(str(anchor(p))+'.reset-123').write_bytes(anchor(p).read_bytes())
   if marker=='directory':ip.mkdir()
   elif marker=='dangling_symlink':ip.symlink_to(ip.name+'.absent')
   else:ip.write_bytes({'empty':b'','partial':b'{"v":','damaged':b'\xff\x00','unreadable':b'opaque'}[marker])
   if marker=='unreadable':ip.chmod(0)
   before=inspect_disk(p);h=hnew(p);st=state(h)
   assert not st['status']['healthy'] and st['status']['fence']['kind']=='reset_incomplete'
   assert st['pending']==0 and before==inspect_disk(p)
   hfeed(h,s);held(h)
   failed=None
   try:assert h.clear_journal_fence('op','finish interrupted reset')
   except IsADirectoryError:failed='directory remains fenced; operator repair required';assert marker=='directory';assert not h.journal_status()['healthy']
   else:
    assert not os.path.lexists(ip) and h.journal_fence_clearances[-1]['rebinds_rejournaled']==0
    assert [r['op'] for r in records(p)]==['journal_header','journal_reset']
   z=hfeed(hnew(p),s);held(z)
   if marker=='unreadable':assert not ip.exists()
   rows.append(dict(marker=marker,pairmode=pairmode,startup=st,recovery=failed or 'zero-carry clearance',restart=state(z)))
 row.update(cases=rows,count=len(rows))

def action_case(name,action,target=None,side='before',error=OSError,followup='retry'):
 p,s,h=restored(name);ip=Path(str(p)+'.reset-intent')
 if action=='clear':ip.write_bytes(b'');h=hnew(p)
 trace=[];triggered=False
 real={k:getattr(os,k) for k in ['open','write','fsync','replace','unlink']}
 def wrap(kind):
  def call(*args,**kw):
   nonlocal triggered
   path=str(args[0]) if kind in ['open','replace','unlink'] else fpath(args[0])
   relevant=(path.startswith(str(p)) or path==str(p.parent)) and (kind!='open' or bool(args[1]&os.O_CREAT))
   if not relevant:return real[kind](*args,**kw)
   n=len(trace);trace.append(dict(index=n,op=kind,path=path))
   if n==target and side=='before':triggered=True;raise error(name)
   r=real[kind](*args,**kw)
   if n==target and side=='after':triggered=True;raise error(name)
   return r
  return call
 with ExitStack() as stack:
  for k in real:stack.enter_context(patch.object(os,k,wrap(k)))
  try:
   if action=='reset':h.reset_journal('op','reset retry')
   else:h.clear_journal_fence('op','clear interruption')
  except (Crash,OSError):assert target is not None
 if target is not None:assert triggered
 before=state(h)
 if action=='reset' and target is not None:
  assert not before['status']['healthy'] and before['pending']==0
  if followup=='feed':hfeed(h,s);held(h);assert not h.journal_status()['healthy']
  else:
   result=h.reset_journal('op','retry after error');assert result['status']=='completed';hfeed(h,s);held(h)
 else:
  z=hfeed(hnew(p),s);held(z)
  if target is not None and error==OSError:
   assert not h.journal_status()['healthy'];h.clear_journal_fence('op','retry clearance')
 rs=[]
 if action!='reset' or followup!='feed':
  for _ in range(2):
   z=hfeed(hnew(p),s);held(z);rs.append(state(z))
 return dict(trace=trace,target=target,side=side,error=error.__name__,before=before,restarts=rs,followup=followup)

def retries(row):
 base=action_case('retry-base','reset');rows=[]
 for t in base['trace']:
  for side in ['before','after']:
   for followup in ['retry','feed']:
    r=action_case('retry-'+str(t['index'])+'-'+side+'-'+followup,'reset',t['index'],side,followup=followup);rows.append(r)
 row.update(operations=len(base['trace']),cases=rows,count=len(rows))

def clearance(row):
 base=action_case('clear-base','clear');rows=[]
 for t in base['trace']:
  for side in ['before','after']:
   for error in [Crash,OSError]:rows.append(action_case('clear-'+str(t['index'])+'-'+side+'-'+error.__name__,'clear',t['index'],side,error))
 row.update(operations=len(base['trace']),cases=rows,count=len(rows))

def durability(row):
 # os.open(O_CREAT) succeeds, then wrapper raises OSError before helper's try.
 # Existence is not a completed file+directory fsync.
 p,s,h=restored('intent-durability-open');ip=str(p)+'.reset-intent';old=pair(p);real=os.open;fd=None;fsyncs=[];realfs=os.fsync
 def opening(path,*a,**kw):
  nonlocal fd
  x=real(path,*a,**kw)
  if str(path)==ip:fd=x;raise OSError('return-boundary failure after intent create, before any fsync')
  return x
 def syncing(fd):fsyncs.append(fpath(fd));return realfs(fd)
 with patch.object(os,'open',opening),patch.object(os,'fsync',syncing):
  try:h.reset_journal('op','durability report witness')
  except OSError:pass
 assert fd is not None;os.close(fd)
 failed=state(h);assert failed['resets'][-1]['intent_durable'] is False and fsyncs==[] and pair(p)==old
 # Model the legal power-loss result of an unsynced directory entry disappearing.
 Path(ip).unlink();z=hfeed(hnew(p),s);assert z._plan_owner=={'a1:p':'i'}
 row.update(witness=failed,fsync_calls=fsyncs,intent_bytes=0,modeled_power_loss_restart=state(z),finding='CLOSED: visible marker never substitutes for confirmed durability',simulation_scope='Only unsynced marker entry removed; journal and identity bytes unchanged')
 # Real syscall-like failure sequence: file fsync EIO, cleanup unlink EACCES.
 p,s,h=restored('intent-durability-fsync');ip=str(p)+'.reset-intent';realfs=os.fsync;realunlink=os.unlink
 def failfs(fd):
  if fpath(fd)==ip:raise OSError('EIO intent fsync')
  return realfs(fd)
 def failunlink(path,*a,**kw):
  if str(path)==ip:raise PermissionError('EACCES cleanup unlink')
  return realunlink(path,*a,**kw)
 with patch.object(os,'fsync',failfs),patch.object(os,'unlink',failunlink):
  try:h.reset_journal('op','fsync and cleanup failure')
  except OSError:pass
 assert h.journal_resets[-1]['intent_durable'] is False
 row['fsync_failure_plus_cleanup_failure']=state(h)

out={}
for name,fn in [('intent_controls',controls),('reset_retries_and_live_errors',retries),('intent_clearance_matrix',clearance),('intent_durability_reporting',durability)]:
 r={}
 try:fn(r);r['passed']=True
 except Exception as ex:r.update(passed=False,error=repr(ex),traceback=traceback.format_exc())
 out[name]=r;print(name,r['passed'],r.get('error',''),flush=True)
(E/'intent-final7727.json').write_text(json.dumps(out,indent=2,default=str)+'\n')
sys.exit(not all(r['passed'] for r in out.values()))
