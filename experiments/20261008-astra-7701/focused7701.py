"""Independent identity, runtime, result and restore probes. Defect assertions are not approvals."""
import os,json,hashlib,copy,traceback,sys
from pathlib import Path
from unittest.mock import patch
E=Path(__file__).resolve().parent
ns={'__file__':str(E/'followup7694.py'),'__name__':'defs'}
src=(E/'followup7694.py').read_text();exec(compile(src[:src.index('\nout={}\n')],str(E/'followup7694.py'),'exec'),ns)
for k in ['fresh','history','two','hb','bindq','hfeed','hnew','v','held','records','restarts','fpath','HiveReducer','hr']:globals()[k]=ns[k]
T=ns['T']
def anchor(p):return Path(str(p)+'.id')
def snapshot(h):return dict(view=v(h),last_result=h.last_rebind_result.as_dict() if h.last_rebind_result else (h.last_rebind_result.as_dict() if h.last_rebind_result is not None else None),audit=h.owner_rebinds)
def restore(row):
 p,s,h=fresh('identity-restore');assert hb(h);old=p.read_bytes();oldid=anchor(p).read_bytes();p.write_bytes(old+b'{"torn":')
 n=hfeed(hnew(p),s);held(n);assert n.clear_journal_fence('reviewer','discard old authorization, leave held')
 ar=Path(n.journal_status()['fence_clearances'][-1]['archived']);assert ar.read_bytes()==old+b'{"torn":'
 reset=p.read_bytes();newid=anchor(p).read_bytes();assert newid!=oldid;held(hfeed(hnew(p),s));rows=[]
 for mode,bad in [('append_archived_prefix',reset+old),('archived_whole_file',ar.read_bytes()),('replace_with_old_valid_journal',old),('replace_with_archived_clean_prefix',ar.read_bytes()[:-len(b'{"torn":')])]:
  p.write_bytes(bad);rs=restarts(p,s)
  for x in rs:held(x);assert not x.journal_status()['healthy'] and not hb(x)
  rows.append(dict(mode=mode,restarts=[snapshot(x) for x in rs],hashes_recomputed=False,anchor_retained=True))
 # Explicit accepted threat boundary: rolling BOTH files back revives the discarded authorization.
 p.write_bytes(old);anchor(p).write_bytes(oldid);z=hfeed(hnew(p),s);assert z._plan_owner=={'a1:p':'i'} and z.journal_status()['healthy']
 row.update(cases=rows,joint_rollback=snapshot(z),joint_rollback_requires_documentation=True,verdict='Prior single-file rollback witness CLOSED; two-file rollback remains possible')
def runtime(row):
 rows=[]
 for mode in ['prefix_edit_next_rebind','prefix_edit_verify','missing_journal','missing_anchor','bad_anchor','changed_anchor','suffix_append','unchanged']:
  p,s,h=fresh('runtime7701-'+mode,two());assert hb(h);data=p.read_bytes();before=snapshot(h)
  if mode.startswith('prefix_edit'):
   bad=data.replace(b'case-proof',b'case-prooX',1);assert bad!=data and len(bad)==len(data);p.write_bytes(bad)
  elif mode=='missing_journal':p.unlink()
  elif mode=='missing_anchor':anchor(p).unlink()
  elif mode=='bad_anchor':anchor(p).write_bytes(b'{')
  elif mode=='changed_anchor':anchor(p).write_text(json.dumps(dict(v=5,journal_id='changed')))
  elif mode=='suffix_append':p.write_bytes(data+b'\n')
  disk=p.read_bytes() if p.exists() else None
  if mode=='prefix_edit_next_rebind':
   r=bindq(h);assert not r and r.status=='refused';result=r.as_dict()
  else:result=h.verify_journal();assert result==(mode=='unchanged')
  assert h.journal_status()['healthy']==(mode=='unchanged')
  assert (p.read_bytes() if p.exists() else None)==disk
  rows.append(dict(mode=mode,result=result,before=before,after=snapshot(h),restart=[snapshot(x) for x in restarts(p,s)]))
 row['cases']=rows
class Crash(BaseException):pass
def startup(row):
 rows=[]
 # Stop exactly between durable journal creation and anchor creation.
 p=T/'create-anchor-crash.jsonl'
 with patch.object(HiveReducer,'_write_anchor',side_effect=Crash('before anchor')):
  try:hnew(p)
  except Crash:pass
  else:raise AssertionError('not interrupted')
 assert p.exists() and not anchor(p).exists() and len(records(p))==1
 h=hfeed(hnew(p),history());assert h.journal_status()['healthy'] and anchor(p).exists()
 r=hb(h);assert r and r.durable
 rows.append(dict(mode='crash_between_journal_and_anchor',restart=snapshot(h),returned=r.as_dict(),verdict='OPEN Medium explicit crash-fencing requirement: silently adopts header-only journal and permits durable rebind'))
 for mode in ['journal_missing_id_present','id_missing_committed_journal','id_missing_header_only','empty_journal_id_present','both_missing','legacy_marker_header_adoption']:
  p,s,h=fresh('startup7701-'+mode)
  if mode=='id_missing_committed_journal':assert hb(h)
  if mode in ['journal_missing_id_present','both_missing']:p.unlink()
  if mode in ['id_missing_committed_journal','id_missing_header_only','both_missing','legacy_marker_header_adoption']:anchor(p).unlink()
  if mode=='empty_journal_id_present':p.write_bytes(b'')
  if mode=='legacy_marker_header_adoption':Path(str(p)+'.fence').write_bytes(b'legacy fence')
  z=hfeed(hnew(p),s);first=snapshot(z)
  expected=mode in ['id_missing_header_only','both_missing','legacy_marker_header_adoption']
  assert z.journal_status()['healthy']==expected
  r=hb(z)
  assert bool(r)==expected
  later=restarts(p,s)
  rows.append(dict(mode=mode,first=first,result=r.as_dict(),later=[snapshot(x) for x in later]))
 row['cases']=rows
def prefixes(row):
 p,s,h=fresh('prefix7701-base',two());assert hb(h) and bindq(h);lines=p.read_bytes().splitlines(keepends=True);a=anchor(p).read_bytes();rows=[]
 for k in range(len(lines)+1):
  d=T/('prefix7701-'+str(k)+'.jsonl');d.write_bytes(b''.join(lines[:k]));anchor(d).write_bytes(a);rs=restarts(d,s)
  expected={} if k<3 else {'a1:p':'i'}
  if k==5:expected['a1:q']='j'
  for z in rs:assert z._plan_owner==expected and z.journal_status()['healthy']==(k>0)
  rows.append(dict(records=k,restarts=[snapshot(z) for z in rs]))
 row['cases']=rows
def legacy4(row):
 src=Path(os.environ['HIVE_SRC'])/'experiments/20261008-astra-7694/journal-followup7694/commit-never-written.jsonl'
 p=T/'legacy4-authentic.jsonl';p.write_bytes(src.read_bytes());before=p.read_bytes();h=hfeed(hnew(p),history());held(h)
 assert not h.journal_status()['healthy'] and not hb(h);old=snapshot(h)
 assert h.clear_journal_fence('reviewer','legacy4 inspected');assert Path(h.journal_status()['fence_clearances'][-1]['archived']).read_bytes()==before
 held(hfeed(hnew(p),history()));assert hb(h)
 row.update(source=str(src),sha256=hashlib.sha256(before).hexdigest(),before=old,after=snapshot(hfeed(hnew(p),history())))
out={}
for name,fn in [('archive_restore',restore),('runtime_integrity',runtime),('startup_identity',startup),('clean_prefixes',prefixes),('legacy4',legacy4)]:
 r={}
 try:fn(r);r['passed']=True
 except Exception as e:r.update(passed=False,error=repr(e),traceback=traceback.format_exc())
 out[name]=r;print(name,r['passed'],r.get('error',''),flush=True)
(E/'focused7701.json').write_text(json.dumps(out,indent=2,default=str)+'\n')
sys.exit(not all(r['passed'] for r in out.values()))
