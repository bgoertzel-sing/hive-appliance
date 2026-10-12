"""Independent 7678 followups. Defect reproductions are not conformance passes."""
import copy,hashlib,json,os,sys,traceback
from pathlib import Path
from unittest.mock import patch
E=Path(__file__).resolve().parent
src=(E/'followup7669.py').read_text();q0={'__file__':str(E/'followup7669.py'),'__name__':'retained_followup'}
exec(compile(src[:src.index('\nfor name,fn in ')],str(E/'followup7669.py'),'exec'),q0)
I,P,R,hnew,hfeed,hop,hb,v,events,fpath,held,fenced,HiveReducer=[q0[k] for k in ['I','P','R','hnew','hfeed','hop','hb','v','events','fpath','held','fenced','HiveReducer']]
T=E/'journal-followup7678';T.mkdir(exist_ok=True);q0['T']=T;q0['q']['T']=T
fresh=q0['q']['fresh']
def save(n,o):(E/n).write_text(json.dumps(o,indent=2,default=str)+'\n')
def records(jp):return [json.loads(t) for t in jp.read_text().splitlines()]
def put(jp,es):jp.write_text(''.join(json.dumps(e,sort_keys=True)+'\n' for e in es))
def corrupt(e):
 e=copy.deepcopy(e);s=e['op_id'];e['op_id']=('0' if s[0]!='0' else '1')+s[1:];assert e['entry_hash']!=HiveReducer._entry_hash(e);return e

def exact_abort(row):
 jp,s,h=fenced('exact-abort-content');assert h.clear_journal_fence('reviewer','cancel this uncertain rebind');held(h)
 before=hfeed(hnew(jp),s);held(before);lines=records(jp);assert len(lines)==2 and lines[1]['op']=='abort_rebind';original=lines[1]['op_id'];lines[1]=corrupt(lines[1]);put(jp,lines)
 restarts=[]
 for _ in range(2):
  n=hfeed(hnew(jp),s);held(n);assert n.journal_status()['corrupt_records'] and n.journal_status()['unapplied_total']==1;restarts.append(v(n))
 row.update(verdict='CLOSED Medium exact7669 F-abort-content',original_abort_op=original,edited_abort=lines[1],before_corruption=v(before),restarts=restarts,scope='Exact one-character op_id edit, no recomputed hashes')

def live_state(row):
 rows=[]
 for mode in ['remove_directory_fsync','remove_unlink']:
  jp,s,h=fresh('memory-'+mode);fp=Path(str(jp)+'.fence');before=copy.deepcopy(vars(h));real_sync=os.fsync;real_unlink=os.unlink;ds=0;trace=[]
  def sync(fd):
   nonlocal ds
   p=fpath(fd);trace.append(dict(op='fsync',path=p,owner=dict(h._plan_owner),audit=list(h.owner_rebinds),open=hop(h)))
   if p==str(T):
    ds+=1
    if mode=='remove_directory_fsync' and ds==2:raise OSError('post-unlink directory fsync')
   return real_sync(fd)
  def unlink(p,*a,**kw):
   if mode=='remove_unlink' and str(p)==str(fp):raise OSError('unlink')
   return real_unlink(p,*a,**kw)
  with patch.object(os,'fsync',sync),patch.object(os,'unlink',unlink):ok=hb(h)
  assert not ok;held(h);after=copy.deepcopy(vars(h));changed=[k for k in before if before[k]!=after[k]]
  assert set(changed)=={'_journal_indeterminate','_journal_aborted'}
  assert before['_pending_receipts']==after['_pending_receipts'] and before['_state']==after['_state'] and h.owner_rebinds==[]
  ind=h.journal_status()['indeterminate'];assert ind['abort_durable'] is True and ind['marker_present']==(mode=='remove_unlink') and ind['persisted']==ind['marker_present']
  rs=records(jp);assert len(rs)==2 and rs[1]['op']=='abort_rebind' and rs[1]['entry_hash']==h._entry_hash(rs[1]) and rs[1]['target_in_journal']
  assert not hb(h);restarts=[]
  for _ in range(2):
   n=hfeed(hnew(jp),s);held(n);assert n.owner_rebinds==[];restarts.append(v(n))
  assert all(not x['owner'] and not x['audit'] and x['open']==['i'] for x in trace)
  rows.append(dict(mode=mode,returned=ok,changed_state_fields=changed,live=v(h),trace=trace,restarts=restarts,events=events(s)))
 row.update(cases=rows,verdict='CLOSED requested memory/disk agreement: only journal diagnostics change; business state never applied, so no compensating rollback needed')

def compound(row):
 rows=[]
 for mode in ['abort_write_fail_marker_ok','abort_fsync_rollback_fail_marker_ok','abort_write_and_marker_open_fail','abort_write_and_marker_dirsync_fail','abort_short_rollback_fail_marker_open_fail']:
  jp,s,h=fresh('compound-'+mode);fp=str(jp)+'.fence';real_open=os.open;real_sync=os.fsync;real_write=os.write;real_trunc=os.ftruncate;ds=0;js=0;trace=[]
  def sync(fd):
   nonlocal ds,js
   p=fpath(fd);trace.append(['fsync',p])
   if p==str(T):
    ds+=1
    if ds==2 or (ds==3 and mode=='abort_write_and_marker_dirsync_fail'):raise OSError('directory fsync '+str(ds))
   if p==str(jp):
    js+=1
    if js>=2 and mode=='abort_fsync_rollback_fail_marker_ok':raise OSError('abort fsync')
   return real_sync(fd)
  def opened(p,*a,**kw):
   trace.append(['open',str(p)])
   if ds>=2 and str(p)==fp+'.tmp' and mode in ['abort_write_and_marker_open_fail','abort_short_rollback_fail_marker_open_fail']:raise OSError('marker restore open')
   return real_open(p,*a,**kw)
  def write(fd,data):
   p=fpath(fd);trace.append(['write',p,len(data)])
   if ds>=2 and p==str(jp):
    if mode=='abort_short_rollback_fail_marker_open_fail':return real_write(fd,data[:15])
    if mode!='abort_fsync_rollback_fail_marker_ok':raise OSError('abort write')
   return real_write(fd,data)
  def trunc(fd,n):
   if ds>=2 and mode in ['abort_fsync_rollback_fail_marker_ok','abort_short_rollback_fail_marker_open_fail']:raise OSError('abort rollback truncate')
   return real_trunc(fd,n)
  with patch.object(os,'fsync',sync),patch.object(os,'open',opened),patch.object(os,'write',write),patch.object(os,'ftruncate',trunc):ok=hb(h)
  assert not ok;held(h);ind=h.journal_status()['indeterminate'];assert ind['abort_durable'] is False
  assert ind['marker_present']==(mode in ['abort_write_fail_marker_ok','abort_fsync_rollback_fail_marker_ok','abort_write_and_marker_dirsync_fail'])
  exposed=mode in ['abort_write_and_marker_open_fail','abort_short_rollback_fail_marker_open_fail']
  if 'marker_open_fail' in mode or mode=='abort_write_and_marker_dirsync_fail':assert 'MAY replay after a restart' in ind['error']
  else:assert 're-written durably' in ind['error']
  restarts=[]
  for _ in range(2):
   n=hfeed(hnew(jp),s)
   if exposed:assert n._plan_owner=={'a1:p':'i'} and hop(n)==[] and n.journal_status()['indeterminate'] is None
   else:held(n)
   restarts.append(v(n))
  rows.append(dict(mode=mode,returned=ok,live=v(h),restarts=restarts,trace=trace,refused_replayed=exposed))
 row.update(cases=rows,verdict='OPEN Medium F-journal-refused-compound: acknowledged triple-fault boundary reproduces refused rebind on restart; status clearly warns while process is alive',scope='Concrete OSError injection + fresh reducers, not power-loss simulation. Marker-dir-fsync failure leaves visible marker but no durability guarantee; not claimed to replay without a crash.')

def temporal(row):
 # Obtain genuine serial writer records: cancelled A followed by successful B.
 s=q0['q']['history']()+[I('j','q'),P('q'),R('q-ok','q','j'),P('q','j')]
 jp,_,h=fresh('temporal-base',s);real=os.fsync
 def sync(fd):
  if fpath(fd)==str(jp):raise OSError('A append')
  return real(fd)
 with patch.object(os,'fsync',sync),patch.object(os,'ftruncate',side_effect=OSError('rollback')):assert not hb(h)
 assert h.clear_journal_fence('reviewer','cancel A');assert h.rebind_plan_owner('a1','q','j',actor='reviewer',reason='later B')
 A,abA,B=records(jp);assert abA['op_id']==A['op_id'];base=hfeed(hnew(jp),s);assert base._plan_owner=={'a1:q':'j'}
 # Genuine cancelled B pair is produced by the writer as well (separate file).
 bj=T/'temporal-cancel-B.jsonl';bh=hfeed(hnew(bj),s);real=os.fsync
 def syncb(fd):
  if fpath(fd)==str(bj):raise OSError('B append')
  return real(fd)
 with patch.object(os,'fsync',syncb),patch.object(os,'ftruncate',side_effect=OSError('rollback')):assert not bh.rebind_plan_owner('a1','q','j',actor='reviewer',reason='cancelled B')
 assert bh.clear_journal_fence('reviewer','cancel B');BB,abB=records(bj)
 cases=[('serial_corrupt_cancel_A_then_good_B',[A,corrupt(abA),B],{'a1:q':'j'},False),('corrupt_cancel_B_after_target',[A,BB,corrupt(abB)],{},False),('forward_intact_cancel_B',[A,abB,BB],{'a1:q':'j'},True),('forward_corrupt_cancel_B',[A,corrupt(abB),BB],{'a1:q':'j'},True),('duplicate_after_corrupt_cancel',[BB,corrupt(abB),BB],{},False),('interleaved_cancellations',[A,abA,BB,corrupt(abB)],{},False)]
 rows=[]
 for name,recs,owners,revived in cases:
  dest=T/(name+'.jsonl');put(dest,recs);restarts=[]
  for _ in range(2):
   n=hfeed(hnew(dest),s);assert n._plan_owner==owners and n.journal_status()['corrupt_records'];restarts.append(v(n))
  rows.append(dict(case=name,restarts=restarts,previously_cancelled_B_replays=revived))
 row.update(cases=rows,events=events(s),verdict='Narrow scope is safe for intact serial ordering with in-place cancellation corruption, but cannot cover reordered/forward cancellation records: later target replays even when corrupt_records explicitly diagnoses it',scope='Forward cases move authentic cancellation before target (plus one-character edit in corrupt variant); not generated by current single-writer append protocol. No hash recomputed. Intact order controls and duplicate physical line remain fail-closed. Requires explicit corruption/order scope or whole-journal fencing.')

def torn_abort(row):
 rows=[]
 for mode in ['lost_final_newline','truncated_abort_json','malformed_complete_abort','blank_abort_line']:
  jp,s,h=fenced('torn-abort-'+mode);assert h.clear_journal_fence('reviewer','durably cancel before storage corruption');held(hfeed(hnew(jp),s));original=jp.read_bytes();entry,ab=original.splitlines(keepends=True);assert json.loads(ab)['op']=='abort_rebind'
  if mode=='lost_final_newline':damaged=original[:-1]
  elif mode=='truncated_abort_json':damaged=entry+ab[:20]
  elif mode=='malformed_complete_abort':damaged=entry+ab[:20]+b'\n'
  else:damaged=entry+b' '*len(ab.rstrip(b'\n'))+b'\n'
  jp.write_bytes(damaged);restarts=[]
  for _ in range(2):
   n=hfeed(hnew(jp),s)
   if mode=='malformed_complete_abort':held(n);assert n.journal_status()['corrupt_records']
   else:assert n._plan_owner=={'a1:p':'i'} and hop(n)==[] and not n.journal_status()['corrupt_records']
   restarts.append(v(n))
  asides=[dict(file=p.name,hex=p.read_bytes().hex()) for p in T.glob(jp.name+'.torn-*')]
  if mode in ['lost_final_newline','truncated_abort_json']:assert len(asides)==1 and bytes.fromhex(asides[0]['hex'])==damaged[len(entry):]
  rows.append(dict(mode=mode,original_hex=original.hex(),damaged_hex=damaged.hex(),restarts=restarts,asides=asides,cancelled_replayed=mode!='malformed_complete_abort'))
 row.update(cases=rows,verdict='OPEN Medium F-abort-tail: deleting only final newline from a durably successful cancellation silently revives it; copied-aside cancellation not considered by parser',scope='Single-byte newline loss needs neither target change nor record reordering nor recomputed hash. Whitespace replacement is a broader destructive-content control. Preserve forensic aside, but do not treat unknown/cancellation tail as authorization.')

def fence_structure(row):
 # Two successful entries let us distinguish full fencing from only-last fencing.
 s=q0['q']['history']()+[I('j','q'),P('q'),R('qrc','q','j'),P('q','j')]
 jp,_,h=fresh('two-entries',s);assert hb(h);assert h.rebind_plan_owner('a1','q','j',actor='reviewer',reason='second');A,B=records(jp);rows=[]
 for mode in ['valid_last','valid_nonlast','legacy_v1','marker_bad_hash','embedded_bad_hash','entry_op_mismatch','missing_entry']:
  dest=T/('fence-structure-'+mode+'.jsonl');put(dest,[A,B]);fp=Path(str(dest)+'.fence');entry=A if mode=='valid_nonlast' else B;m=json.loads(h._marker_bytes(entry))
  if mode=='legacy_v1':m={'v':1,'op_id':B['op_id'],'entry':B}
  if mode=='marker_bad_hash':m['marker_hash']='bad'
  if mode=='embedded_bad_hash':m['entry']['reason']='edited';m['marker_hash']=h._hash_without(m,'marker_hash')
  if mode=='entry_op_mismatch':m['op_id']='different';m['marker_hash']=h._hash_without(m,'marker_hash')
  if mode=='missing_entry':m.pop('entry');m['marker_hash']=h._hash_without(m,'marker_hash')
  fp.write_text(json.dumps(m));n=hfeed(hnew(dest),s);ind=n.journal_status()['indeterminate'];assert ind
  assert n._plan_owner==({'a1:p':'i'} if mode=='valid_last' else {})
  assert ind['scope']==('entry' if mode=='valid_last' else 'all');before=v(n);trace=[];real_sync=os.fsync;real_unlink=os.unlink
  def sync(fd):trace.append(['fsync',fpath(fd),fp.exists(),dest.read_text()]);return real_sync(fd)
  def unlink(p,*a,**kw):trace.append(['unlink',str(p)]);return real_unlink(p,*a,**kw)
  with patch.object(os,'fsync',sync),patch.object(os,'unlink',unlink):assert n.clear_journal_fence('reviewer','inspect '+mode)
  ab=[x for x in records(dest) if x['op']=='abort_rebind'];assert B['op_id'] in {x['op_id'] for x in ab};assert all(x['entry_hash']==h._entry_hash(x) for x in ab)
  ix=next(i for i,x in enumerate(trace) if x[0]=='unlink');assert all(x[0]=='fsync' and x[1]==str(dest) and x[2] for x in trace[:ix]) and len(trace[:ix])==len(ab)
  owners={} if mode=='valid_nonlast' else {'a1:p':'i'};restarts=[]
  for _ in range(2):
   r=hfeed(hnew(dest),s);assert r._plan_owner==owners and r.journal_status()['indeterminate'] is None and not r.journal_status()['corrupt_records'];restarts.append(v(r))
  rows.append(dict(mode=mode,before_clear=before,abort_records=ab,trace=trace,restarts=restarts))
 row.update(cases=rows,verdict='CLOSED F-fence-content exact and extended: trusted last entry selective, all other cases broad; durable clearance always cancels last; legacy v1 blocks all until clearance')

out={}
functions=[('exact_abort_content',exact_abort),('live_memory_disk_agreement',live_state),('compound_failure',compound),('corrupt_record_temporal_scope',temporal),('torn_cancelled_record',torn_abort),('fence_structure_clearance_v1',fence_structure),('rollback_preserves_prior_record',q0['prior_record']),('startup_fsync_boundaries',q0['startup']),('complete_matching_legacy_fence_clear',q0['matching_fence_and_clear'])]
for name,fn in functions:
 r={}
 try:fn(r);r['passed']=True
 except Exception as ex:r.update(passed=False,error=repr(ex),traceback=traceback.format_exc())
 out[name]=r;print(name,r['passed'],r.get('error',''),flush=True);save('followup7678.json',out)
save('followup7678-summary.json',dict(groups=len(out),passed=sum(r['passed'] for r in out.values()),failed=[k for k,vv in out.items() if not vv['passed']],note='Includes defect reproductions, not safety approvals'))
sys.exit(not all(r['passed'] for r in out.values()))
