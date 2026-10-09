"""Adversarial inter-operation namespace probes: explicit excluded-scope evidence."""
import os,json
from pathlib import Path
from unittest.mock import patch
E=Path(__file__).resolve().parent
ns={'__file__':str(E/'reset7718.py'),'__name__':'defs'};src=(E/'reset7718.py').read_text();exec(compile(src[:src.index('\nout={}\n')],str(E/'reset7718.py'),'exec'),ns)
for k in ['hnew','hfeed','history','hb','hr','state','anchor']:globals()[k]=ns[k]
T=E/'namespace-scope7750-final-cases';T.mkdir();rows=[]
# A new entry after absence checks is not covered by the initial strict read.
d=T/'first-use';d.mkdir();p=d/'journal';create=hr.HiveReducer._create_journal

def creation(self,path):
 anchor(Path(path)).symlink_to('missing-created-after-check');return create(self,path)
with patch.object(hr.HiveReducer,'_create_journal',creation):h=hnew(p)
assert h.journal_status()['healthy'] and not anchor(p).is_symlink()
rows.append(dict(case='post-absence-entry-insertion',new_symlink_overwritten=True,state=state(h)))
# Operator clear has a lstat->replace window for an anchor that was regular.
d=T/'clear';d.mkdir();p=d/'journal';h=hnew(p);p.write_bytes(p.read_bytes()+b'{');h=hnew(p);ls=os.lstat;hit=[]
def lstat(path,*a,**kw):
 st=ls(path,*a,**kw)
 if str(path)==str(anchor(p)) and not hit:
  hit.append(True);anchor(p).rename(d/'saved-id');anchor(p).symlink_to('missing-after-lstat')
 return st
with patch.object(os,'lstat',lstat):assert h.clear_journal_fence('op','namespace race')
assert hit and not anchor(p).is_symlink() and not list(d.glob('journal.id.cleared-*'))
rows.append(dict(case='clear-anchor-post-lstat-symlink',new_symlink_overwritten_without_archive=True,state=state(h)))
# Stable ancestor symlinks work; concurrently retargeting one breaks path/FD binding.
d=T/'parent-retarget';d.mkdir();a=d/'a';b=d/'b';a.mkdir();b.mkdir();link=d/'live';link.symlink_to(a,target_is_directory=True);p=link/'journal';h=hfeed(hnew(p),history())
for name in ['journal','journal.id']:(b/name).write_bytes((a/name).read_bytes())
before=(b/'journal').read_bytes();op=os.open;hit=[]
def opening(path,flags,*args,**kw):
 fd=op(path,flags,*args,**kw)
 if str(path)==str(p) and flags&os.O_RDWR:
  hit.append(True)
  if len(hit)==2:
   (b/'journal').write_bytes((a/'journal').read_bytes())
   link.unlink();link.symlink_to(b,target_is_directory=True)
 return fd
with patch.object(os,'open',opening):result=hb(h)
assert result and hit and h.journal_status()['healthy'] and (b/'journal').read_bytes()!=before and (a/'journal').read_bytes()!=(b/'journal').read_bytes()
z=hfeed(hnew(p),history());assert not z._plan_owner
rows.append(dict(case='parent-retarget-after-journal-open',result=result.as_dict(),live=state(h),restart=state(z),current_path_has_pending_but_no_commit=True,old_directory_received_commit=True))
result=dict(passed=True,cases=rows,count=len(rows),classification='Not an additional in-scope durability defect: requires a writer mutating the namespace during the operation. Demonstrates why stable protected ancestors, one writer and stopped-service recovery are mandatory; O_NOFOLLOW is not a namespace-locking mechanism.')
(E/'namespace-scope7750-final.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
