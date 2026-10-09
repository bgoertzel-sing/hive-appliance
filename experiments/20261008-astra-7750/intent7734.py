"""Independent current-round intent confirmation, status and compound failure controls."""
import os,sys,json,errno,traceback
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
E=Path(__file__).resolve().parent
ns={'__file__':str(E/'reset7718.py'),'__name__':'defs'}
src=(E/'reset7718.py').read_text();exec(compile(src[:src.index('\nout={}\n')],str(E/'reset7718.py'),'exec'),ns)
for k in ['restored','hnew','hfeed','held','state','pair','hr','Crash','fpath']:globals()[k]=ns[k]
ns['T']=E/'intent7734-cases';ns['T'].mkdir(exist_ok=True)

def case(name,existing=False,target=None,side='before',error=OSError,helper=False,cleanup=False):
 p,s,h=restored(name);ip=str(p)+'.reset-intent';old=pair(p)
 if existing:Path(ip).write_bytes(b'unsynced leftover');h=hnew(p)
 trace=[];syncs=[];triggered=False;opened=set();real={k:getattr(os,k) for k in ['open','write','fsync','fstat','close','replace','unlink']}
 def wrap(kind):
  def call(*a,**kw):
   nonlocal triggered
   path=str(a[0]) if kind in ['open','replace','unlink'] else fpath(a[0])
   relevant=path.startswith(str(p)) or path==str(p.parent)
   if not relevant:return real[kind](*a,**kw)
   i=len(trace);trace.append(dict(index=i,op=kind,path=path))
   hit=i==target and not helper
   if cleanup and kind=='unlink' and path==ip:raise PermissionError(errno.EACCES,'cleanup denied')
   if hit and side=='before':triggered=True;raise error('before '+kind)
   r=real[kind](*a,**kw)
   if kind=='open':opened.add(r)
   if kind=='close':opened.discard(a[0])
   if kind=='fsync':syncs.append(path)
   if hit and side=='after':triggered=True;raise error('after '+kind)
   return r
  return call
 realhelper=h._sync_existing_durably if existing else h._write_file_durably
 def helpercall(*a,**kw):
  nonlocal triggered
  if str(a[0])!=ip:return realhelper(*a,**kw)
  if side=='before':triggered=True;raise error('before intent helper')
  realhelper(*a,**kw);triggered=True;raise error('after intent helper')
 with ExitStack() as stack:
  for k in real:stack.enter_context(patch.object(os,k,wrap(k)))
  if helper:stack.enter_context(patch.object(h,'_sync_existing_durably' if existing else '_write_file_durably',helpercall))
  try:h.reset_journal('op','intent matrix')
  except (Crash,OSError):pass
 for fd in opened:
  try:real['close'](fd)
  except OSError:pass
 failed=state(h);present=os.path.lexists(ip)
 if target is not None or helper:
  assert triggered
  fence=failed['status']['fence'];audit=failed['resets'][-1]
  assert not failed['status']['healthy'] and failed['pending']==0
  assert fence['intent_present']==audit['intent_present']==present
  assert fence['intent_durable']==audit['intent_durable']
  if fence['intent_durable']:
   assert present and ip in syncs and str(p.parent) in syncs
   assert 'fsync confirmed' in fence['error'] or 'new rebind-free journal and anchor are complete' in fence['error']
  elif fence['failed_step']!='remove reset-intent marker':
   assert pair(p)==old and 'NOT confirmed' in fence['error'] and 'keep the service stopped' in fence['error']
  else:assert not present and 'restart is safe' in fence['error']
  hfeed(h,s);held(h)
  if isinstance(error,type) and error is OSError:
   assert h.clear_journal_fence('op','finish failed reset');assert h.journal_fence_clearances[-1]['rebinds_rejournaled']==0
   held(hfeed(hnew(p),s))
 return dict(trace=trace,fsync_acknowledgements=syncs,failed=failed,present=present,existing=existing,target=target,side=side,error=error.__name__,helper=helper,cleanup_failure=cleanup)

def matrix(row):
 rows=[];bases={}
 for existing in [False,True]:
  mode='existing' if existing else 'new';base=case('baseline-'+mode,existing);bases[mode]=base['trace']
  for t in base['trace']:
   for side in ['before','after']:
    for error in [Crash,OSError]:rows.append(case(mode+'-'+str(t['index'])+'-'+side+'-'+error.__name__,existing,t['index'],side,error))
  for side in ['before','after']:
   for error in [Crash,OSError]:rows.append(case(mode+'-helper-'+side+'-'+error.__name__,existing,None,side,error,helper=True))
 row.update(baselines=bases,cases=rows,count=len(rows))

def compound(row):
 rows=[]
 for existing in [False,True]:
  base=case('compound-base-'+str(existing),existing)
  for t in base['trace']:
   if t['op']=='fsync' and (t['path'].endswith('.reset-intent') or t['path']==str(ns['T'])):
    rows.append(case('compound-'+str(existing)+'-'+str(t['index']),existing,t['index'],'before',OSError,cleanup=True))
    if t['path']==str(ns['T']):break
 row.update(cases=rows,count=len(rows))

def mode000(row):
 p,s,h=restored('mode000');ip=Path(str(p)+'.reset-intent');ip.write_bytes(b'leftover');old=pair(p);ip.chmod(0);h=hnew(p)
 try:
  try:h.reset_journal('op','unreadable intent')
  except PermissionError:pass
  else:raise AssertionError('permission failure required')
  st=state(h);assert st['resets'][-1]['intent_durable'] is False and st['resets'][-1]['intent_present'] is True
  assert os.path.lexists(ip) and ip.stat().st_mode & 0o777==0 and pair(p)==old
  row.update(failed=st,old_pair_unchanged=True,not_deleted=True,uid=os.getuid())
 finally:ip.chmod(0o600)
 assert h.reset_journal('op','repair permissions then retry')['status']=='completed';held(hfeed(hnew(p),s))
 row['permission_repair_retry_held']=True

def stat_errors(row):
 rows=[]
 for kind in ['stat','lstat']:
  for eno in [errno.EIO,errno.EACCES]:
   p,s,h=restored('stat-'+kind+'-'+str(eno));ip=str(p)+'.reset-intent';Path(ip).write_bytes(b'unsynced');h=hnew(p);old=pair(p);real=getattr(os,kind);fs=os.fsync;syncs=[];calls=[];in_helper=False;helper=h._sync_existing_durably
   def wrapped_helper(path):
    nonlocal in_helper
    in_helper=True
    try:return helper(path)
    finally:in_helper=False
   def failing(path,*a,**kw):
    if in_helper and str(path)==ip:calls.append(kind);raise OSError(eno,'intent classification fails')
    return real(path,*a,**kw)
   def syncing(fd):syncs.append(fpath(fd));return fs(fd)
   def stop(*a,**kw):raise OSError(errno.EIO,'stop at first pair mutation')
   with patch.object(h,'_sync_existing_durably',wrapped_helper),patch.object(os,kind,failing),patch.object(os,'fsync',syncing),patch.object(os,'replace',stop):
    try:h.reset_journal('op','classify existing marker')
    except OSError:pass
   st=state(h);assert pair(p)==old;reported=st['resets'][-1]['intent_durable'];contradiction=reported and ip not in syncs
   rows.append(dict(kind=kind,errno=eno,calls=calls,fsync_acknowledgements=syncs,failed=st,old_pair_unchanged=True,file_fsync_missing_but_durable=contradiction))
 row.update(cases=rows,defect_reproduced=any(x['file_fsync_missing_but_durable'] for x in rows))

out={}
for name,fn in [('intent_matrix',matrix),('compound_failures',compound),('mode000',mode000),('classification_errors',stat_errors)]:
 r={}
 try:fn(r);r['passed']=True
 except Exception as ex:r.update(passed=False,error=repr(ex),traceback=traceback.format_exc())
 out[name]=r;print(name,r['passed'],r.get('error',''),r.get('count',''),flush=True)
(E/'intent7734.json').write_text(json.dumps(out,indent=2,default=str)+'\n');sys.exit(not all(r['passed'] for r in out.values()))
