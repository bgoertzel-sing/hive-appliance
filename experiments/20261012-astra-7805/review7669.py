"""Sole independent 7669 review. A reproduced defect is an assertion, not a safety pass."""
import copy,hashlib,json,os,sys,traceback,stat
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
E=Path(__file__).resolve().parent
src=(E/'review7656.py').read_text();q={'__file__':str(E/'review7656.py'),'__name__':'retained7656'}
exec(compile(src[:src.index('\nout={}\n')],str(E/'review7656.py'),'exec'),q)
I,P,R,hnew,hfeed,hop,hb,v,events,HiveReducer,HiveEvent,Event=[q[k] for k in ['I','P','R','hnew','hfeed','hop','hb','v','events','HiveReducer','HiveEvent','Event']]
import hive.reducer as hr
T=E/'journal-7669';T.mkdir(exist_ok=True)
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
 entry=json.loads(jp.read_text());entry['incident_id']='j';jp.write_text(json.dumps(entry)+'\n');m=hfeed(hnew(jp),s)
 assert not m._plan_owner and 'hash mismatch' in m.journal_unapplied()[0]['why']
 row.update(verdict='CLOSED Medium exact7656 witness',original_events=events(s),changed_events=events(changed),changed_replay=v(n),edited_entry_replay=v(m))

def canonical(row):
 jp,s,h=fresh('canonical');s[0].payload['extra']={'z':'caf\u00e9 \u2603','a':[1,{'b':True,'a':None}]};h=hfeed(hnew(jp),s);assert hb(h)
 original=jp.read_bytes();entry=json.loads(original)
 # Reverse all object keys; equivalent Unicode escape/literal and JSON whitespace.
 def reverse(x):
  if isinstance(x,dict):return {k:reverse(x[k]) for k in reversed(list(x))}
  if isinstance(x,list):return [reverse(v) for v in x]
  return x
 changed=[Event.from_dict(json.loads(json.dumps(reverse(e.to_dict()),ensure_ascii=False,indent=3))) for e in s]
 jp.write_text(json.dumps(reverse(entry),ensure_ascii=False,separators=(', ', ' : '))+'\n')
 n=hfeed(hnew(jp),changed);assert n._stream_digest==h._stream_digest and n._plan_owner=={'a1:p':'i'} and not n.journal_unapplied()
 assert hr.HiveReducer._entry_hash(entry)==hr.HiveReducer._entry_hash(reverse(entry))
 # Every serialized content field changes digest, not just receipts.
 fields={}
 for key,value in [('ts',1.25),('source','other'),('subject','else'),('schema_version','2'),('severity','critical')]:
  ds=events(s);ds[0][key]=value;ns=[Event.from_dict(d) for d in ds];m=hfeed(hnew(jp),ns);assert not m._plan_owner and m.journal_unapplied();fields[key]=m._stream_digest
 row.update(equivalent_encoding_replay=v(n),edited_field_digests=fields,unicode_scope='JSON escaped versus literal same Unicode code points; NFC/NFD are different event content, not promised semantic normalization',json_domain='JSON string-key payload objects; repr fallback for non-JSON mixed key objects not cross-language canonicalization')

def faults(row):
 modes=['before_fence_open','fence_write_zero','fence_fsync','fence_replace','fence_directory_fsync','after_fence_before_append','write_before','short_write','write_after_complete','append_fsync_before','append_fsync_after','truncate_before','truncate_after','rollback_fsync','close_after_commit','remove_unlink','remove_directory_fsync','rollback_remove_unlink','rollback_remove_directory_fsync','all_fsync_fail']
 rows=[]
 for mode in modes:
  jp,s,h=fresh('fault-'+mode);fp=str(jp)+'.fence';real={n:getattr(os,n) for n in ['open','write','fsync','replace','ftruncate','close','unlink']};trace=[];jsync=0;dsync=0
  def opened(path,*a,**kw):
   ps=str(path);trace.append(['open',ps])
   if (mode=='before_fence_open' and ps==fp+'.tmp') or (mode=='after_fence_before_append' and ps==str(jp)):raise OSError(mode)
   return real['open'](path,*a,**kw)
  def write(fd,data):
   p=fpath(fd);trace.append(['write',p,len(data)])
   if p==fp+'.tmp' and mode=='fence_write_zero':return 0
   if p==str(jp):
    if mode=='write_before':raise OSError(mode)
    if mode=='short_write':return real['write'](fd,data[:len(data)//2])
    n=real['write'](fd,data)
    if mode=='write_after_complete':raise OSError(mode)
    return n
   return real['write'](fd,data)
  def sync(fd):
   nonlocal jsync,dsync
   p=fpath(fd);trace.append(['fsync',p,dict(h._plan_owner),len(h.owner_rebinds)])
   if mode=='all_fsync_fail':raise OSError(mode)
   if p==fp+'.tmp' and mode=='fence_fsync':raise OSError(mode)
   if p==str(T):
    dsync+=1
    if (dsync==1 and mode=='fence_directory_fsync') or (dsync==2 and mode in ['remove_directory_fsync','rollback_remove_directory_fsync']):raise OSError(mode)
   if p==str(jp):
    jsync+=1
    if jsync==1 and mode in ['append_fsync_before','truncate_before','truncate_after','rollback_fsync','rollback_remove_unlink','rollback_remove_directory_fsync']:raise OSError(mode)
    if jsync==1 and mode=='append_fsync_after':real['fsync'](fd);raise OSError(mode)
    if jsync==2 and mode=='rollback_fsync':raise OSError(mode)
   return real['fsync'](fd)
  def replace(a,b):
   trace.append(['replace',str(a),str(b)])
   if mode=='fence_replace':raise OSError(mode)
   return real['replace'](a,b)
  def truncate(fd,size):
   trace.append(['truncate',fpath(fd),size])
   if mode=='truncate_before':raise OSError(mode)
   n=real['ftruncate'](fd,size)
   if mode=='truncate_after':raise OSError(mode)
   return n
  def close(fd):
   p=fpath(fd);trace.append(['close',p]);n=real['close'](fd)
   if p==str(jp) and mode=='close_after_commit':raise OSError(mode)
   return n
  def unlink(path,*a,**kw):
   trace.append(['unlink',str(path)])
   if str(path)==fp and mode in ['remove_unlink','rollback_remove_unlink']:raise OSError(mode)
   return real['unlink'](path,*a,**kw)
  with ExitStack() as stack:
   for name,fn in [('open',opened),('write',write),('fsync',sync),('replace',replace),('ftruncate',truncate),('close',close),('unlink',unlink)]:stack.enter_context(patch.object(os,name,fn))
   ok=hb(h)
  assert ok==(mode=='close_after_commit')
  if not ok:held(h)
  n=hfeed(hnew(jp),s)
  if mode in ['close_after_commit','remove_directory_fsync']:
   assert n._plan_owner=={'a1:p':'i'} and hop(n)==[]
  else:held(n)
  if mode=='truncate_before':assert n.journal_status()['indeterminate'] and jp.stat().st_size>0
  if mode=='remove_directory_fsync':assert h.journal_status()['indeterminate']['persisted'] is False and n.journal_status()['indeterminate'] is None
  rows.append(dict(mode=mode,returned=ok,trace=trace,fence_exists=Path(fp).exists(),journal_bytes=jp.stat().st_size,live=v(h),restart=v(n),defect_reproduced=mode=='remove_directory_fsync'))
 row.update(cases=rows,exact7656_failed_fsync_and_truncate='CLOSED; durable marker survives restart',close_after_durable_write='CLOSED; returns True consistently',verdict='OPEN Medium F-fence-remove-dir-fsync: False live, absent marker, fresh replay closes i')

def crashes(row):
 rows=[]
 for mode in ['before_fence','fence_written_before_rename','after_fence_before_append','after_append_before_remove','during_rollback','after_fence_unlink_before_dirsync']:
  jp,s,h=fresh('crash-'+mode);fp=str(jp)+'.fence';real_open=os.open;real_replace=os.replace;real_unlink=os.unlink;real_sync=os.fsync;real_trunc=os.ftruncate;jsync=0;dsync=0
  def opened(p,*a,**kw):
   if (mode=='before_fence' and str(p)==fp+'.tmp') or (mode=='after_fence_before_append' and str(p)==str(jp)):raise Crash(mode)
   return real_open(p,*a,**kw)
  def replace(a,b):
   if mode=='fence_written_before_rename':raise Crash(mode)
   return real_replace(a,b)
  def unlink(p,*a,**kw):
   if mode=='after_append_before_remove' and str(p)==fp:raise Crash(mode)
   return real_unlink(p,*a,**kw)
  def sync(fd):
   nonlocal jsync,dsync
   p=fpath(fd)
   if p==str(jp):
    jsync+=1
    if mode=='during_rollback' and jsync==1:raise OSError('force rollback')
   if p==str(T):
    dsync+=1
    if mode=='after_fence_unlink_before_dirsync' and dsync==2:raise Crash(mode)
   return real_sync(fd)
  def truncate(fd,n):
   if mode=='during_rollback':raise Crash(mode)
   return real_trunc(fd,n)
  with patch.object(os,'open',opened),patch.object(os,'replace',replace),patch.object(os,'unlink',unlink),patch.object(os,'fsync',sync),patch.object(os,'ftruncate',truncate):
   try:hb(h)
   except Crash:pass
   else:raise AssertionError('crash not reached')
  n=hfeed(hnew(jp),s)
  if mode=='after_fence_unlink_before_dirsync':assert n._plan_owner=={'a1:p':'i'}
  else:held(n)
  if mode in ['after_fence_before_append','after_append_before_remove','during_rollback']:assert n.journal_status()['indeterminate']
  rows.append(dict(mode=mode,restart=v(n),fence_exists=Path(fp).exists(),journal_bytes=jp.stat().st_size))
 row.update(cases=rows,scope='BaseException abrupt control-flow termination then fresh reducer, no physical power-loss claim. Post-unlink crash is commit ambiguity; explicit fsync error/refusal is separate reproduced defect.')

def fenced(name):
 jp,s,h=fresh(name);real_sync=os.fsync
 def sync(fd):
  if fpath(fd)==str(jp):raise OSError('append fsync')
  return real_sync(fd)
 with patch.object(os,'fsync',sync),patch.object(os,'ftruncate',side_effect=OSError('rollback')):assert not hb(h)
 n=hfeed(hnew(jp),s);held(n);assert n.journal_status()['indeterminate'];return jp,s,n

def clear(row):
 jp,s,h=fenced('clear-success');fp=Path(str(jp)+'.fence');trace=[];real_sync=os.fsync;real_unlink=os.unlink
 for actor,reason in [('', 'r'),(' ', 'r'),('a',''),('a',None)]:
  try:h.clear_journal_fence(actor,reason)
  except ValueError:pass
  else:raise AssertionError('invalid audit accepted')
 def sync(fd):trace.append(['fsync',fpath(fd),fp.exists(),jp.read_text()]);return real_sync(fd)
 def unlink(p):trace.append(['unlink',str(p)]);return real_unlink(p)
 with patch.object(os,'fsync',sync),patch.object(os,'unlink',unlink):assert h.clear_journal_fence('reviewer','inspected uncertain entry')
 held(h);abort=json.loads(jp.read_text().splitlines()[-1]);assert abort['op']=='abort_rebind' and abort['actor']=='reviewer' and abort['entry_hash']==h._entry_hash(abort)
 assert trace[0][0]=='fsync' and trace[0][1]==str(jp) and trace[0][2] and 'abort_rebind' in trace[0][3]
 assert trace[1]==['unlink',str(fp)] and trace[2][0:2]==['fsync',str(T)]
 restarts=[]
 for _ in range(2):
  n=hfeed(hnew(jp),s);held(n);assert n.journal_status()['indeterminate'] is None and 'aborted' in n.journal_unapplied()[0]['why'];restarts.append(v(n))
 assert hb(n);last=hfeed(hnew(jp),s);assert last._plan_owner=={'a1:p':'i'} and len(last.owner_rebinds)==1
 row.update(clear_trace=trace,abort_record=abort,live_clearance=h.journal_status()['fence_clearances'],restarts=restarts,reissue_restart=v(last),audit_note='Durable actor/reason present in abort JSONL; status fence_clearances is live-only and not reconstructed at startup')

def clear_faults(row):
 rows=[]
 for mode in ['write_zero','append_fsync','append_and_rollback_fail','unlink','directory_fsync','crash_before_abort','crash_after_abort_before_unlink','crash_after_unlink']:
  jp,s,h=fenced('clear-'+mode);fp=str(jp)+'.fence';real_write=os.write;real_sync=os.fsync;real_unlink=os.unlink;real_trunc=os.ftruncate;jsync=0
  def write(fd,data):
   if fpath(fd)==str(jp):
    if mode=='write_zero':return 0
    if mode=='crash_before_abort':raise Crash(mode)
   return real_write(fd,data)
  def sync(fd):
   nonlocal jsync
   p=fpath(fd)
   if p==str(jp):
    jsync+=1
    if jsync==1 and mode in ['append_fsync','append_and_rollback_fail']:raise OSError(mode)
   if p==str(T):
    if mode=='directory_fsync':raise OSError(mode)
    if mode=='crash_after_unlink':raise Crash(mode)
   return real_sync(fd)
  def unlink(p):
   if str(p)==fp:
    if mode=='unlink':raise OSError(mode)
    if mode=='crash_after_abort_before_unlink':raise Crash(mode)
   return real_unlink(p)
  def truncate(fd,n):
   if mode=='append_and_rollback_fail':raise OSError(mode)
   return real_trunc(fd,n)
  with patch.object(os,'write',write),patch.object(os,'fsync',sync),patch.object(os,'unlink',unlink),patch.object(os,'ftruncate',truncate):
   try:h.clear_journal_fence('reviewer','fault at '+mode)
   except (OSError,Crash) as ex:error=type(ex).__name__+': '+str(ex)
   else:raise AssertionError('fault not reached')
  restarts=[]
  for _ in range(2):
   n=hfeed(hnew(jp),s);held(n);restarts.append(v(n))
  rows.append(dict(mode=mode,error=error,fence_exists=Path(fp).exists(),restarts=restarts))
 row['cases']=rows

def corrupt_fence(row):
 rows=[]
 for mode in ['invalid_utf8','invalid_json','json_array','empty_object','unreadable_open','edited_op_id','missing_entry']:
  jp,s,h=fenced('marker-'+mode);fp=Path(str(jp)+'.fence');marker=json.loads(fp.read_text());expected=marker['op_id']
  if mode=='invalid_utf8':fp.write_bytes(b'\xff')
  if mode=='invalid_json':fp.write_bytes(b'{oops')
  if mode=='json_array':fp.write_text('[]')
  if mode=='empty_object':fp.write_text('{}')
  if mode=='edited_op_id':marker['op_id']='changed-id';fp.write_text(json.dumps(marker))
  if mode=='missing_entry':fp.write_text(json.dumps({'op_id':'changed-id'}))
  import builtins
  real_open=builtins.open
  def opened(p,*a,**kw):
   if str(p)==str(fp):raise PermissionError('injected unreadable marker')
   return real_open(p,*a,**kw)
  with ExitStack() as stack:
   if mode=='unreadable_open':stack.enter_context(patch.object(builtins,'open',opened))
   n=hfeed(hnew(jp),s)
  if mode in ['edited_op_id','missing_entry']:assert n._plan_owner=={'a1:p':'i'} and hop(n)==[]
  else:held(n)
  assert n.journal_status()['indeterminate']
  assert not hb(n)
  before=v(n)
  if mode not in ['edited_op_id','missing_entry']:
   assert n.clear_journal_fence('reviewer','unreadable marker inspected')
   for _ in range(2):held(hfeed(hnew(jp),s))
  rows.append(dict(mode=mode,original_op_id=expected,restart=before,defect_reproduced=mode in ['edited_op_id','missing_entry']))
 row.update(cases=rows,verdict='OPEN Medium F-fence-content: parseable corrupt marker op_id is trusted without matching embedded entry; uncertain entry replays even while indeterminate status present')

def tail_faults(row):
 rows=[]
 for phase in ['startup','runtime']:
  for mode in ['positive_short','write_zero','write_error_after_short','aside_fsync','readback_mismatch','short_journal_read','aside_dirsync','truncate','journal_fsync']:
   jp=T/('tail-'+phase+'-'+mode+'.jsonl');s=history();h=hfeed(hnew(jp),s) if phase=='runtime' else None;fragment=b'{"torn-evidence":12345';jp.write_bytes(fragment)
   real_write=os.write;real_sync=os.fsync;real_pread=os.pread;real_trunc=os.ftruncate;wc=0;verified=False;traces=[]
   def write(fd,data):
    nonlocal wc
    p=fpath(fd)
    if '.torn-' in p:
     wc+=1;traces.append(['aside_write',len(data)])
     if mode=='write_zero':return 0
     if mode=='write_error_after_short' and wc>1:raise OSError(mode)
     if mode in ['positive_short','write_error_after_short']:return real_write(fd,data[:3])
    return real_write(fd,data)
   def sync(fd):
    p=fpath(fd);traces.append(['fsync',p])
    if '.torn-' in p and mode=='aside_fsync':raise OSError(mode)
    if p==str(jp) and mode=='journal_fsync':raise OSError(mode)
    if p==str(T) and mode=='aside_dirsync' and list(T.glob(jp.name+'.torn-*')):raise OSError(mode)
    return real_sync(fd)
   def pread(fd,n,off):
    nonlocal verified
    p=fpath(fd);data=real_pread(fd,n,off)
    if p==str(jp) and n==len(fragment) and mode=='short_journal_read':return data[:-1]
    if '.torn-' in p:
     traces.append(['aside_readback',len(data)]);verified=True
     if mode=='readback_mismatch':return b'x'*len(data)
    return data
   def truncate(fd,size):
    traces.append(['truncate',size,verified])
    assert verified
    if mode=='truncate':raise OSError(mode)
    return real_trunc(fd,size)
   result=None;error=None
   with patch.object(os,'write',write),patch.object(os,'fsync',sync),patch.object(os,'pread',pread),patch.object(os,'ftruncate',truncate):
    try:
     if phase=='startup':h=hnew(jp)
     else:result=hb(h)
    except OSError as ex:error=str(ex)
   aside=[dict(name=p.name,hex=p.read_bytes().hex()) for p in T.glob(jp.name+'.torn-*')]
   if mode=='positive_short':
    assert error is None and (phase=='startup' or result is True) and len(aside)==1 and aside[0]['hex']==fragment.hex()
   else:
    assert (error is not None if phase=='startup' else result is False)
    if mode!='journal_fsync':assert jp.read_bytes()==fragment
    else:assert jp.read_bytes()==b'' and aside[0]['hex']==fragment.hex()
   rows.append(dict(phase=phase,mode=mode,result=result,error=error,journal_hex=jp.read_bytes().hex(),aside=aside,trace=traces))
 row.update(cases=rows,verdict='CLOSED Low exact short-write loss; loops safely to completion or refuses before truncation',documentation_qualification='After verified durable aside, ftruncate may succeed then journal fsync fail: original journal has already changed. Blanket docs any-step-fails => untouched is false; bytes remain in durable aside.')

def observability(row):
 rows=[]
 for version in [2,3]:
  jp=T/('201-v'+str(version)+'.jsonl');recs=[]
  for k in range(201):
   e=dict(v=version,op='owner_rebind',op_id='op-'+str(k),agent_id='a1',plan_id='p',incident_id='i',actor='op',reason='unmatched',seq=0,stream_digest='different')
   if version==3:e['entry_hash']=HiveReducer._entry_hash(e)
   recs.append(e)
  jp.write_text(''.join(json.dumps(e)+'\n' for e in recs));h=hnew(jp);st=h.journal_status();all_=h.journal_unapplied()
  assert st['pending']==0 and len(st['unapplied'])==200 and st['unapplied_total']==201 and st['unapplied_omitted']==1 and len(all_)==201
  assert all_[0]['op_id']=='op-0' and all_[-1]['op_id']=='op-200';all_.clear();assert len(h.journal_unapplied())==201
  rows.append(dict(version=version,status=st,all_dispositions=h.journal_unapplied()))
 row.update(verdict='CLOSED Low exact201 witness plus current-format mismatches',cases=rows)

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

def controls(row):
 # Observe directory fsync after marker creation AND removal on success.
 jp,s,h=fresh('normal-order');trace=[];real_sync=os.fsync;real_unlink=os.unlink;fp=str(jp)+'.fence'
 def sync(fd):trace.append(dict(op='fsync',path=fpath(fd),owner=dict(h._plan_owner),audit=len(h.owner_rebinds),fence=Path(fp).exists(),journal_size=jp.stat().st_size));return real_sync(fd)
 def unlink(p):trace.append(dict(op='unlink',path=str(p)));return real_unlink(p)
 with patch.object(os,'fsync',sync),patch.object(os,'unlink',unlink):assert hb(h)
 assert [(t['op'],t['path']) for t in trace]==[('fsync',fp+'.tmp'),('fsync',str(T)),('fsync',str(jp)),('unlink',fp),('fsync',str(T))]
 assert all(not t['owner'] and t['audit']==0 for t in trace if t['op']=='fsync')
 b=jp.read_bytes();n=hfeed(hnew(jp),s);hfeed(n,s);n._replay_journal();assert len(n.owner_rebinds)==1 and jp.read_bytes()==b
 dp=T/'duplicate.jsonl';dp.write_bytes(b+b);d=hfeed(hnew(dp),s);assert len(d.owner_rebinds)==1 and not d.journal_pending()
 # Real 647fac6-format source record copied from prior evidence, with exact original event stream.
 prior=json.loads((Path(os.environ['HIVE_SRC'])/'experiments/20261008-astra-7656/review7656.json').read_text())
 old=prior['F_journal_order_exact']['cases'][0];old_events=[Event.from_dict(e) for e in old['events']]
 old_path=Path(os.environ['HIVE_SRC'])/'experiments/20261008-astra-7656/journal-cases/target_success_then_failure.jsonl'
 lp=T/'authentic-647fac6-v2.jsonl';lp.write_bytes(old_path.read_bytes());legacy=hfeed(hnew(lp),old_events)
 assert not legacy._plan_owner and legacy.journal_unapplied() and 'legacy entry (format v2)' in legacy.journal_unapplied()[0]['why']
 assert hb(legacy);n=hfeed(hnew(lp),old_events);assert n._plan_owner=={'a1:p':'i'} and len(n.journal_unapplied())==1 and hop(n)==['i','j']
 row.update(normal_trace=trace,authentic_v2_source=str(old_path),source_sha256=hashlib.sha256(old_path.read_bytes()).hexdigest(),migrated=v(n))

out={}
functions=[('F_journal_content',content),('canonical_hashing',canonical),('fence_fault_matrix',faults),('fence_crash_boundaries',crashes),('durable_clear',clear),('clear_fault_boundaries',clear_faults),('corrupt_fence',corrupt_fence),('tail_boundaries',tail_faults),('F_unapplied_observability',observability),('aggregate_real_10000',aggregate),('journal_controls_migration',controls)]
for name in ['unregister','journal_order','tail','default_and_legacy','rejected_and_partial','caps','recovery_text']:functions.append(('retained_'+name,q[name]))
g=q['g']
for name,fn in [('foreign',g['foreign']),('incidentless',g['incidentless']),('hold',g['hold']),('quiet_guidance',g['quiet_and_guidance']),('plan_only_witness',g['a']['witness']),('hold_144_schedules',g['a']['schedules']),('refusals_pending',g['a']['refusals_and_pending']),('late_link_warnings',g['a']['warnings']),('regressions',g['retained'])]:functions.append(('retained_'+name,fn))
for name,fn in functions:
 r={}
 try:fn(r);r['passed']=True
 except Exception as ex:r.update(passed=False,error=repr(ex),traceback=traceback.format_exc())
 out[name]=r;print(name,r['passed'],r.get('error',''),flush=True);save('review7669.json',out)
save('review7669-summary.json',dict(groups=len(out),passed=sum(r['passed'] for r in out.values()),failed=[k for k,v in out.items() if not v['passed']],note='Includes explicitly asserted defect reproductions, not safety approvals'))
sys.exit(not all(r['passed'] for r in out.values()))
