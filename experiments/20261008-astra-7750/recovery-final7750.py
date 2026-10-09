"""Independent restore-guidance, permissions/EIO, artifact and migration probes."""
import json,os,builtins,errno,traceback,sys
from pathlib import Path
from unittest.mock import patch
E=Path(__file__).resolve().parent
ns={'__file__':str(E/'focused7701.py'),'__name__':'defs'};src=(E/'focused7701.py').read_text();exec(compile(src[:src.index('\nout={}\n')],str(E/'focused7701.py'),'exec'),ns)
for k in ['fresh','hnew','hfeed','history','hb','snapshot','anchor','held','records']:globals()[k]=ns[k]
T=ns['T']=E/'recovery-final7750-cases';T.mkdir(exist_ok=True)
def guide(row):
 p,s,h=fresh('guide7708');assert hb(h);old=p.read_bytes();oldid=anchor(p).read_bytes()
 p.write_bytes(old+b'{torn');n=hfeed(hnew(p),s);held(n);assert n.clear_journal_fence('operator','discard former authorization');held(hfeed(hnew(p),s))
 p.write_bytes(old);anchor(p).write_bytes(oldid)
 # Exact documented procedure: restore both, call clear before serving.
 z=hnew(p);before=snapshot(z);ret=z.clear_journal_fence('operator','restore backup; reissue only wanted rebinds');assert ret is False
 z=hfeed(z,s);assert z._plan_owner=={'a1:p':'i'} and z.journal_status()['healthy']
 row.update(before_feed=before,clear_result=ret,after=snapshot(z),second_restart=snapshot(hfeed(hnew(p),s)),verdict='OPEN: restore warning accurate, but proposed clear_journal_fence call is a no-op on healthy restored pair and discarded authorization returns')
def artifacts(row):
 rows=[]
 for suffix in ['.tmp','.id.tmp','.new-interrupted','.id.new-interrupted','.fence.cleared-old','.fence.tmp.cleared-old']:
  for state in ['first_use','valid_committed']:
   p=T/('artifact7708-'+suffix.replace('.','_')+'-'+state+'.jsonl');s=history()
   if state=='valid_committed':assert hb(hfeed(hnew(p),s))
   stray=Path(str(p)+suffix);stray.write_bytes(b'leftover bytes, not a current journal')
   rs=[hfeed(hnew(p),s) for _ in range(2)]
   for z in rs:assert z.journal_status()['healthy'] and z._plan_owner==({'a1:p':'i'} if state=='valid_committed' else {})
   assert stray.read_bytes()==b'leftover bytes, not a current journal'
   rows.append(dict(suffix=suffix,state=state,restarts=[snapshot(z) for z in rs]))
 row['cases']=rows

def unreadable(row):
 rows=[];real=os.open
 for target in ['journal','anchor']:
  for err in [errno.EACCES,errno.EIO]:
   p,s,h=fresh('unreadable7708-'+target+str(err));assert hb(h);q=p if target=='journal' else anchor(p);old=p.read_bytes();aid=anchor(p).read_bytes()
   def denied(file,*a,**kw):
    if str(file)==str(q):raise OSError(err,os.strerror(err))
    return real(file,*a,**kw)
   with patch.object(os,'open',denied):
    rs=[hfeed(hnew(p),s) for _ in range(2)]
    for z in rs:assert not z.journal_status()['healthy'] and not z._plan_owner and not hb(z)
    try:rs[0].clear_journal_fence('operator','unreadable inspection')
    except OSError:clear='raised'
    else:clear='succeeded' # anchor-only read failure can be repaired by replacing anchor, archive readable
   assert p.read_bytes()==old if clear=='raised' else True
   rows.append(dict(target=target,errno=err,clear=clear,restarts=[snapshot(z) for z in rs]))
  p,s,h=fresh('chmod7708-'+target);assert hb(h);q=p if target=='journal' else anchor(p);q.chmod(0)
  try:
   rs=[hfeed(hnew(p),s) for _ in range(2)]
   for z in rs:assert not z.journal_status()['healthy'] and not z._plan_owner
  finally:q.chmod(0o600)
  rows.append(dict(target=target,actual_chmod_000=True,euid=os.geteuid(),restarts=[snapshot(z) for z in rs]))
 row['cases']=rows

def legacy(row):
 rows=[]
 for version in range(1,5):
  for op in ['owner_rebind','abort_rebind','rebind_pending']:
   p=T/f'legacy7708-{version}-{op}.jsonl';p.write_text(json.dumps(dict(v=version,op=op))+'\n');old=p.read_bytes()
   rs=[hfeed(hnew(p),history()) for _ in range(2)]
   for z in rs:assert z.journal_status()['fence']['kind']=='legacy' and not z._plan_owner and not hb(z)
   assert p.read_bytes()==old and not anchor(p).exists()
   rows.append(dict(version=version,op=op,restarts=[snapshot(z) for z in rs]))
 row['cases']=rows
out={}
for name,fn in [('restore_guidance',guide),('leftover_artifacts',artifacts),('unreadable',unreadable),('legacy_versions',legacy)]:
 r={}
 try:fn(r);r['passed']=True
 except Exception as ex:r.update(passed=False,error=repr(ex),traceback=traceback.format_exc())
 out[name]=r;print(name,r['passed'],r.get('error',''),flush=True)
(E/'recovery-final7750.json').write_text(json.dumps(out,indent=2,default=str)+'\n');sys.exit(not all(x['passed'] for x in out.values()))
