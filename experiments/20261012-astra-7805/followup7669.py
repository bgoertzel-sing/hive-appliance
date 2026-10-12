"""Focused new concerns from primary review; no full-suite repetition."""
import hashlib,json,os,sys,traceback
from pathlib import Path
from unittest.mock import patch
E=Path(__file__).resolve().parent
src=(E/'review7669.py').read_text();q={'__file__':str(E/'review7669.py'),'__name__':'followup_defs'};exec(compile(src[:src.index('\nout={}\n')],str(E/'review7669.py'),'exec'),q)
I,P,R,hnew,hfeed,hop,hb,v,events,fpath,held,fenced,HiveReducer=[q[k] for k in ['I','P','R','hnew','hfeed','hop','hb','v','events','fpath','held','fenced','HiveReducer']]
T=E/'journal-followup7669';T.mkdir(exist_ok=True);q['T']=T
out={}
def save(): (E/'followup7669.json').write_text(json.dumps(out,indent=2,default=str)+'\n')
def prior_record(row):
 s=q['history']()+[I('j','q'),P('q'),R('qrc','q','j'),P('q','j')];jp=T/'prior-record.jsonl';h=hfeed(hnew(jp),s);assert hb(h);good=jp.read_bytes();real=os.fsync;calls=[]
 def sync(fd):
  if fpath(fd)==str(jp):
   calls.append(dict(size=jp.stat().st_size,owner=dict(h._plan_owner)))
   if len(calls)==1:raise OSError('second append fails')
  return real(fd)
 with patch.object(os,'fsync',sync):assert not h.rebind_plan_owner('a1','q','j',actor='op',reason='second-op')
 assert len(calls)==2 and calls[1]['size']==len(good) and jp.read_bytes()==good
 n=hfeed(hnew(jp),s);assert n._plan_owner=={'a1:p':'i'} and n.quarantined_plans()==['a1:q'] and hop(n)==['j'];row.update(calls=calls,restart=v(n),events=events(s))
def startup(row):
 rows=[]
 for at in [1,2]:
  jp=T/('startup-'+str(at)+'.jsonl');real=os.fsync;calls=[]
  def sync(fd):
   calls.append(fpath(fd))
   if len(calls)==at:raise OSError('startup fsync')
   return real(fd)
  with patch.object(os,'fsync',sync):
   try:hnew(jp)
   except OSError as ex:error=str(ex)
   else:raise AssertionError('fault not reached')
  rows.append(dict(at=at,calls=calls,error=error))
 row['cases']=rows

def abort_content(row):
 jp,s,h=fenced('abort-content');assert h.clear_journal_fence('reviewer','cancel this uncertain rebind');held(h)
 before=hfeed(hnew(jp),s);held(before);lines=[json.loads(t) for t in jp.read_text().splitlines()];assert len(lines)==2 and lines[1]['op']=='abort_rebind';original=lines[1]['op_id']
 lines[1]['op_id']=('0' if original[0]!='0' else '1')+original[1:]
 assert lines[1]['entry_hash']!=HiveReducer._entry_hash(lines[1]);jp.write_text(''.join(json.dumps(e)+'\n' for e in lines))
 restarts=[]
 for _ in range(2):
  n=hfeed(hnew(jp),s);assert n._plan_owner=={'a1:p':'i'} and hop(n)==[] and not n.journal_unapplied();restarts.append(v(n))
 row.update(verdict='OPEN Medium F-abort-content',defect_reproduced=True,original_abort_op=original,edited_abort=lines[1],before_corruption=v(before),restarts=restarts,scope='One hex character in abort op_id changed; no hashes recomputed. Parser detects mismatch but honors edited abort id and replays original cancelled rebind. Corruption detection assurance, not malicious-store threat.')

def matching_fence_and_clear(row):
 # A complete committed matching record plus marker cannot itself authorize replay.
 jp,s,h=q['fresh']('complete-matching');assert hb(h);e=json.loads(jp.read_text());fp=Path(str(jp)+'.fence');fp.write_text(json.dumps(dict(v=1,op_id=e['op_id'],entry=e)))
 n=hfeed(hnew(jp),s);held(n);assert n.journal_status()['indeterminate'];assert n.clear_journal_fence('reviewer','complete does not imply committed')
 for _ in range(2):held(hfeed(hnew(jp),s))
 row.update(complete_matching_entry=e,cancelled_durable=True,two_restarts_held=True)

for name,fn in [('rollback_preserves_prior_record',prior_record),('startup_fsync_boundaries',startup),('abort_content_corruption',abort_content),('complete_matching_fence_clear',matching_fence_and_clear)]:
 r={}
 try:fn(r);r['passed']=True
 except Exception as ex:r.update(passed=False,error=repr(ex),traceback=traceback.format_exc())
 out[name]=r;print(name,r['passed'],r.get('error',''),flush=True);save()
sys.exit(not all(r['passed'] for r in out.values()))
