"""Independent classification, namespace error, race and recovery metadata probes."""
import os,sys,json,errno,builtins,traceback,stat
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
E=Path(__file__).resolve().parent
ns={'__file__':str(E/'reset7718.py'),'__name__':'defs'}
src=(E/'reset7718.py').read_text();exec(compile(src[:src.index('\nout={}\n')],str(E/'reset7718.py'),'exec'),ns)
ns['T']=E/'focused7741-cases';ns['T'].mkdir(exist_ok=True)
for k in ['restored','hnew','hfeed','held','state','pair','anchor','fpath']:globals()[k]=ns[k]

def classification(row):
 rows=[]
 for kind in ['stat','lstat']:
  for where in ['first','confirm','every']:
   for eno in [errno.EIO,errno.EACCES]:
    p,s,h=restored('class-'+kind+'-'+where+'-'+str(eno));ip=str(p)+'.reset-intent';Path(ip).write_bytes(b'unsynced');h=hnew(p);old=pair(p);real=getattr(os,kind);fs=os.fsync;calls=[];syncs=[];count=0
    def failing(path,*a,**kw):
     nonlocal count
     if str(path)==ip:
      count+=1
      if where=='every' or count==(1 if where=='first' else 2):calls.append(count);raise OSError(eno,'classification fault')
     return real(path,*a,**kw)
    def syncing(fd):syncs.append(fpath(fd));return fs(fd)
    def stop(*a,**kw):raise OSError(errno.EIO,'first mutation fault')
    with patch.object(os,kind,failing),patch.object(os,'fsync',syncing),patch.object(os,'replace',stop):
     try:h.reset_journal('op','classification')
     except OSError:pass
     st=state(h)
    f=st['status']['fence'];assert pair(p)==old and st['pending']==0
    if kind=='lstat':
     assert calls and not f['intent_durable'] and ip not in syncs
     if where=='every':assert f['intent_present'] is None and f['presence_error'] and st['status']['reset_in_progress'] is None
    else:assert not calls and f['intent_durable'] and ip in syncs # stat no longer called
    rows.append(dict(kind=kind,where=where,errno=eno,calls=calls,fsyncs=syncs,state=st,old_pair_unchanged=True))
 row.update(cases=rows,count=len(rows),passed=True)

def races(row):
 rows=[]
 for mode in ['swap_regular','swap_symlink','swap_directory','fstat_error','fstat_nonregular','fstat_device','nofollow_missing']:
  p,s,h=restored('race-'+mode);ip=Path(str(p)+'.reset-intent');ip.write_bytes(b'intent');h=hnew(p);old=pair(p);op=os.open;fs=os.fsync;fst=os.fstat;syncs=[];flags=[];hit=False
  def opening(path,flag,*a,**kw):
   nonlocal hit
   if str(path)==str(ip):
    hit=True;flags.append(flag)
    if mode in ['swap_regular','swap_symlink','swap_directory','nofollow_missing']:
     ip.rename(str(ip)+'.original')
     if mode=='swap_regular':ip.write_bytes(b'replacement')
     elif mode=='swap_directory':ip.mkdir()
     else:ip.symlink_to(ip.name+'.original')
   return op(path,flag,*a,**kw)
  def fstat(fd):
   if fpath(fd).startswith(str(ip)):
    if mode=='fstat_error':raise OSError(errno.EIO,'fstat fault')
    x=fst(fd)
    if mode in ['fstat_nonregular','fstat_device']:
     a=list(x);a[0]=stat.S_IFDIR|0o700 if mode=='fstat_nonregular' else a[0];a[2]=a[2]+1 if mode=='fstat_device' else a[2];return os.stat_result(a)
    return x
   return fst(fd)
  def syncing(fd):syncs.append(fpath(fd));return fs(fd)
  with ExitStack() as stack:
   stack.enter_context(patch.object(os,'open',opening));stack.enter_context(patch.object(os,'fstat',fstat));stack.enter_context(patch.object(os,'fsync',syncing))
   if mode=='nofollow_missing':stack.enter_context(patch.object(os,'O_NOFOLLOW',0))
   # Same inode reached through a symlink is accepted without O_NOFOLLOW. Record portability limit.
   try:h.reset_journal('op','TOCTOU');raised=False
   except OSError:raised=True
  st=state(h)
  if mode!='nofollow_missing':assert raised and hit and pair(p)==old and not st['status']['fence']['intent_durable'] and not syncs
  rows.append(dict(mode=mode,raised=raised,open_flags=flags,host_O_NOFOLLOW=os.O_NOFOLLOW,fsyncs=syncs,state=st,old_pair_unchanged=pair(p)==old))
 row.update(cases=rows,count=len(rows),passed=True)

def checks(row):
 rows=[]
 for operation in ['startup','reset','clear']:
  for target in ['intent','journal','anchor','fence','fence_tmp']:
   for eno in [errno.EIO,errno.EACCES,errno.ENOTDIR]:
    name='check-'+operation+'-'+target+'-'+str(eno);p,s,h=restored(name);ip=str(p)+'.reset-intent';paths=dict(intent=ip,journal=str(p),anchor=str(anchor(p)),fence=str(p)+'.fence',fence_tmp=str(p)+'.fence.tmp');bad=paths[target];ls=os.lstat;op=os.open;calls=[]
    if operation=='clear':Path(ip).write_bytes(b'intent');h=hnew(p)
    def lstat(path,*a,**kw):
     if str(path)==bad:calls.append('lstat');raise OSError(eno,'strict presence fault')
     return ls(path,*a,**kw)
    def opening(path,*a,**kw):
     # .id is inspected by open/read, not lstat; clear similarly reads journal directly.
     if str(path)==bad and (target=='anchor' or (operation=='clear' and target=='journal')):
      calls.append('open');raise OSError(eno,'strict read fault')
     return op(path,*a,**kw)
    with patch.object(os,'lstat',lstat),patch.object(os,'open',opening):
     raised=False
     try:
      if operation=='startup':h=hnew(p)
      elif operation=='reset':h.reset_journal('op','strict check')
      else:h.clear_journal_fence('op','strict check')
     except OSError:raised=True
     st=state(h)
    # Clearance never reads old anchor, replacing it only after durable journal replacement.
    applicable=True # clear now lstat-checks the anchor before replacement
    if applicable:
     assert calls and not st['status']['healthy']
     assert raised==(operation!='startup')
     if operation=='startup':
      assert st['pending']==0 and st['status']['fence']['kind']==('reset_incomplete' if target=='intent' else 'unwritable')
      if target=='intent':assert st['status']['reset_in_progress'] is None and h._reset_discard
     if operation=='reset':assert st['pending']==0
     hfeed(h,s);held(h)
    rows.append(dict(operation=operation,target=target,errno=eno,applicable=applicable,calls=calls,raised=raised,state=st))
 row.update(cases=rows,count=len(rows),passed=True)

def metadata(row):
 rows=[]
 # Fail each completed helper boundary and verify a presence error never makes disk-progress claims up.
 for mode in ['confirm','rename','anchor_copy','new_anchor','new_journal','unlink']:
  p,s,h=restored('meta-'+mode);ip=str(p)+'.reset-intent';old=pair(p);ls=os.lstat;rep=os.replace;un=os.unlink;wf=h._write_file_durably;wa=h._write_anchor;rd=h._replace_durably;active=False
  def fault():
   nonlocal active
   active=True;raise OSError(errno.EIO,'after '+mode)
  def lstat(path,*a,**kw):
   if active and str(path)==ip:raise OSError(errno.EACCES,'presence unavailable')
   return ls(path,*a,**kw)
  def write(path,*a,**kw):
   r=wf(path,*a,**kw)
   if (mode=='confirm' and str(path)==ip) or (mode=='anchor_copy' and str(path).startswith(str(anchor(p))+'.reset-')):fault()
   return r
  def replace(a,b,*c,**kw):
   r=rep(a,b,*c,**kw)
   if mode=='rename' and str(a)==str(p):fault()
   return r
  def writeanchor(*a,**kw):
   r=wa(*a,**kw)
   if mode=='new_anchor':fault()
   return r
  def replace_durably(path,*a,**kw):
   r=rd(path,*a,**kw)
   if mode=='new_journal' and str(path)==str(p):fault()
   return r
  def unlink(path,*a,**kw):
   r=un(path,*a,**kw)
   if mode=='unlink' and str(path)==ip:fault()
   return r
  with patch.object(os,'lstat',lstat),patch.object(os,'replace',replace),patch.object(os,'unlink',unlink),patch.object(h,'_write_file_durably',write),patch.object(h,'_write_anchor',writeanchor),patch.object(h,'_replace_durably',replace_durably):
   try:h.reset_journal('op','metadata boundary')
   except OSError:pass
   st=state(h)
  f=st['status']['fence'];assert active and f['intent_present'] is None and f['presence_error'] and not f['intent_durable']
  assert f['completed_steps']==st['resets'][-1]['completed_steps']
  assert f['presence_error']==st['resets'][-1]['presence_error']
  if pair(p)!=old:assert 'old journal and .id are unchanged' not in f['error']
  assert 'marker was unlinked' not in f['error']
  rows.append(dict(mode=mode,state=st,actual_intent_present=os.path.lexists(ip),old_pair_unchanged=pair(p)==old,audit_has_presence_error='presence_error' in st['resets'][-1]))
 row.update(cases=rows,count=len(rows),passed=True)

def dangling_anchor(row):
 p=ns['T']/'dangling-anchor.jsonl';a=anchor(p);a.symlink_to(a.name+'.missing');h=hnew(p)
 row.update(anchor_initially_dangling=True,anchor_replaced=not a.is_symlink(),journal_created=p.exists(),state=state(h),passed=True)
 assert not row['anchor_replaced'] and not row['journal_created'] and h.journal_status()['fence']['kind']=='identity'

out={}
for name,fn in [('classification',classification),('races',races),('strict_checks',checks),('metadata_boundaries',metadata),('dangling_anchor',dangling_anchor)]:
 r={}
 try:fn(r)
 except Exception as ex:r.update(passed=False,error=repr(ex),traceback=traceback.format_exc())
 out[name]=r;print(name,r['passed'],r.get('error',''),flush=True)
(E/'focused7741.json').write_text(json.dumps(out,indent=2,default=str)+'\n');sys.exit(not all(x['passed'] for x in out.values()))
