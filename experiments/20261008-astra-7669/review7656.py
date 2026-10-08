"""Independent 7656 probes; defect-reproduction assertions are not safety passes."""
import copy, hashlib, inspect, json, logging, os, sys, traceback
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
E=Path(__file__).resolve().parent
sys.path.insert(0,os.environ['HIVE_SRC'])
raw=(E/'review7638-final.py').read_text();defs=raw[:raw.index('\nout={}\n')]
g={'__file__':str(E/'review7638-final.py'),'__name__':'prior7638'}
exec(compile(defs,str(E/'review7638-final.py'),'exec'),g)
I,P,R,hnew,hfeed,hop,hview,hb=[g[k] for k in ['I','P','R','hnew','hfeed','hop','hview','hb']]
HiveReducer,HiveEvent,Event=[g[k] for k in ['HiveReducer','HiveEvent','Event']]
from hive.appliance import HiveAppliance
from hive.adapter import StubAgentAdapter
import hive.reducer as hr
T=E/'journal-cases';T.mkdir(exist_ok=True)
g['T']=T
logging.getLogger().setLevel(logging.CRITICAL)
def hist_closed():return [I('i','p'),P(),R(i='i'),P(i='i')]
def bind(h):return hb(h)
def v(h):return dict(hview(h),journal_status=h.journal_status(),event_seq=h._event_seq,digest=h._stream_digest)
def events(s):return [e.to_dict() for e in s]
def save(n,o):(E/n).write_text(json.dumps(o,indent=2,default=str)+'\n')
def normalized(h):
 x=hview(h)
 for a in x['audit']:a.pop('replayed',None)
 return x

def unregister(row):
 rows=[]
 for mode in ['reducer','appliance']:
  s=[I('j','p'),P(),R('j-evidence',i='j')];suffix=[I('k'),P(i='k')]
  if mode=='reducer':
   h=hfeed(hnew(),s);before=v(h);h.unregister_agent('a1');after_unreg=v(h);h.register_agent('a1');hfeed(h,suffix)
  else:
   app=HiveAppliance(volatile_rebinds=True);app.register_agent(StubAgentAdapter('a1',events=s));assert app.tick()['errors']==[]
   h=app.reducer;before=v(h);app.unregister_agent('a1');after_unreg=v(h);app.register_agent(StubAgentAdapter('a1',events=suffix));assert app.tick()['errors']==[]
  assert after_unreg['hold']=={'a1:p':'ownerless_held'}
  assert hop(h)==['k'] and not h._plan_owner and not h.owner_rebinds and h.quarantined_plans()==['a1:p']
  after=v(h);pv=h.preview_rebind('a1','p','k');assert pv['foreign_steps_discarded']==[0] and pv['would_close']==[]
  assert hb(h,'k') and hop(h)==['k']
  hfeed(h,[R('j-evidence',i='j')]);assert hop(h)==['k']
  hfeed(h,[R('fresh-k',i='k')]);assert hop(h)==[]
  rows.append(dict(mode=mode,events=events(s),suffix=events(suffix),before=before,after_unregister=after_unreg,after_reregister=after,preview=pv,after_fresh_evidence=v(h)))
 row.update(verdict='CLOSED prior High exact witness',cases=rows)

def journal_order(row):
 rows=[]
 for label,receipts in [('target_success_then_failure',[R('yes',i='i'),R('no',i='i',ok=False)]),('target_success_then_foreign_failure',[R('yes',i='i'),R('no',i='j',ok=False)]),('plan_success_then_failure',[R('yes'),R('no',ok=False)])]:
  jp=T/(label+'.jsonl');s=[I('i','p'),I('j','p'),P()]+receipts+[P(i='i')]
  h=hfeed(hnew(jp),s);assert bind(h);before=v(h);assert hop(h)==['i','j']
  n=hfeed(hnew(jp),s);assert normalized(n)==normalized(h);assert not n.journal_status()['unapplied'] and n.owner_rebinds[0]['replayed']
  changed=copy.deepcopy(s);changed[3].id='different-event-id'
  m=hfeed(hnew(jp),changed);assert m.quarantined_plans()==['a1:p'] and not m._plan_owner and len(m.journal_status()['unapplied'])==1
  reordered=s[:3]+[s[4],s[3]]+s[5:];q=hfeed(hnew(jp),reordered);assert q.quarantined_plans()==['a1:p'] and q.journal_status()['unapplied']
  rows.append(dict(case=label,events=events(s),original=before,replay=v(n),identity_mismatch=v(m),order_mismatch=v(q)))
 row.update(verdict='CLOSED exact three original orders; content boundary separately tested',cases=rows)

def content_hash(row):
 s=[I('i','p'),I('j','p'),P(),R('yes',i='i'),R('no',i='i',ok=False),P(i='i')]
 jp=T/'same-ids-different-payload.jsonl';h=hfeed(hnew(jp),s);assert bind(h) and hop(h)==['i','j']
 changed=copy.deepcopy(s);changed[4].payload['verified']=True
 n=hfeed(hnew(jp),changed)
 assert n._stream_digest==h._stream_digest and not n.journal_status()['unapplied']
 assert hop(n)==['j'] and n._plan_owner=={'a1:p':'i'}
 row.update(verdict='OPEN High F-journal-content',defect_reproduced=True,original_events=events(s),modified_events=events(changed),original=v(h),replay=v(n),interpretation='Stream digest excludes payload and timestamp. Same identity/kind with changed failure payload accepts original authorization on different evidence and closes original-open incident. Assumes same IDs can carry changed payload; no malicious hash collision required.')

def journal_controls(row):
 s=[I('i','p'),I('j','p'),P(),R(i='j'),P(i='i')];jp=T/'good.jsonl';h=hfeed(hnew(jp),s);calls=[];real=os.fsync
 def sync(fd):
  calls.append(dict(owner=copy.deepcopy(h._plan_owner),audit=copy.deepcopy(h.owner_rebinds),record=json.loads(jp.read_text())));return real(fd)
 with patch('hive.reducer.os.fsync',sync):assert bind(h)
 assert len(calls)==1 and calls[0]['owner']=={} and calls[0]['audit']==[]
 b=jp.read_bytes();n=hfeed(hnew(jp),s);assert normalized(n)==normalized(h)
 hfeed(n,s);n._replay_journal();assert len(n.owner_rebinds)==1 and jp.read_bytes()==b
 dp=T/'duplicate.jsonl';dp.write_bytes(b+b);d=hfeed(hnew(dp),s);assert len(d.owner_rebinds)==1 and d.journal_pending()==[]
 u=hfeed(hnew(),s);u._journal_path=str(T);before=copy.deepcopy(vars(u));assert not bind(u) and vars(u)==before
 row.update(write_ahead=calls,original=v(h),replay=v(n),duplicate=v(d),open_failure_unchanged=True)

def fault_matrix(row):
 rows=[]
 for mode in ['write_before','short_write','write_after_complete','fsync_before','fsync_after','truncate_before','truncate_after','rollback_fsync','close_after']:
  jp=T/('fault-'+mode+'.jsonl');s=hist_closed();h=hfeed(hnew(jp),s)
  real_write,real_sync,real_trunc,real_close=os.write,os.fsync,os.ftruncate,os.close
  trace=[];nsync=0
  def write(fd,data):
   trace.append('write:'+str(len(data)))
   if mode=='write_before':raise OSError('injected write-before')
   if mode=='short_write':return real_write(fd,data[:len(data)//2])
   got=real_write(fd,data)
   if mode=='write_after_complete':raise OSError('injected write-after-complete')
   return got
  def sync(fd):
   nonlocal nsync
   nsync+=1;trace.append('fsync:'+str(nsync))
   if nsync==1 and mode in ['fsync_before','truncate_before','truncate_after','rollback_fsync']:raise OSError('injected append-fsync')
   if nsync==1 and mode=='fsync_after':real_sync(fd);raise OSError('injected fsync-after')
   if nsync==2 and mode=='rollback_fsync':raise OSError('injected rollback-fsync')
   return real_sync(fd)
  def trunc(fd,size):
   trace.append('truncate:'+str(size))
   if mode=='truncate_before':raise OSError('injected truncate-before')
   ret=real_trunc(fd,size)
   if mode=='truncate_after':raise OSError('injected truncate-after')
   return ret
  def close(fd):
   trace.append('close');ret=real_close(fd)
   if mode=='close_after':raise OSError('injected close-after')
   return ret
  with patch('hive.reducer.os.write',write),patch('hive.reducer.os.fsync',sync),patch('hive.reducer.os.ftruncate',trunc),patch('hive.reducer.os.close',close):assert not bind(h)
  assert hop(h)==['i'] and h.quarantined_plans()==['a1:p'] and not h.owner_rebinds
  before=v(h);size=jp.stat().st_size
  if mode in ['truncate_before','truncate_after','rollback_fsync']:
   assert h.journal_status()['indeterminate'] and not bind(h)
  elif mode!='close_after':assert size==0 and h.journal_status()['indeterminate'] is None
  n=hfeed(hnew(jp),s)
  if mode in ['truncate_before','close_after']:
   assert hop(n)==[] and n._plan_owner=={'a1:p':'i'} and n.journal_status()['indeterminate'] is None
  else:assert hop(n)==['i'] and not n._plan_owner
  rows.append(dict(mode=mode,syscalls=trace,bytes_after_refusal=size,refused=v(h),before_second_call=before,restart=v(n),defect_reproduced=mode in ['truncate_before','close_after']))
 row.update(verdict='OPEN Medium F-journal-refused-fsync',cases=rows,flush_boundary='No Python file flush exists in new raw os.write implementation. os.write-to-fsync interval injected; rollback truncation and its own fsync separately injected.',interpretation='Successful rollback is fsynced and fixed. Failed truncation fences only live memory: restart silently applies refused operation. close() error after durable write also reports clean refusal with no fence and replays. A truncated-but-unfsynced rollback has no proven power-loss safety.')

def tail(row):
 rows=[]
 for mode in ['startup_ascii','startup_utf8','append_ascii','append_utf8']:
  jp=T/(mode+'.jsonl');fragment=b'{"op":' if mode.endswith('ascii') else b'\xff'
  if mode.startswith('startup'):jp.write_bytes(fragment)
  h=hnew(jp)
  if mode.startswith('append'):jp.write_bytes(fragment)
  s=hist_closed();hfeed(h,s);assert bind(h);aside=h.journal_status()['set_aside'];assert len(aside)==1 and Path(aside[0]).read_bytes()==fragment
  n=hfeed(hnew(jp),s);assert normalized(n)==normalized(h)
  rows.append(dict(mode=mode,events=events(s),aside=aside,restart=v(n)))
 # Complete malformed/UTF8 lines are isolated, later valid line preserved.
 jp=T/'invalid-complete-lines.jsonl';s=hist_closed();h=hfeed(hnew(jp),s);assert bind(h);good=jp.read_bytes();jp.write_bytes(b'\xff\n{broken}\n{"op":"wrong"}\n'+good)
 n=hfeed(hnew(jp),s);assert n.journal_status()['invalid_lines']==3 and n._plan_owner=={'a1:p':'i'}
 row.update(verdict='CLOSED original Medium normal startup/append, including invalid UTF8',cases=rows,complete_invalid_lines=v(n))

def tail_faults(row):
 rows=[]
 for phase in ['startup','append']:
  for mode in ['aside_write_before','aside_short_write','aside_fsync','truncate','journal_fsync','dir_fsync']:
   jp=T/('tailfault-'+phase+'-'+mode+'.jsonl');s=hist_closed();fragment=b'{"torn-evidence":12345'
   h=hfeed(hnew(jp),s) if phase=='append' else None;jp.write_bytes(fragment)
   real_write,real_sync,real_trunc=os.write,os.fsync,os.ftruncate;trace=[];wc=0;fc=0
   def write(fd,data):
    nonlocal wc
    wc+=1;trace.append('write:'+str(wc))
    if wc==1 and mode=='aside_write_before':raise OSError('aside-write')
    if wc==1 and mode=='aside_short_write':return real_write(fd,data[:3])
    return real_write(fd,data)
   def sync(fd):
    nonlocal fc
    fc+=1;trace.append('fsync:'+str(fc))
    if (mode,fc) in [('aside_fsync',1),('journal_fsync',2),('dir_fsync',3)]:raise OSError('tail-sync')
    return real_sync(fd)
   def trunc(fd,n):
    trace.append('truncate')
    if mode=='truncate':raise OSError('tail-truncate')
    return real_trunc(fd,n)
   raised=None;returned=None
   with patch('hive.reducer.os.write',write),patch('hive.reducer.os.fsync',sync),patch('hive.reducer.os.ftruncate',trunc):
    try:
     if phase=='startup':h=hnew(jp)
     else:returned=bind(h)
    except OSError as ex:raised=str(ex)
   if mode=='aside_short_write':
    assert raised is None
    if phase=='append':assert returned is True
    a=list(T.glob(jp.name+'.torn-*'));assert len(a)==1 and a[0].read_bytes()==fragment[:3]
   elif phase=='startup':assert raised is not None
   else:assert returned is False and not h._plan_owner
   if h is not None and mode!='aside_short_write':assert not h._plan_owner
   rows.append(dict(phase=phase,mode=mode,trace=trace,raised=raised,returned=returned,journal_bytes=jp.read_bytes().hex(),aside=[dict(name=p.name,bytes=p.read_bytes().hex()) for p in T.glob(jp.name+'.torn-*')]))
 row.update(cases=rows,verdict='OPEN Low F-tail-aside-short-write',interpretation='Tail quarantine os.write return count is ignored. A short write loses original torn bytes while journal truncation and successful new rebind proceed; valid complete entries remain safe. Other injected tail-boundary errors refuse append or fail startup before new entry.')

def default_and_legacy(row):
 s=hist_closed();cases=[]
 with patch.dict(os.environ,{},clear=False):
  os.environ.pop('HIVE_REBIND_JOURNAL',None)
  for mode in ['default','volatile','env','explicit_over_env']:
   if mode in ['env','explicit_over_env']:os.environ['HIVE_REBIND_JOURNAL']=str(T/('env-'+mode+'.jsonl'))
   kw={'volatile_rebinds':True} if mode=='volatile' else {}
   if mode=='explicit_over_env':kw['rebind_journal']=str(T/'explicit-wins.jsonl')
   app=HiveAppliance(**kw);app.register_agent(StubAgentAdapter('a1',events=s));assert app.tick()['errors']==[];h=app.reducer;before=v(h)
   ok=bind(h);assert ok==(mode!='default')
   assert hop(h)==(['i'] if mode=='default' else [])
   if mode=='explicit_over_env':assert h._journal_path==kw['rebind_journal']
   cases.append(dict(mode=mode,return_value=ok,before=before,after=v(h)))
 legacy={'v':1,'op':'owner_rebind','agent_id':'a1','plan_id':'p','incident_id':'i','actor':'legacy-op','reason':'legacy-proof'}
 jp=T/'legacy-v1.jsonl';jp.write_text(json.dumps(legacy)+'\n');h=hfeed(hnew(jp),s);assert not h._plan_owner and h.quarantined_plans()==['a1:p'] and len(h.journal_status()['unapplied'])==1
 before=v(h);assert bind(h);n=hfeed(hnew(jp),s);assert n._plan_owner=={'a1:p':'i'} and len(n.journal_status()['unapplied'])==1
 row.update(verdict='CLOSED prior Medium default; legacy deliberate fail-closed compatibility change',appliance=cases,legacy_before=before,legacy_reissue_restart=v(n),direct_reducer_default_volatile=HiveReducer()._volatile_rebinds)

def rejected_and_partial(row):
 s=[I('owned'),P('ownedp','owned'),I('i','p'),P(),R(i='i'),P(i='i')];jp=T/'conflicting-plan.jsonl';h=hfeed(hnew(jp),s)
 before=copy.deepcopy(vars(h));reject=P('ownedp','other');hfeed(h,[reject]);after=copy.deepcopy(vars(h));after['rejected_plan_registrations']=before['rejected_plan_registrations'];assert before==after
 assert bind(h);n=hfeed(hnew(jp),s[:2]+[reject]+s[2:]);assert normalized(n)==normalized(h) and n._event_seq==6
 # Partial replay cannot reconstruct counter/hash from an agent/local snapshot.
 partial=hfeed(hnew(jp),s[2:]);assert partial.quarantined_plans()==['a1:p'] and partial.journal_status()['pending']==1 and partial.journal_status()['unapplied']==[]
 hfeed(partial,[I('extra1'),I('extra2')]);assert len(partial.journal_status()['unapplied'])==1 and not partial._plan_owner
 # Synthetic hydrate of event-derived reducer state without counters, not an actual API.
 held=hfeed(hnew(),s);snap=copy.deepcopy(vars(held));hydrated=hnew(jp)
 for k,value in snap.items():
  if not k.startswith('_journal') and k not in ['_event_seq','_stream_digest']:setattr(hydrated,k,value)
 hydrated._replay_journal();assert hydrated._event_seq==0 and hydrated.journal_status()['pending']==1 and hydrated.quarantined_plans()==['a1:p']
 row.update(rejected_PLAN=dict(events=events(s),rejected=reject.to_dict(),only_changed_field='rejected_plan_registrations +1 (existing diagnostic exception)',stream_position_unchanged=True,restart=v(n)),partial_suffix=v(partial),synthetic_snapshot_without_stream_metadata=v(hydrated),native_snapshot_api=hasattr(HiveReducer,'snapshot'),native_restore_api=hasattr(HiveReducer,'restore_snapshot'),interpretation='No native hive reducer snapshot/restore API. Snapshot-only/partial reconstruction cannot replay authorization. Pending remains visible until position reached, then mismatch is unapplied; full original ordered replay required. Synthetic hydrate only demonstrates missing metadata, not a supported restore path.')

def caps(row):
 # Retained 600-hold lifecycle helper with only new cap expectations adapted.
 src=inspect.getsource(g['a']['isolation_and_caps'])
 replacements={
  'and len(h.owner_candidates)==600':'and len(h.owner_candidates)==256 and h.owner_candidates_dropped==344',
  'hive_candidate_keys=600':'hive_candidate_keys=256',
  "assert h.preview_rebind('a1','p599','i599')['allowed']":"assert not h.preview_rebind('a1','p599','i599')['allowed'];assert h.preview_rebind('a1','p599','i599',True)['allowed']"}
 for old,new in replacements.items():assert old in src;src=src.replace(old,new)
 env=dict(g['a']);exec(compile(src,'adapted-cap-helper','exec'),env);env['isolation_and_caps'](row)
 row['adaptations']=replacements;row['adapted_helper_sha256']=hashlib.sha256(src.encode()).hexdigest()
 # Exact 255/256/257 boundaries, no monkeypatch of actual candidate limit.
 h=hnew();counts=[]
 for k in range(257):
  hfeed(h,[I('i'+str(k),'p'+str(k)),P('p'+str(k)),P('p'+str(k),'i'+str(k))])
  if k>=254:counts.append(dict(plans=k+1,candidates=len(h.owner_candidates),holds=len(h.quarantined_plans()),drops=h.owner_candidates_dropped))
 assert counts==[dict(plans=255,candidates=255,holds=255,drops=0),dict(plans=256,candidates=256,holds=256,drops=0),dict(plans=257,candidates=256,holds=257,drops=1)]
 row['candidate_boundary']=counts
 # Real 64MiB boundary; fixed timestamp/UUID only to calculate exact record size.
 class U:hex='0'*32
 jp=T/'cap-size-template.jsonl';s=hist_closed();h=hfeed(hnew(jp),s)
 with patch('hive.reducer.time.time',return_value=123.0),patch('hive.reducer.uuid.uuid4',return_value=U()):assert bind(h)
 template=jp.read_bytes();limit=hr.MAX_HIVE_JOURNAL_BYTES;assert limit==64*1024*1024
 big=E/'tmp'/'cap-cases';big.mkdir(parents=True,exist_ok=True);boundary=[]
 for label,size in [('one_under_after_append',limit-len(template)-1),('exact_after_append',limit-len(template)),('one_over_after_append',limit-len(template)+1),('already_at_cap',limit),('already_over_cap',limit+1)]:
  path=big/(label+'.jsonl')
  with path.open('wb') as f:f.write(b' '*(size-1)+b'\n')
  h=hfeed(hnew(path),s);before=path.stat().st_size
  with patch('hive.reducer.time.time',return_value=123.0),patch('hive.reducer.uuid.uuid4',return_value=U()):ok=bind(h)
  assert ok==(label in ['one_under_after_append','exact_after_append'])
  assert path.stat().st_size==before+(len(template) if ok else 0)
  if not ok:assert h.quarantined_plans()==['a1:p'] and not h._plan_owner
  n=hfeed(hnew(path),s);assert bool(n._plan_owner)==ok
  boundary.append(dict(case=label,before=before,after=path.stat().st_size,returned=ok,hold=n.quarantined_plans(),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
 row['journal_boundary']=boundary;row['journal_limit']=limit;row['large_fixture_policy']='Generated 64MiB padding files excluded; exact recipe, sizes and hashes retained.'

def recovery_text(row):
 from tests.test_astra7582 import test_local_recovery_text_names_all_hold_reasons
 test_local_recovery_text_names_all_hold_reasons();row['authored_test_real_assertions_pass']=True
 # Mutation proves assertion executes, not merely an empty-text conditional.
 Reducer=g['Reducer'];original=Reducer.restore_snapshot
 def poisoned(self,snap):original(self,snap);self.migration_diagnostics['recovery']=''
 with patch.object(Reducer,'restore_snapshot',poisoned):
  try:test_local_recovery_text_names_all_hold_reasons()
  except AssertionError:row['empty_recovery_mutant_detected']=True
  else:raise AssertionError('recovery mutation survived')

out={}
functions=[('F_unregister_escape',unregister),('F_journal_order_exact',journal_order),('F_journal_content',content_hash),('journal_controls',journal_controls),('F_journal_refused_fsync',fault_matrix),('F_journal_tail_exact',tail),('tail_fault_boundaries',tail_faults),('defaults_legacy',default_and_legacy),('rejected_partial_snapshot',rejected_and_partial),('caps',caps),('recovery_text_assertions',recovery_text),('F_foreign_progress_retained',g['foreign']),('incidentless_retained',g['incidentless']),('F_hold_expiry_retained',g['hold']),('quiet_guidance_retained',g['quiet_and_guidance']),('exact_plan_only_witness',g['a']['witness']),('hold_144_schedules',g['a']['schedules']),('refusals_pending',g['a']['refusals_and_pending']),('late_link_warnings',g['a']['warnings']),('retained_regressions',g['retained'])]
for name,fn in functions:
 r={}
 try:fn(r);r['passed']=True
 except Exception as ex:r.update(passed=False,error=repr(ex),traceback=traceback.format_exc())
 out[name]=r;print(name,r['passed'],r.get('error',''),flush=True)
 save('review7656.json',out)
sys.exit(not all(r['passed'] for r in out.values()))
