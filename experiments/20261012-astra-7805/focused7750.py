"""Independent namespace/recovery witnesses. Expected defect reproduction is not a safety pass."""
import os,sys,json,errno,stat,traceback,multiprocessing,time
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
E=Path(__file__).resolve().parent
ns={'__file__':str(E/'reset7718.py'),'__name__':'defs'}
src=(E/'reset7718.py').read_text();exec(compile(src[:src.index('\nout={}\n')],str(E/'reset7718.py'),'exec'),ns)
for k in ['hnew','hfeed','held','state','pair','anchor','history','hb','hr','fpath']:globals()[k]=ns[k]
T=E/'focused7750-cases';T.mkdir(exist_ok=True)
def snap(p):
 st=os.lstat(p)
 return dict(mode=st.st_mode,inode=st.st_ino,device=st.st_dev,link=os.readlink(p) if stat.S_ISLNK(st.st_mode) else None,data=p.read_bytes().hex() if stat.S_ISREG(st.st_mode) else None)
def make(p,kind,target):
 if kind in ['dangling','valid']:p.symlink_to(target)
 elif kind=='directory':p.mkdir();(p/'preserved').write_text('directory evidence')
 else:os.mkfifo(p)
def variants(row):
 rows=[]
 for which in ['journal','anchor']:
  for other in ['present','absent']:
   for kind in ['dangling','valid','directory','fifo']:
    for method in ['clear','reset']:
     d=T/('-'.join([which,other,kind,method]));d.mkdir();p=d/'journal';s=history();h=hfeed(hnew(p),s);assert hb(h)
     bad=p if which=='journal' else anchor(p);good=anchor(p) if which=='journal' else p
     target=d/'referent'
     if kind=='valid':target.write_bytes(bad.read_bytes())
     target_before=target.read_bytes() if target.exists() else None
     bad.unlink()
     if other=='absent':good.unlink()
     make(bad,kind,target);before=snap(bad);good_before=snap(good) if other=='present' else None
     starts=[]
     for _ in range(2):
      h=hnew(p);f=h.journal_status()['fence'];assert f['kind']=='identity' and f['artifacts']==[str(bad)]
      assert not h._journal_pending and not h._journal_applied and snap(bad)==before
      assert (snap(good) if os.path.lexists(good) else None)==good_before
      starts.append(state(h))
     if method=='clear':assert h.clear_journal_fence('op','preserve nonregular entry')
     else:assert h.reset_journal('op','preserve nonregular entry')['status']=='completed'
     aside=[q for q in d.iterdir() if q.name.startswith(bad.name+'.') and q.name!=anchor(p).name and snap(q)['inode']==before['inode']]
     assert len(aside)==1 and snap(aside[0])==before
     if kind=='directory':assert (aside[0]/'preserved').read_text()=='directory evidence'
     assert stat.S_ISREG(os.lstat(p).st_mode) and stat.S_ISREG(os.lstat(anchor(p)).st_mode)
     assert (target.read_bytes() if target.exists() else None)==target_before
     z=hfeed(hnew(p),s);held(z);assert z.journal_status()['healthy']
     rows.append(dict(which=which,other=other,kind=kind,method=method,entry_preserved=before,archive=str(aside[0]),starts=starts,restart=state(z)))
 row.update(cases=rows,count=len(rows),passed=True)
def reader_errors(row):
 rows=[]
 for which in ['journal','anchor']:
  for operation in ['lstat','open','fstat','read','close']:
   for eno in [errno.EIO,errno.EACCES,errno.ENOTDIR,errno.ENOENT]:
    d=T/('error-'+which+'-'+operation+'-'+str(eno));d.mkdir();p=d/'journal';h=hnew(p);bad=p if which=='journal' else anchor(p);old=pair(p);real=getattr(os,operation);hits=[]
    def failing(*a,**kw):
     path=str(a[0]) if operation in ['lstat','open'] else fpath(a[0])
     if path==str(bad):
      hits.append(operation)
      if operation=='close':real(*a,**kw)
      raise OSError(eno,'injected '+operation,path)
     return real(*a,**kw)
    with patch.object(os,operation,failing):h=hnew(p)
    f=h.journal_status()['fence'];assert hits and pair(p)==old and not h._journal_pending
    expected='identity' if eno==errno.ENOENT and operation=='lstat' else 'unwritable'
    assert f['kind']==expected,(which,operation,eno,f)
    rows.append(dict(which=which,operation=operation,errno=eno,hits=hits,state=state(h),unchanged=True))
 row.update(cases=rows,count=len(rows),passed=True)
def reader_swaps(row):
 rows=[]
 for which in ['journal','anchor']:
  for mode in ['missing','regular','symlink','directory']:
   d=T/('swap-'+which+'-'+mode);d.mkdir();p=d/'journal';h=hnew(p);bad=p if which=='journal' else anchor(p);saved=Path(str(bad)+'.original');op=os.open;hit=[]
   def opening(path,*a,**kw):
    if str(path)==str(bad) and not hit:
     hit.append(True);bad.rename(saved)
     if mode=='regular':bad.write_bytes(saved.read_bytes())
     elif mode=='symlink':bad.symlink_to(saved)
     elif mode=='directory':bad.mkdir()
    return op(path,*a,**kw)
   with patch.object(os,'open',opening):h=hnew(p)
   assert hit and h.journal_status()['fence']['kind']=='unwritable' and not h._journal_pending
   rows.append(dict(which=which,mode=mode,state=state(h)))
 row.update(cases=rows,count=len(rows),passed=True)
def runtime(row):
 rows=[]
 for which in ['journal','anchor']:
  for kind in ['dangling','valid','directory','fifo']:
   for method in ['verify','append']:
    if kind=='fifo' and which=='journal' and method=='verify':continue # blocking case isolated below
    d=T/('runtime-'+which+'-'+kind+'-'+method);d.mkdir();p=d/'journal';s=history();h=hfeed(hnew(p),s);bad=p if which=='journal' else anchor(p);target=d/'original';bad.rename(target);make(bad,kind,target if kind!='dangling' else d/'absent');before=snap(bad)
    result=h.verify_journal() if method=='verify' else hb(h)
    assert not result and snap(bad)==before and not h._plan_owner
    st=state(h);defect=which=='journal' and kind=='directory' and method=='append'
    if defect:assert st['status']['healthy'] and st['status']['fence'] is None
    else:assert st['status']['fence']['kind']=='changed'
    rows.append(dict(which=which,kind=kind,method=method,result=result.as_dict() if hasattr(result,'as_dict') else result,state=st,missing_changed_fence=defect))
 row.update(cases=rows,count=len(rows),directory_append_defect_reproduced=True,passed=True)
def blocking_child(mode,path,conn):
 p=Path(path);h=hnew(p);op=os.open
 if mode=='runtime_verify':p.unlink();os.mkfifo(p);conn.send('about to verify FIFO');h.verify_journal()
 else:
  bad=p if mode=='startup_journal' else anchor(p)
  def opening(path,*a,**kw):
   if str(path)==str(bad):
    bad.unlink();os.mkfifo(bad);conn.send('lstat regular; FIFO installed before os.open')
   return op(path,*a,**kw)
  with patch.object(os,'open',opening):hnew(p)
 conn.send('returned')
def blocking(row):
 rows=[]
 for mode in ['runtime_verify','startup_journal','startup_anchor']:
  d=T/('blocking-'+mode);d.mkdir();p=d/'journal';a,b=multiprocessing.Pipe(False);proc=multiprocessing.Process(target=blocking_child,args=(mode,str(p),b));proc.start();assert a.poll(5);entered=a.recv();proc.join(0.5);blocked=proc.is_alive();assert blocked
  # Unblock with a writer: the regular-file fstat check then finally fences.
  bad=anchor(p) if mode=='startup_anchor' else p;fd=os.open(bad,os.O_WRONLY|os.O_NONBLOCK);os.close(fd);proc.join(5)
  if proc.is_alive():proc.terminate();proc.join();raise AssertionError('did not unblock')
  assert a.poll(1) and a.recv()=='returned' and proc.exitcode==0
  rows.append(dict(mode=mode,entered=entered,blocked_without_fifo_writer=blocked,wait_seconds=0.5,returned_after_writer_open=True,exit_code=proc.exitcode))
 row.update(cases=rows,count=len(rows),passed=True,defect_reproduced=True)
def directory_links(row):
 rows=[]
 for method in ['startup','verify','append','clear','reset']:
  d=T/('parent-'+method);d.mkdir();actual=d/'actual';actual.mkdir();alias=d/'linked';alias.symlink_to(actual,target_is_directory=True);p=alias/'journal';s=history();h=hnew(p)
  if method=='verify':assert h.verify_journal()
  elif method=='append':hfeed(h,s);assert hb(h)
  elif method=='clear':p.write_bytes(p.read_bytes()+b'{');h=hnew(p);assert h.clear_journal_fence('op','parent symlink')
  elif method=='reset':assert h.reset_journal('op','parent symlink')['status']=='completed'
  assert h.journal_status()['healthy'] and (actual/'journal').is_file()
  rows.append(dict(method=method,symlink_followed=True,actual_target=str(actual),state=state(h)))
 row.update(cases=rows,count=len(rows),passed=True,scope='O_NOFOLLOW protects only final component; static directory symlink follows for all operations. Protected stable parent namespace is required, not enforced.')
def archives(row):
 d=T/'archives';d.mkdir();p=d/'journal';s=history();h=hfeed(hnew(p),s);assert hb(h);old=pair(p);h=hnew(p);assert h.reset_journal('op','archive trace')['status']=='completed'
 for suffix in ['.fenced-z','.reset-z','.cleared-z']:
  Path(str(p)+suffix).write_bytes(old[str(p)])
  Path(str(anchor(p))+suffix).symlink_to(anchor(p))
 reads=[];op=os.open
 def opening(path,flags,*a,**kw):
  reads.append(dict(path=str(path),flags=flags))
  assert not any(t in str(path) for t in ['.fenced-','.reset-','.cleared-']) or (flags&os.O_ACCMODE)==os.O_WRONLY,(path,flags)
  return op(path,flags,*a,**kw)
 with patch.object(os,'open',opening):
  for _ in range(2):z=hfeed(hnew(p),s);held(z);assert z.verify_journal()
  assert hb(z)
  z=hfeed(hnew(p),s);assert z._plan_owner=={'a1:p':'i'}
 row.update(passed=True,opens=reads,archive_read_count=0,full_replay_held_after_reset=True,reissue_replays=True)
out={}
for name,fn in [('nonregular_variants',variants),('reader_errors',reader_errors),('reader_swaps',reader_swaps),('runtime',runtime),('fifo_blocking',blocking),('directory_symlinks',directory_links),('archive_trace',archives)]:
 r={}
 try:fn(r)
 except Exception as ex:r.update(passed=False,error=repr(ex),traceback=traceback.format_exc())
 out[name]=r;print(name,r['passed'],r.get('error',''),flush=True)
(E/'focused7750.json').write_text(json.dumps(out,indent=2,default=str)+'\n');sys.exit(not all(r['passed'] for r in out.values()))
