"""Focused followups on evidence classification, durable rollback and diagnostics."""
import copy, hashlib, json, os, sys
from pathlib import Path
from unittest.mock import patch
E=Path(__file__).resolve().parent
src=(E/'review7656.py').read_text();scope={'__file__':str(E/'review7656.py'),'__name__':'followup_defs'}
exec(compile(src[:src.index('\nout={}\n')],str(E/'review7656.py'),'exec'),scope)
I,P,R,hnew,hfeed,hop,hb,v,HiveReducer=[scope[k] for k in ['I','P','R','hnew','hfeed','hop','hb','v','HiveReducer']]
T=E/'journal-followup';T.mkdir(exist_ok=True)
rows={}
# Exact 7638 all-fsync-fail injection. Rollback truncates, rollback fsync fails.
s=[I('i','p'),P(),R(i='i'),P(i='i')];jp=T/'exact-7638-fsync.jsonl';h=hfeed(hnew(jp),s)
with patch('hive.reducer.os.fsync',side_effect=OSError('injected fsync failure')):assert not hb(h)
assert h.journal_status()['indeterminate'] and not h._plan_owner and jp.read_bytes()==b''
n=hfeed(hnew(jp),s);assert hop(n)==['i'] and n.journal_status()['indeterminate'] is None
rows['exact_7638_all_fsync_fail']=dict(live=v(h),restart=v(n),qualification='Process restart sees truncation, but failed rollback fsync does not establish power-loss durability; memory fence is lost.')
# A failed second append preserves and fsyncs a prior committed record.
s2=s+[I('j','q'),P('q'),R('qrc','q','j'),P('q','j')];jp=T/'prior-record-rollback.jsonl';h=hfeed(hnew(jp),s2);assert hb(h);good=jp.read_bytes();real=os.fsync;calls=[]
def sync(fd):
 calls.append(dict(size=jp.stat().st_size,owner=dict(h._plan_owner)))
 if len(calls)==1:raise OSError('first append fsync failure')
 return real(fd)
with patch('hive.reducer.os.fsync',sync):assert not h.rebind_plan_owner('a1','q','j',actor='op',reason='second-op')
assert len(calls)==2 and calls[1]['size']==len(good) and jp.read_bytes()==good
n=hfeed(hnew(jp),s2);assert n._plan_owner=={'a1:p':'i'} and n.quarantined_plans()==['a1:q'] and hop(n)==['j']
rows['rollback_preserves_prior_record']=dict(events=scope['events'](s2),calls=calls,restart=v(n))
# New-file and directory durability boundaries at startup fail explicitly.
startup=[]
for at in [1,2]:
 jp=T/('create-fsync-'+str(at)+'.jsonl');real=os.fsync;calls=[]
 def sync(fd):
  calls.append(fd)
  if len(calls)==at:raise OSError('create-fsync-'+str(at))
  return real(fd)
 with patch('hive.reducer.os.fsync',sync):
  try:hnew(jp)
  except OSError as ex:raised=str(ex)
  else:raise AssertionError('constructor unexpectedly accepted fsync fault')
 startup.append(dict(boundary='new-file' if at==1 else 'parent-directory',fsync_count=len(calls),exception=raised,bytes=jp.stat().st_size))
rows['startup_fsync_boundaries']=startup
# Status caps drop oldest unapplied diagnostics (disk remains authoritative).
jp=T/'201-mismatches.jsonl';records=[]
for k in range(201):records.append(dict(v=2,op='owner_rebind',op_id='op-'+str(k),agent_id='a1',plan_id='p',incident_id='i',actor='op',reason='unmatched',seq=0,stream_digest='different'))
jp.write_text(''.join(json.dumps(r)+'\n' for r in records));h=hnew(jp);st=h.journal_status();assert len(st['unapplied'])==200 and st['unapplied'][0]['op_id']=='op-1' and st['pending']==0
rows['unapplied_status_retention']=dict(input_entries=201,status_entries=200,first_visible=st['unapplied'][0]['op_id'],last_visible=st['unapplied'][-1]['op_id'],pending=0,cumulative_unapplied_counter=hasattr(h,'journal_unapplied_total'),qualification='Errors logged and raw journal retained, but journal_status has no truncation/total indicator. This is bounded diagnostic history, not dropped active hold.')
# Severity refinement: Event says immutable; payload mutation is robustness/contract,
# not a demonstrated ordinary identical-stream replay failure.
rows['content_hash_classification']=dict(verdict='OPEN Medium F-journal-content',supersedes='Initial review7656.json High classification',reason='Changed-payload witness violates schemas.types.Event immutable-event convention. Digest detects identity/order mismatch, not content corruption. No claimed failure on identical complete serialized events; exact three original orders pass. Medium integrity/assurance gap, not High ordinary replay failure.')
(E/'followup7656.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows,indent=2))
