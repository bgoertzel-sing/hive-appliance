"""Independent public-path witnesses; each case is a hard-timeout child process.
Only os.open/lstat are observed or fault-injected; no reducer method is replaced.
"""
import os,sys,json,subprocess,tempfile,stat,errno
from pathlib import Path
from unittest.mock import patch
E=Path(__file__).resolve().parent
sys.path.insert(0,os.environ['HIVE_SRC'])
from tests.test_astra7638 import run
from tests.test_astra7656 import S
import hive.reducer as hr

def case(name):
 with tempfile.TemporaryDirectory(prefix='independent7805-') as td:
  jp=str(Path(td)/'journal'); h=run(S,journal=jp); assert h.journal_status()['healthy']
  real_open=os.open;real_lstat=os.lstat;calls=[];done=False
  def swap(p,kind):
   os.rename(p,p+'.original')
   if kind=='fifo':os.mkfifo(p)
   elif kind=='directory':os.mkdir(p)
   elif kind=='symlink':os.symlink(p+'.original',p)
  def observe(p,flags,*a,**k):
   if os.fspath(p)==jp:calls.append(flags)
   return real_open(p,flags,*a,**k)
  if name.startswith(('append-','verify-')):
   op,kind=name.split('-');swap(jp,kind)
   with patch.object(os,'open',observe):
    result=h.rebind_plan_owner('a1','p','i',actor='reviewer',reason=name) if op=='append' else h.verify_journal()
   assert not result
   assert h.journal_status()['fence']['kind']=='changed' and not h.journal_status()['healthy']
   assert not h._plan_owner and not h._journal_applied
   assert calls and all(f&os.O_NONBLOCK and f&os.O_NOFOLLOW for f in calls)
   if op=='append':assert any(f&os.O_APPEND and f&os.O_RDWR for f in calls),calls
   # Explicit clearance preserves the malformed entry and never replays a refusal.
   assert h.clear_journal_fence('reviewer','recover nonregular')
   n=run(S,journal=jp);assert not n._plan_owner and n.journal_status()['healthy']
   return dict(case=name,flags=calls,real_append_open=op=='append',refused=True,changed=True,restart_held=True)
  if name.startswith('errno-'):
   code=getattr(errno,name.split('-')[1]);hit=[]
   def failing(p,flags,*a,**k):
    if os.fspath(p)==jp and flags&os.O_APPEND:hit.append(flags);raise OSError(code,'injected append open',jp)
    return real_open(p,flags,*a,**k)
   with patch.object(os,'open',failing):result=h.rebind_plan_owner('a1','p','i',actor='reviewer',reason=name)
   assert hit and not result and not h._plan_owner and h.journal_status()['fence']['kind']=='changed'
   assert not run(S,journal=jp)._plan_owner
   return dict(case=name,errno=code,real_append_path=True,changed=True,restart_held=True)
  if name.startswith(('startup-','race-','intent-')):
   which=name.split('-')[-1];p=jp if which=='journal' else jp+'.id' if which=='anchor' else jp+'.reset-intent'
   if which=='marker':
    h=hr.HiveReducer(rebind_journal=jp) # reset is valid only before replay
    Path(p).write_text('intent')
   def lst(q,*a,**k):
    nonlocal done
    st=real_lstat(q,*a,**k)
    if os.fspath(q)==p and not done:done=True;swap(p,'fifo')
    return st
   if name.startswith('startup-'):swap(p,'fifo')
   if which=='marker':
    def intent_open(q,flags,*a,**k):
     nonlocal done
     if os.fspath(q)==p and not flags&os.O_CREAT and not done:
      done=True;swap(p,'fifo')
     return real_open(q,flags,*a,**k)
    with patch.object(os,'open',intent_open):
     try:h.reset_journal('reviewer','intent FIFO race');raise AssertionError('reset accepted FIFO')
     except OSError:pass
    assert done and not h.journal_status()['healthy']
    assert h.journal_status()['fence']['intent_durable'] is False
   else:
    with patch.object(os,'lstat',lst) if name.startswith('race-') else patch.object(os,'open',observe):n=run(S,journal=jp)
    assert not n.journal_status()['healthy'] and not n._plan_owner and not n._journal_pending
    if name.startswith('race-'):assert done
   assert stat.S_ISFIFO(real_lstat(p).st_mode)
   return dict(case=name,rejected=True,fifo_preserved=True)
  if name=='exclusive-create-fifo':
   p=jp+'.new';os.mkfifo(p)
   try:h._write_file_durably(p,b'x');raise AssertionError('accepted')
   except FileExistsError:pass
   assert stat.S_ISFIFO(real_lstat(p).st_mode)
   return dict(case=name,rejected_before_write=True)
  raise AssertionError(name)

if len(sys.argv)>1:
 print(json.dumps(case(sys.argv[1])));sys.exit()
names=[f'{op}-{kind}' for op in ['append','verify'] for kind in ['fifo','directory','symlink']]+['errno-'+x for x in ['EISDIR','ENXIO','ELOOP','ENOTDIR']]+[f'{op}-{kind}' for op in ['startup','race'] for kind in ['journal','anchor']]+['intent-race-marker','exclusive-create-fifo']
results=[]
for n in names:
 try:
  p=subprocess.run([sys.executable,__file__,n],capture_output=True,text=True,timeout=5)
  row=dict(case=n,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr,timed_out=False)
 except subprocess.TimeoutExpired as ex:row=dict(case=n,exit_code=None,timed_out=True,stdout=str(ex.stdout),stderr=str(ex.stderr))
 results.append(row)
(E/'independent7805-qualified.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2));assert all(x['exit_code']==0 and not x['timed_out'] for x in results)
