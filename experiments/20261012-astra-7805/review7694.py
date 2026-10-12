"""Sole independent 7694 review (7669 exact witnesses retained). A reproduced defect is an assertion, not a safety pass."""
import copy,hashlib,json,os,sys,traceback,stat
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
E=Path(__file__).resolve().parent
src=(E/'review7656.py').read_text();q={'__file__':str(E/'review7656.py'),'__name__':'retained7656'}
exec(compile(src[:src.index('\nout={}\n')],str(E/'review7656.py'),'exec'),q)
I,P,R,hnew,hfeed,hop,hb,v,events,HiveReducer,HiveEvent,Event=[q[k] for k in ['I','P','R','hnew','hfeed','hop','hb','v','events','HiveReducer','HiveEvent','Event']]
import hive.reducer as hr
T=E/'journal-7694';T.mkdir(exist_ok=True)
def save(n,o):(E/n).write_text(json.dumps(o,indent=2,default=str)+'\n')
def history():return [I('i','p'),P(),R(i='i'),P(i='i')]
def fresh(name,s=None):
 s=s or history();jp=T/(name+'.jsonl');return jp,s,hfeed(hnew(jp),s)
def fpath(fd):return os.readlink('/proc/self/fd/'+str(fd))
def held(h):assert not h._plan_owner and hop(h)==['i'] and h.quarantined_plans()==['a1:p']
class Crash(BaseException):pass

def content(row):
 s=[I('i','p'),I('j','p'),P(),R('yes',i='i'),R('no',i='i',ok=False),P(i='i')]
 jp,s,h=fresh('exact-content',s);assert hb(h) and hop(h)==['i','j']
 changed=copy.deepcopy(s);changed[4].payload['verified']=True;n=hfeed(hnew(jp),changed)
 assert h._stream_digest!=n._stream_digest and hop(n)==['i','j'] and not n._plan_owner and n.journal_status()['unapplied_total']==1
 lines=[json.loads(x) for x in jp.read_text().splitlines()];entry=lines[1];entry['incident_id']='j';jp.write_text(''.join(json.dumps(x)+'\n' for x in lines));m=hfeed(hnew(jp),s)
 assert not m._plan_owner and 'hash mismatch' in m.journal_status()['corrupt_records'][0]['why']
 row.update(verdict='CLOSED Medium exact7656 witness',original_events=events(s),changed_events=events(changed),changed_replay=v(n),edited_entry_replay=v(m))

def canonical(row):
 jp,s,h=fresh('canonical');s[0].payload['extra']={'z':'caf\u00e9 \u2603','a':[1,{'b':True,'a':None}]};h=hfeed(hnew(jp),s);assert hb(h)
 original=jp.read_bytes();entries=[json.loads(x) for x in original.splitlines()];entry=entries[0]
 # Reverse all object keys; equivalent Unicode escape/literal and JSON whitespace.
 def reverse(x):
  if isinstance(x,dict):return {k:reverse(x[k]) for k in reversed(list(x))}
  if isinstance(x,list):return [reverse(v) for v in x]
  return x
 changed=[Event.from_dict(json.loads(json.dumps(reverse(e.to_dict()),ensure_ascii=False,indent=3))) for e in s]
 jp.write_text(''.join(json.dumps(reverse(e),ensure_ascii=False,separators=(', ', ' : '))+'\n' for e in entries))
 n=hfeed(hnew(jp),changed);assert n._stream_digest==h._stream_digest and n._plan_owner=={'a1:p':'i'} and not n.journal_unapplied()
 assert hr.HiveReducer._rec_hash(entry)==hr.HiveReducer._rec_hash(reverse(entry))
 # Every serialized content field changes digest, not just receipts.
 fields={}
 for key,value in [('ts',1.25),('source','other'),('subject','else'),('schema_version','2'),('severity','critical')]:
  ds=events(s);ds[0][key]=value;ns=[Event.from_dict(d) for d in ds];m=hfeed(hnew(jp),ns);assert not m._plan_owner and m.journal_unapplied();fields[key]=m._stream_digest
 row.update(equivalent_encoding_replay=v(n),edited_field_digests=fields,unicode_scope='JSON escaped versus literal same Unicode code points; NFC/NFD are different event content, not promised semantic normalization',json_domain='JSON string-key payload objects; repr fallback for non-JSON mixed key objects not cross-language canonicalization')

def aggregate(row):
 assert hr.MAX_HIVE_PLANS==10000;h=hnew();counts=[]
 # Full real event stream, one open incident/held plan then 9999 additional plans.
 # No constant/state monkeypatch; all tracked plans below limit are retained.
 hfeed(h,[I('i','p'),P(),P(i='i')]);old=copy.deepcopy(h.quarantine_reasons());hfeed(h,[I('refused')])
 for k in range(1,10001):
  hfeed(h,[P('p'+str(k),'refused' if k==10000 else '')])
  attempted=k+1
  if attempted>=9999:counts.append(dict(attempted=attempted,tracked=len(h._plan_steps),held=h.quarantine_reasons(),refused=h.plans_refused_cap))
 assert [x['tracked'] for x in counts]==[9999,10000,10000] and h.plans_refused_cap==1 and h.quarantine_reasons()==old and len(h._plan_steps)==10000 and 'a1:p10000' not in h._plan_steps
 assert 'refused' in hop(h);hfeed(h,[R('for-refused','p10000','refused')]);assert 'refused' in hop(h)
 # Existing tracked plan/candidate still works at cap, nothing dropped.
 assert hb(h) and 'i' in hop(h);hfeed(h,[R('fresh','p','i')]);assert hop(h)==['refused'] and len(h._plan_steps)==10000
 row.update(verdict='CLOSED Low tracked-plan admission',boundary=counts,retained_plan_keys_sha256=hashlib.sha256(json.dumps(sorted(h._plan_steps)).encode()).hexdigest(),after_existing_rebind=dict(tracked=len(h._plan_steps),open=hop(h)),scope='Caps tracked plans, not arbitrary incident/receipt counts or legacy oversized journal loading; no claim of universal memory bound')

out={}
functions=[('F_journal_content',content),('canonical_hashing',canonical),('aggregate_real_10000',aggregate)]
for name in ['unregister','journal_order','rejected_and_partial','recovery_text']:functions.append(('retained_'+name,q[name]))
g=q['g']
for name,fn in [('foreign',g['foreign']),('incidentless',g['incidentless']),('hold',g['hold']),('quiet_guidance',g['quiet_and_guidance']),('plan_only_witness',g['a']['witness']),('hold_144_schedules',g['a']['schedules']),('refusals_pending',g['a']['refusals_and_pending']),('late_link_warnings',g['a']['warnings']),('regressions',g['retained'])]:functions.append(('retained_'+name,fn))
for name,fn in functions:
 r={}
 try:fn(r);r['passed']=True
 except Exception as ex:r.update(passed=False,error=repr(ex),traceback=traceback.format_exc())
 out[name]=r;print(name,r['passed'],r.get('error',''),flush=True);save('review7694.json',out)
save('review7694-summary.json',dict(groups=len(out),passed=sum(r['passed'] for r in out.values()),failed=[k for k,v in out.items() if not v['passed']]))
sys.exit(not all(r['passed'] for r in out.values()))
