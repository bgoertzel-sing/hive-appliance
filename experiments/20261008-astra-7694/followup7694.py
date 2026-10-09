"""Sole independent v4 protocol review. Assertions include defects, not safety passes.
Historical original byte fixtures + retained event/fault witnesses; no source changes.
"""
import builtins,copy,hashlib,inspect,json,os,sys,traceback,difflib
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
E=Path(__file__).resolve().parent;S=Path(os.environ['HIVE_SRC'])
raw=(E/'review7694.py').read_text();q={'__file__':str(E/'review7694.py'),'__name__':'defs'};exec(compile(raw[:raw.index('\nout={}\n')],str(E/'review7694.py'),'exec'),q)
I,P,R,hnew,hfeed,hop,hb,v,events,HiveReducer,Event,hr=[q[k] for k in ['I','P','R','hnew','hfeed','hop','hb','v','events','HiveReducer','Event','hr']]
T=E/'journal-followup7694';T.mkdir(exist_ok=True)
def save(n,o):(E/n).write_text(json.dumps(o,indent=2,default=str)+'\n')
def history():return [I('i','p'),P(),R(i='i'),P(i='i')]
def fresh(name,s=None):
 s=s or history();p=T/(name+'.jsonl');return p,s,hfeed(hnew(p),s)
def fpath(fd):return os.readlink('/proc/self/fd/'+str(fd))
def held(h):assert not h._plan_owner and hop(h)==['i'] and h.quarantined_plans()==['a1:p']
def records(p):return [json.loads(x) for x in p.read_bytes().splitlines()]
def put(p,rows):p.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
def restarts(p,s,n=2):return [hfeed(hnew(p),s) for _ in range(n)]
def two():return history()+[I('j','q'),P('q'),R('q-ok','q','j'),P('q','j')]
def bindq(h):return h.rebind_plan_owner('a1','q','j',actor='operator-original',reason='second-proof')
class Crash(BaseException):pass

def historical_exact(row):
 # EXACT archived bytes, not regenerated weaker samples: every journal artifact
 # emitted by 7678's three OPEN groups, with their exact original event streams.
 prior=S/'experiments/20261008-astra-7678';res=json.loads((prior/'followup7678.json').read_text());rows=[]
 streams={'temporal': [Event.from_dict(x) for x in res['corrupt_record_temporal_scope']['events']]}
 for name in ['lost_final_newline','truncated_abort_json','malformed_complete_abort','blank_abort_line']:
  case=next(x for x in res['torn_cancelled_record']['cases'] if x['mode']==name);p=T/('exact7678-tail-'+name+'.jsonl');p.write_bytes(bytes.fromhex(case['damaged_hex']));rs=restarts(p,history())
  for h in rs:held(h);assert not h.journal_status()['healthy']
  assert p.read_bytes()==bytes.fromhex(case['damaged_hex']);rows.append(dict(group='F-abort-tail',case=name,exact_bytes_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),restart=[v(x) for x in rs]))
 for item in res['compound_failure']['cases']:
  name='compound-'+item['mode']+'.jsonl';src=prior/'journal-followup7678'/name;p=T/('exact7678-'+name);p.write_bytes(src.read_bytes());rs=restarts(p,history())
  for h in rs:held(h);assert not h.journal_status()['healthy']
  rows.append(dict(group='F-journal-refused-compound',case=item['mode'],source=str(src),restart=[v(x) for x in rs]))
 for item in res['corrupt_record_temporal_scope']['cases']:
  name=item['case']+'.jsonl';src=prior/'journal-followup7678'/name;p=T/('exact7678-'+name);p.write_bytes(src.read_bytes());rs=restarts(p,streams['temporal'])
  for h in rs:assert not h._plan_owner and not h.journal_status()['healthy']
  rows.append(dict(group='F-abort-order-scope',case=item['case'],source=str(src),restart=[v(x) for x in rs]))
 row.update(cases=rows,interpretation='Exact v3 witness bytes now whole-journal migration-fenced; native v4 equivalents separately tested. Abort/marker writer steps no longer exist.')

def tails_and_order(row):
 rows=[]
 for mode in ['lost_final_newline','truncated_commit_json','malformed_complete_commit','blank_commit_line','commit_before_pending','second_pair_first','interleave','remove_middle','duplicate_pair','edited_pending_id','edited_commit_id','edited_target','bad_utf8','array','unknown_op']:
  p,s,h=fresh('native-'+mode,two());assert hb(h) and bindq(h);original=p.read_bytes();L=original.splitlines(keepends=True)
  if mode=='lost_final_newline':bad=original[:-1]
  elif mode=='truncated_commit_json':bad=b''.join(L[:-1])+L[-1][:20]
  elif mode=='malformed_complete_commit':bad=b''.join(L[:-1])+L[-1][:20]+b'\n'
  elif mode=='blank_commit_line':bad=b''.join(L[:-1])+b' '*len(L[-1].rstrip(b'\n'))+b'\n'
  elif mode=='commit_before_pending':bad=L[1]+L[0]+b''.join(L[2:])
  elif mode=='second_pair_first':bad=b''.join(L[2:]+L[:2])
  elif mode=='interleave':bad=b''.join([L[0],L[2],L[1],L[3]])
  elif mode=='remove_middle':bad=b''.join([L[0],L[2],L[3]])
  elif mode=='duplicate_pair':bad=original+original
  elif mode in ['edited_pending_id','edited_commit_id','edited_target']:
   rs=records(p);r=rs[1 if mode=='edited_commit_id' else 0];key='incident_id' if mode=='edited_target' else 'op_id';value=r[key];r[key]=('0' if value[0]!='0' else '1')+value[1:];put(p,rs);bad=p.read_bytes()
  else:bad=original+{'bad_utf8':b'\xff\n','array':b'[]\n','unknown_op':b'{"v":4,"op":"wrong"}\n'}[mode]
  p.write_bytes(bad);rs=restarts(p,s)
  for n in rs:assert not n._plan_owner and not n.journal_status()['healthy'] and n.journal_status()['corrupt_records'] and not hb(n)
  assert p.read_bytes()==bad
  rows.append(dict(mode=mode,original_sha256=hashlib.sha256(original).hexdigest(),damaged_sha256=hashlib.sha256(bad).hexdigest(),restarts=[v(n) for n in rs]))
 # Refused pending with no commit: loss of newline cannot create authorization.
 p,s,h=fresh('refused-pending-tail');real=os.fsync;count=0
 def sync(fd):
  nonlocal count
  if fpath(fd)==str(p):
   count+=1
   if count==2:raise OSError('commit fsync')
  return real(fd)
 with patch.object(os,'fsync',sync):assert not hb(h)
 held(h);assert len(records(p))==1;held(hfeed(hnew(p),s));p.write_bytes(p.read_bytes()[:-1])
 for n in restarts(p,s):held(n);assert not n.journal_status()['healthy']
 row.update(cases=rows,refused_pending_tail='held twice; no bytes trimmed',verdict='CLOSED F-abort-tail/F-abort-order-scope at native v4 boundaries; whole-file rollback separately tested')

def fault_matrix(row):
 rows=[]
 # Retain 7656/7669 syscall fault boundaries for BOTH v4 records.
 for phase in ['pending','commit']:
  for mode in ['open','write_before','short_zero','positive_short','write_after_complete','fsync_before','fsync_after','truncate_before','truncate_after','rollback_fsync','close_after','all_after_write_fail']:
   p,s,h=fresh('fault-'+phase+'-'+mode);before=copy.deepcopy(vars(h));real={k:getattr(os,k) for k in ['open','write','fsync','ftruncate','close']};trace=[];writes=0;syncs=0;active=False;triggered=False
   def opened(path,*a,**kw):
    nonlocal active,triggered
    if str(path)==str(p):
     active=(phase=='pending' and syncs==0) or (phase=='commit' and syncs==1)
     if active and mode=='open':triggered=True;raise PermissionError('record open')
    return real['open'](path,*a,**kw)
   def write(fd,data):
    nonlocal writes,triggered
    if fpath(fd)!=str(p):return real['write'](fd,data)
    writes+=1;trace.append(['write',len(data),active,dict(h._plan_owner)])
    if active:
     if mode=='write_before':triggered=True;raise OSError('write before')
     if mode=='short_zero':triggered=True;return 0
     if mode=='positive_short':triggered=True;return real['write'](fd,data[:max(1,len(data)//2)])
    n=real['write'](fd,data)
    if active and mode=='write_after_complete':triggered=True;raise OSError('after write')
    return n
   def sync(fd):
    nonlocal syncs,triggered
    if fpath(fd)==str(p):
     syncs+=1;trace.append(['fsync',syncs,active,dict(h._plan_owner),len(h.owner_rebinds)])
     target=1 if phase=='pending' else 2
     if active and syncs==target and mode in ['fsync_before','fsync_after','truncate_before','truncate_after','rollback_fsync','all_after_write_fail']:
      triggered=True
      if mode=='fsync_after':real['fsync'](fd)
      raise OSError('record fsync')
     if active and syncs==target+1 and mode in ['rollback_fsync','all_after_write_fail']:raise OSError('rollback fsync')
    return real['fsync'](fd)
   def trunc(fd,size):
    trace.append(['truncate',size])
    if active and mode in ['truncate_before','all_after_write_fail']:raise OSError('truncate before')
    x=real['ftruncate'](fd,size)
    if active and mode=='truncate_after':raise OSError('truncate after')
    return x
   def close(fd):
    nonlocal triggered
    path=fpath(fd);x=real['close'](fd)
    if path==str(p) and active and mode=='close_after':triggered=True;raise OSError('close after')
    return x
   with ExitStack() as stack:
    for k,fn in [('open',opened),('write',write),('fsync',sync),('ftruncate',trunc),('close',close)]:stack.enter_context(patch.object(os,k,fn))
    ok=hb(h)
   assert triggered,(phase,mode)
   uncertain=phase=='commit' and mode in ['truncate_before','truncate_after','rollback_fsync','all_after_write_fail']
   assert ok==(uncertain or mode in ['positive_short','close_after']),(phase,mode,ok)
   if not ok:
    held(h)
    changed=[k for k in before if before[k]!=vars(h)[k]]
    assert all(k.startswith('_journal') for k in changed),changed
   rs=restarts(p,s)
   for n in rs:
    if ok and mode not in ['truncate_after','rollback_fsync']:assert n._plan_owner=={'a1:p':'i'} and hop(n)==[]
    else:held(n)
   rows.append(dict(phase=phase,mode=mode,returned=ok,live=v(h),restart=[v(n) for n in rs],trace=trace,divergence=bool(h._plan_owner)!=bool(rs[0]._plan_owner)))
 row.update(cases=rows,verdict='No False-return replay in 24 v4 fault cases; commit rollback uncertainty returns True with possible lost authorization; close-after and positive short writes safe')

def commit_absent(row):
 # Stronger than simulating power loss: commit write writes NO bytes, then
 # rollback itself fails, so the True-return divergence occurs on ordinary restart.
 p,s,h=fresh('commit-never-written');real_write=os.write;real_trunc=os.ftruncate;trace=[]
 def write(fd,data):
  if fpath(fd)==str(p):
   trace.append(['write',len(data),data.decode()])
   if b'"rebind_commit"' in data:raise OSError('commit write before any byte')
  return real_write(fd,data)
 def trunc(fd,n):raise OSError('rollback unavailable')
 with patch.object(os,'write',write),patch.object(os,'ftruncate',trunc):ok=hb(h)
 assert ok and h._plan_owner=={'a1:p':'i'} and hop(h)==[] and len(records(p))==1
 assert h.journal_status()['fence']['kind']=='commit_uncertain' and h.journal_status()['fence']['applied']
 rs=restarts(p,s)
 for n in rs:held(n);assert n.journal_status()['healthy']
 row.update(returned=ok,live=v(h),trace=trace,restarts=[v(n) for n in rs],journal=p.read_text(),verdict='OPEN Medium F-applied-without-durable-commit: True means in-memory applied but cannot mean durable success; structured UNCERTAIN required for current production gate')

def crash_boundaries(row):
 rows=[]
 for mode in ['before_pending_write','after_pending_write','after_pending_fsync','before_commit_write','after_commit_write','after_commit_fsync','before_apply','after_apply']:
  p,s,h=fresh('crash-'+mode);real_write=os.write;real_sync=os.fsync;real_apply=h._do_rebind;trace=[];wc=0;sc=0
  def write(fd,data):
   nonlocal wc
   if fpath(fd)==str(p):
    wc+=1;trace.append(['before_write',wc,dict(h._plan_owner)])
    if (wc==1 and mode=='before_pending_write') or (wc==2 and mode=='before_commit_write'):raise Crash(mode)
    x=real_write(fd,data);trace.append(['after_write',wc])
    if (wc==1 and mode=='after_pending_write') or (wc==2 and mode=='after_commit_write'):raise Crash(mode)
    return x
   return real_write(fd,data)
  def sync(fd):
   nonlocal sc
   x=real_sync(fd)
   if fpath(fd)==str(p):
    sc+=1;trace.append(['after_fsync',sc,dict(h._plan_owner)])
    if (sc==1 and mode=='after_pending_fsync') or (sc==2 and mode=='after_commit_fsync'):raise Crash(mode)
   return x
  def apply(*a,**kw):
   trace.append(['before_apply',dict(h._plan_owner)])
   if mode=='before_apply':raise Crash(mode)
   real_apply(*a,**kw);trace.append(['after_apply',dict(h._plan_owner)])
   if mode=='after_apply':raise Crash(mode)
  with patch.object(os,'write',write),patch.object(os,'fsync',sync),patch.object(h,'_do_rebind',apply):
   try:hb(h)
   except Crash:pass
   else:raise AssertionError('crash not reached')
  rs=restarts(p,s)
  expected=mode in ['after_commit_write','after_commit_fsync','before_apply','after_apply']
  for n in rs:assert bool(n._plan_owner)==expected
  rows.append(dict(mode=mode,trace=trace,live=v(h),restart=[v(n) for n in rs],physical_power_loss=False))
 row.update(cases=rows,actual_order='pending write -> pending fsync -> commit write -> commit fsync -> apply; not pending->apply->commit',scope='Abrupt BaseException + normal fresh-reducer restart; after-write bytes may survive without fsync, not proof of physical durability')

def duplicates(row):
 p,s,h=fresh('duplicate-template');assert hb(h);P0,C0=records(p);rows=[]
 for mode in ['exact_duplicate_commit','second_commit_same_pending','unknown_pending','wrong_pending_hash']:
  rs=copy.deepcopy([P0,C0]);r=copy.deepcopy(C0)
  if mode!='exact_duplicate_commit':
   r['prev']=C0['rec_hash'];r['ts']=0
   if mode=='unknown_pending':r['op_id']='missing'
   if mode=='wrong_pending_hash':r['pending_hash']='wrong';rs=[P0];r['prev']=P0['rec_hash']
   r['rec_hash']=HiveReducer._rec_hash(r)
  dest=T/(mode+'.jsonl');put(dest,rs+[r]);ns=restarts(dest,s)
  for n in ns:held(n);assert not n.journal_status()['healthy']
  why=ns[0].journal_status()['corrupt_records'][0]['why']
  if mode=='second_commit_same_pending':assert 'duplicate commit' in why
  rows.append(dict(mode=mode,why=why,restarts=[v(n) for n in ns]))
 row['cases']=rows

def splice(row):
 # A previously committed operation is deliberately dropped by clearing a
 # corrupted journal from a fresh process. Restore bytes from its archive.
 p,s,h=fresh('splice-live');assert hb(h);old=p.read_bytes();p.write_bytes(old+b'{"torn":')
 n=hfeed(hnew(p),s);held(n);assert n.clear_journal_fence('reviewer','discard old authorization, leave held')
 archive=Path(n.journal_status()['fence_clearances'][-1]['archived']);assert archive.read_bytes()==old+b'{"torn":';reset=p.read_bytes();held(hfeed(hnew(p),s));rows=[]
 for mode,bad in [('append_archived_prefix',reset+old),('archived_whole_file',archive.read_bytes()),('replace_with_old_valid_journal',old),('replace_with_archived_clean_prefix',archive.read_bytes()[:-len(b'{"torn":')])]:
  dest=T/(mode+'.jsonl');dest.write_bytes(bad);rs=restarts(dest,s);revives=mode in ['replace_with_old_valid_journal','replace_with_archived_clean_prefix']
  for x in rs:
   assert bool(x._plan_owner)==revives
   if revives:assert hop(x)==[] and x.journal_status()['healthy']
   else:held(x);assert not x.journal_status()['healthy']
  rows.append(dict(mode=mode,rebind_revived=revives,restarts=[v(x) for x in rs],hashes_recomputed=False))
 # A clean archived journal can exist when a runtime write was refused with
 # an intact pending-only suffix; archive itself is valid and accepted whole.
 p2,s,h2=fresh('clean-archive',two());assert hb(h2);real_write=os.write
 def write(fd,data):
  if fpath(fd)==str(p2) and b'"rebind_pending"' in data:raise OSError('next pending')
  return real_write(fd,data)
 with patch.object(os,'write',write),patch.object(os,'ftruncate',side_effect=OSError('rollback')):assert not bindq(h2)
 assert h2.clear_journal_fence('reviewer','new journal identity');ar=Path(h2.journal_status()['fence_clearances'][-1]['archived']);dest=T/'whole-clean-archive.jsonl';dest.write_bytes(ar.read_bytes());z=hfeed(hnew(dest),s);assert z.journal_status()['healthy'] and z._plan_owner=={'a1:p':'i'}
 row.update(cases=rows,clean_archive_accepted=v(z),first_record=records(T/'splice-live.jsonl')[0],genesis='empty string, no persistent journal-unique identity or external tip anchor',verdict='OPEN Medium F-journal-rollback-anchor: old valid whole journal / clean archived prefix can undo deliberate clearance and close again without rehashing. Internal splices fail. Random id alone cannot detect whole-file rollback without separately anchored expected id/tip.')

def clean_prefixes(row):
 p,s,h=fresh('prefix-base',two());assert hb(h) and bindq(h);L=p.read_bytes().splitlines(keepends=True);rows=[]
 for k in range(5):
  dest=T/('prefix-'+str(k)+'.jsonl');dest.write_bytes(b''.join(L[:k]));ns=restarts(dest,s);expected={} if k<2 else {'a1:p':'i'}
  if k==4:expected['a1:q']='j'
  for n in ns:assert n._plan_owner==expected and n.journal_status()['healthy']
  rows.append(dict(records=k,restarts=[v(n) for n in ns]))
 row.update(cases=rows,verdict='Single current journal prefix only loses authorizations; no wrong closure for every boundary. Do not generalize to old-journal rollback across reset.')

def startup_external(row):
 rows=[]
 for mode in ['missing','read_denied','create_denied','create_file_fsync','create_dir_fsync','runtime_missing','runtime_torn','runtime_append','runtime_prefix_edit_same_size','runtime_open_denied']:
  p=T/('startup-'+mode+'.jsonl');real_open=builtins.open;real_osopen=os.open;real_sync=os.fsync;trace=[]
  if mode.startswith('runtime'):
   s=two();h=hfeed(hnew(p),s);assert hb(h);good=p.read_bytes()
   if mode=='runtime_missing':p.unlink()
   elif mode=='runtime_torn':p.write_bytes(good+b'{')
   elif mode=='runtime_append':p.write_bytes(good+b'\n')
   elif mode=='runtime_prefix_edit_same_size':p.write_bytes(good.replace(b'case-proof',b'case-prooX',1));assert p.stat().st_size==len(good)
   def opened(path,*a,**kw):
    if str(path)==str(p) and mode=='runtime_open_denied':raise PermissionError('unwritable')
    return real_osopen(path,*a,**kw)
   with patch.object(os,'open',opened):ok=bindq(h)
   if mode=='runtime_prefix_edit_same_size':assert ok and h.journal_status()['healthy']
   else:assert not ok
   if mode=='runtime_open_denied':assert h.journal_status()['healthy']
   n=hfeed(hnew(p),s);rows.append(dict(mode=mode,returned=ok,live=v(h),restart=v(n)));continue
  if mode=='read_denied':p.write_bytes(b'')
  def opened(path,*a,**kw):
   if str(path)==str(p) and mode=='read_denied':raise PermissionError('read denied')
   return real_open(path,*a,**kw)
  def osopened(path,*a,**kw):
   if str(path)==str(p) and mode=='create_denied':raise PermissionError('create denied')
   return real_osopen(path,*a,**kw)
  def sync(fd):
   path=fpath(fd);trace.append(path)
   if (path==str(p) and mode=='create_file_fsync') or (path==str(T) and mode=='create_dir_fsync'):raise OSError(mode)
   return real_sync(fd)
  with patch.object(builtins,'open',opened),patch.object(os,'open',osopened),patch.object(os,'fsync',sync):h=hfeed(hnew(p),history())
  assert h.journal_status()['healthy']==(mode=='missing');held(h)
  if mode!='missing':assert not hb(h)
  rows.append(dict(mode=mode,live=v(h),trace=trace))
 from hive.appliance import HiveAppliance
 bad=T/'app-bad.jsonl';bad.write_bytes(b'{');app=HiveAppliance(rebind_journal=str(bad));assert app.status()['rebind_journal_healthy'] is False
 healthy=T/'app-good.jsonl';assert HiveAppliance(rebind_journal=str(healthy)).status()['rebind_journal_healthy'] is True
 row.update(cases=rows,appliance_health_field=True,observations='Missing at startup creates empty healthy file (loss is not detectable); runtime missing/size/tail changes fence; same-size prefix edits bypass last-record-only check; runtime PermissionError refusal leaves healthy=True.')

def legacy_default(row):
 rows=[]
 # Authentic 7678 v3 bytes, 7656 v2 bytes, and original v1 record.
 sources=[(1,dict(v=1,op='owner_rebind',agent_id='a1',plan_id='p',incident_id='i',actor='legacy-op',reason='legacy-proof')),(2,S/'experiments/20261008-astra-7656/journal-cases/target_success_then_failure.jsonl'),(3,S/'experiments/20261008-astra-7678/journal-7678/normal-order.jsonl')]
 for version,src in sources:
  p=T/('legacy-'+str(version)+'.jsonl');p.write_bytes((json.dumps(src)+'\n').encode() if isinstance(src,dict) else src.read_bytes());before=p.read_bytes();s=history();h=hfeed(hnew(p),s);held(h);assert not h.journal_status()['healthy'] and 'legacy or unknown' in h.journal_status()['fence']['error'] and not hb(h)
  st=v(h);assert h.clear_journal_fence('reviewer','legacy reviewed');assert Path(h.journal_status()['fence_clearances'][-1]['archived']).read_bytes()==before;held(hfeed(hnew(p),s));assert hb(h);n=hfeed(hnew(p),s);assert n._plan_owner=={'a1:p':'i'};rows.append(dict(version=version,before=st,after=v(n)))
 # Retain the exact four appliance default/env precedence checks from 7656.
 src=inspect.getsource(q['q']['default_and_legacy']);src=src[:src.index(" legacy={'v':1")]+" row.update(appliance=cases,direct_reducer_default_volatile=HiveReducer()._volatile_rebinds)\n"
 env=dict(q['q']);env['T']=T;exec(compile(src,'adapted-default-controls','exec'),env);d={};env['default_and_legacy'](d)
 row.update(cases=rows,defaults=d,adapted_source=src,docs='README and policy accurately say v1-v3 whole-journal fence; explicit clear + reissue required')

def old_markers(row):
 rows=[]
 for mode in ['invalid_utf8','invalid_json','json_array','empty_object','edited_op_id','missing_entry','valid_nonlast','legacy_v1']:
  p,s,h=fresh('marker-'+mode,two());assert hb(h) and bindq(h);fp=Path(str(p)+'.fence');r=records(p)[0]
  vals={'invalid_utf8':b'\xff','invalid_json':b'{oops','json_array':b'[]','empty_object':b'{}','edited_op_id':json.dumps(dict(v=2,op_id='changed-id',entry=r,marker_hash='bad')).encode(),'missing_entry':b'{"v":2,"op_id":"changed-id"}','valid_nonlast':json.dumps(dict(v=2,op_id=r['op_id'],entry=r)).encode(),'legacy_v1':json.dumps(dict(v=1,op_id=r['op_id'],entry=r)).encode()};fp.write_bytes(vals[mode]);n=hfeed(hnew(p),s);assert not n._plan_owner and n.journal_status()['fence']['kind']=='legacy_marker';assert not hb(n);assert n.clear_journal_fence('reviewer','inspect old marker');assert not fp.exists()
  for x in restarts(p,s):assert not x._plan_owner and x.journal_status()['healthy']
  rows.append(dict(mode=mode,cleared=v(n)))
 row.update(cases=rows,interpretation='Presence alone fences all, so old marker hash/trust narrowing no longer applicable')

out={}
functions=[('exact7678_archived_witnesses',historical_exact),('native_tails_order_edits',tails_and_order),('v4_fault_matrix',fault_matrix),('applied_no_commit',commit_absent),('crash_boundaries',crash_boundaries),('duplicate_commit',duplicates),('archive_splice',splice),('clean_prefixes',clean_prefixes),('startup_external_health',startup_external),('legacy_default',legacy_default),('old_markers',old_markers)]
# Extra clearance/caps groups are installed below by the generation script.
for name,fn in functions:
 r={}
 try:fn(r);r['passed']=True
 except Exception as ex:r.update(passed=False,error=repr(ex),traceback=traceback.format_exc())
 out[name]=r;print(name,r['passed'],r.get('error',''),flush=True);save('followup7694.json',out)
save('followup7694-summary.json',dict(groups=len(out),passed=sum(r['passed'] for r in out.values()),failed=[k for k,vv in out.items() if not vv['passed']],note='Defect assertions are not safety approvals'))
sys.exit(not all(r['passed'] for r in out.values()))
