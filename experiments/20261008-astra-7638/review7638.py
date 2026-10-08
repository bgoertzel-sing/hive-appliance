"""Independent re-review: assertions distinguish conformance controls from reproduced defects."""
import copy, hashlib, inspect, json, logging, os, sys, traceback
from pathlib import Path
from unittest.mock import patch
E=Path(__file__).resolve().parent
sys.path.insert(0,os.environ['HIVE_SRC'])
raw=(E/'review7582.py').read_text();defs=raw[:raw.index('\nout={}\n')]
a={'__file__':str(E/'review7582.py'),'__name__':'prior7582'};exec(compile(defs,str(E/'review7582.py'),'exec'),a)
I,P,R,new,feed,rt,replay,opens,view,preview,rebind=[a[k] for k in ['I','P','R','new','feed','rt','replay','opens','view','preview','rebind']]
Reducer,HiveReducer,HiveEvent,Event=[a[k] for k in ['Reducer','HiveReducer','HiveEvent','Event']]
logging.getLogger().setLevel(logging.CRITICAL)
T=E/'journal-cases';T.mkdir(exist_ok=True)
def hnew(journal=None):
 h=HiveReducer(rebind_journal=str(journal) if journal else None);h.register_agent('a1');return h
def hfeed(h,hist):
 for d in json.loads(json.dumps([e.to_dict() for e in hist])):h.reduce(HiveEvent(source_agent='a1',original_event=Event.from_dict(d)))
 return h
def hop(h):return sorted(i['incident_id'] for i in h._open_agent_incidents('a1'))
def hview(h):return dict(open=hop(h),hold=h.quarantine_reasons(),owner=h._plan_owner,audit=copy.deepcopy(h.owner_rebinds),pending=h.journal_pending(),verified={k:sorted(v) for k,v in h._plan_verified_steps.items()},failed={k:sorted(v) for k,v in h._plan_failed.items()})
def hb(h,i='i',**kw):return h.rebind_plan_owner('a1','p',i,actor='operator-original',reason='case-proof',allow_non_candidate=True,**kw)

def foreign(row):
 rows=[]
 for address in ['incident','dual']:
  for restart in [False,True]:
   hist=[I('i','p'),I('j','p'),P(),R(p='' if address=='incident' else 'p',i='j'),P(i='i')];l,h=new()
   for e in hist:feed(l,h,e)
   if restart:l=rt(l);h=replay(hist)
   pv,hv=preview(l,h);assert pv['foreign_steps_discarded']==hv['foreign_steps_discarded']==[0];assert pv['would_close']==hv['would_close']==[]
   assert rebind(l,h)==[True,True];assert opens(l,h)==[['i','j'],['i','j']]
   assert l.migration_diagnostics['owner_rebinds'][-1]['foreign_steps_discarded']==h.owner_rebinds[-1]['foreign_steps_discarded']==[0]
   after=view(l,h);feed(l,h,R('j-again',p='' if address=='incident' else 'p',i='j'));assert opens(l,h)==[['i','j'],['i','j']]
   feed(l,h,R('i-new',i='i'));assert opens(l,h)==[['j'],['j']]
   assert rebind(l,h,'j',True)==[False,False]
   rows.append(dict(address=address,restart=restart,events=[e.to_dict() for e in hist],preview=[pv,hv],after_rebind=after,after_new_i=view(l,h)))
 row['exact_7582_witnesses']=rows
 variants=[]
 for label,receipts,discard,verified,closed in [
  ('foreign_failure',[R(i='j',ok=False)],[0],[],False),
  ('target_then_foreign_failure',[R('i-ok',i='i'),R('j-fail',i='j',ok=False)],[0],[],False),
  ('foreign_failure_then_target',[R('j-fail',i='j',ok=False),R('i-ok',i='i')],[],[0],True),
  ('foreign_then_blank',[R('j-ok',i='j'),R('plan-ok')],[],[0],True),
  ('blank_then_foreign',[R('plan-ok'),R('j-ok',i='j')],[0],[],False)]:
  for restart in [False,True]:
   l,h=new();hist=[I('i','p'),I('j','p'),P()]+receipts+[P(i='i')]
   for e in hist:feed(l,h,e)
   if restart:l=rt(l);h=replay(hist)
   pv,hv=preview(l,h);assert pv['foreign_steps_discarded']==hv['foreign_steps_discarded']==discard
   assert rebind(l,h)==[True,True];assert opens(l,h)==([['j'],['j']] if closed else [['i','j'],['i','j']]);assert sorted(l._plan_verified['p'])==sorted(h._plan_verified_steps['a1:p'])==verified
   variants.append(dict(case=label,restart=restart,preview=[pv,hv],after=view(l,h)))
 l,h=new()
 for e in [I('i','p'),I('j','p'),P(n=3),R('x0',i='i'),R('x1',i='j',k=1),R('x2',k=2),P(i='i',n=3)]:feed(l,h,e)
 l=rt(l);pv,hv=preview(l,h);assert pv['foreign_steps_discarded']==hv['foreign_steps_discarded']==[1];assert rebind(l,h)==[True,True];assert l._plan_verified['p']==h._plan_verified_steps['a1:p']=={0,2};assert opens(l,h)==[['i','j'],['i','j']]
 feed(l,h,R('fresh1',i='i',k=1));assert opens(l,h)==[['j'],['j']]
 row.update(variants=variants,mixed_three_steps=view(l,h))
 # Old current snapshot has no per-step source: drop unknown evidence on rebind.
 l,h=new()
 for e in [I('i','p'),P(),R(),P(i='i')]:feed(l,h,e)
 snap=l.snapshot();snap.pop('plan_step_src');l=Reducer();l.restore_snapshot(json.loads(json.dumps(snap)));assert l.preview_rebind('p','i')['foreign_steps_discarded']==[0];assert l.rebind_plan_owner('p','i',actor='op',reason='old snapshot');assert [i.id for i in l.open_incidents()]==['i'];row['unknown_provenance_dropped']=True

def incidentless(row):
 l,h=new();hist=[I('j','p'),P(),R('held-plan-only'),P('q','j'),R('q0','q'),I('arbitrary-k'),P(i='arbitrary-k')]
 for e in hist:feed(l,h,e)
 assert opens(l,h)==[['arbitrary-k'],['arbitrary-k']];pv,hv=preview(l,h,'arbitrary-k');assert pv['would_close']==hv['would_close']==['arbitrary-k'];assert rebind(l,h,'arbitrary-k')==[True,True]
 row.update(events=[e.to_dict() for e in hist],preview=[pv,hv],after=view(l,h),interpretation='Plan-only evidence collected while held survives rebind to a newly introduced target. Safety relies on trusted operator proving the same plan/evidence applies to that target; rebind alone is not incident-specific evidence.')

def hold(row):
 rows=[]
 for restart in [False,True]:
  l,h=new();hist=[I('i','p'),P(),R(),P(i='i'),P('q','i'),R('q0','q'),I('k'),P(i='k')]
  for k,e in enumerate(hist):
   feed(l,h,e)
   if restart:l=rt(l);h=replay(hist[:k+1])
  assert opens(l,h)==[['k'],['k']];assert l.quarantine_reasons()=={'p':'ownerless_held'};assert h.quarantine_reasons()=={'a1:p':'ownerless_held'};assert not l._plan_owner.get('p') and not h._plan_owner.get('a1:p')
  before=view(l,h);assert rebind(l,h,'k')==[True,True];assert opens(l,h)==[[],[]];rows.append(dict(restart=restart,before=before,after=view(l,h)))
 hist=[I('i','p'),P(),R(),I('i','p',True),I('k'),P(i='k')];h=hfeed(hnew(),hist);assert h.quarantine_reasons()=={'a1:p':'ownerless_held'};assert not h._plan_owner;assert hop(h)==['k'];assert hview(hfeed(hnew(),hist))['hold']==hview(h)['hold']
 row.update(sibling_closure=rows,hive_duplicate_resolved=hview(h))

def unregister(row):
 h=hfeed(hnew(),[I('j','p'),P(),R('j-evidence',i='j')]);before=hview(h);h.unregister_agent('a1');after_unregister=hview(h);h.register_agent('a1');hfeed(h,[I('k'),P(i='k')]);after=hview(h)
 assert before['hold']=={'a1:p':'ownerless_linked'};assert not after_unregister['hold'];assert after['owner']['a1:p']=='k' and after['open']==[] and not after['audit']
 row.update(severity='High',defect_reproduced=True,before=before,after_unregister=after_unregister,after_reregister_and_PLAN=after,interpretation='Unregister deletes hold latch and incidents, but retains registered plan and explicitly foreign j progress. Ordinary PLAN sets k and closes it with no audit or source discard.')

def journal_good(row):
 jp=T/'good.jsonl';hist=[I('i','p'),I('j','p'),P(),R(i='j'),P(i='i')];h=hfeed(hnew(jp),hist)
 real=__import__('os').fsync;calls=[]
 def fsync(fd):
  calls.append(dict(owner_before=copy.deepcopy(h._plan_owner),audit_before=copy.deepcopy(h.owner_rebinds),line=json.loads(jp.read_text())));return real(fd)
 with patch('hive.reducer.os.fsync',fsync):assert hb(h)
 assert len(calls)==1 and calls[0]['owner_before']=={} and calls[0]['audit_before']==[]
 original=hview(h);raw=jp.read_bytes();r=hfeed(hnew(jp),hist);assert r._plan_owner=={'a1:p':'i'} and r.journal_pending()==[];assert r.owner_rebinds[0]['actor']=='operator-original' and r.owner_rebinds[0]['reason']=='case-proof' and r.owner_rebinds[0]['replayed']
 hfeed(r,hist);r._replay_journal();assert len(r.owner_rebinds)==1 and r.owner_rebinds_total==1 and jp.read_bytes()==raw
 # Duplicate JSONL entries do not apply twice, but the redundant one remains pending forever.
 dp=T/'duplicate.jsonl';dp.write_bytes(raw+raw);d=hfeed(hnew(dp),hist);assert len(d.owner_rebinds)==1 and len(d.journal_pending())==1
 row.update(fsync_write_ahead=calls,original=original,restarted_and_double_event_replay=hview(r),duplicate_lines=hview(d),journal=json.loads(raw))
 # Actual unwritable path: all live state unchanged.
 h=hfeed(hnew(T),hist);before=copy.deepcopy(vars(h));assert not hb(h);assert vars(h)==before;row['unwritable_path_refused_without_mutation']=True

def journal_order(row):
 rows=[]
 for label,receipts in [('target_success_then_failure',[R('yes',i='i'),R('no',i='i',ok=False)]),('target_success_then_foreign_failure',[R('yes',i='i'),R('no',i='j',ok=False)]),('plan_success_then_failure',[R('yes'),R('no',ok=False)])]:
  jp=T/(label+'.jsonl');hist=[I('i','p'),I('j','p'),P()]+receipts+[P(i='i')];h=hfeed(hnew(jp),hist);assert hb(h);before=hview(h);assert hop(h)==['i','j'];restarted=hfeed(hnew(jp),hist);after=hview(restarted);assert hop(restarted)==['j']
  rows.append(dict(case=label,events=[e.to_dict() for e in hist],original=before,replayed=after))
 row.update(severity='High',defect_reproduced=True,cases=rows,interpretation='Journal lacks event position. Replay rebinds as soon as initial PLAN creates hold, before evidence that preceded the original operation. An intermediate success closes i permanently; later failure cannot reopen. Original audited rebind did not close i.')

def fsync_failure(row):
 jp=T/'fsync-fail.jsonl';hist=[I('i','p'),P(),R(i='i'),P(i='i')];h=hfeed(hnew(jp),hist);before=copy.deepcopy(vars(h))
 with patch('hive.reducer.os.fsync',side_effect=OSError('injected fsync failure')):assert not hb(h)
 assert vars(h)==before and len(jp.read_text().splitlines())==1
 restarted=hfeed(hnew(jp),hist);assert restarted._plan_owner=={'a1:p':'i'} and hop(restarted)==[]
 row.update(severity='Medium',defect_reproduced=True,refused_live=hview(h),journal_after_refusal=jp.read_text(),restart=hview(restarted),interpretation='Write/flush completed before fsync failed. API returns False and no live audit/owner change, but restart accepts the intact entry and applies the refused operation. This is an indeterminate commit, not guaranteed durable refusal.')

def corrupt(row):
 entry=json.loads((T/'good.jsonl').read_text());hist=[I('i','p'),I('j','p'),P(),R(i='j'),P(i='i')]
 jp=T/'corrupt.jsonl';jp.write_text('{broken}\n'+json.dumps({'op':'wrong'})+'\n'+json.dumps(entry)+'\n{"op":')
 h=hfeed(hnew(jp),hist);assert h._plan_owner=={'a1:p':'i'};row['skip_bad_complete_lines_and_tail']=hview(h)
 # A pre-existing unterminated tail poisons the next successful append.
 tp=T/'tail-append.jsonl';tp.write_text('{"op":');h=hfeed(hnew(tp),hist);assert hb(h);assert h._plan_owner=={'a1:p':'i'}
 restarted=hfeed(hnew(tp),hist);assert not restarted._plan_owner and restarted.quarantined_plans()==['a1:p']
 row.update(severity='Medium',defect_reproduced=True,tail_append_bytes=tp.read_text(),successful_before_restart=hview(h),after_restart=hview(restarted),interpretation='Loader skips truncated tail but append does not truncate or delimit it. A later successful, fsynced rebind is concatenated with the torn tail and discarded at next restart.')
 # Invalid UTF-8 crash recovery isn't line-isolated either.
 up=T/'invalid-utf8.jsonl';up.write_bytes(b'\xff\n'+json.dumps(entry).encode()+b'\n')
 try:HiveReducer(rebind_journal=str(up))
 except UnicodeDecodeError:row['invalid_utf8_raises']=True
 else:raise AssertionError('expected decoding failure')

def quiet_and_guidance(row):
 l,h=new()
 for e in [I('i','p'),P(),R(i='i'),P(i='i')]:feed(l,h,e)
 records=[]
 class C(logging.Handler):
  def emit(self,r):records.append(dict(level=r.levelname,message=r.getMessage()))
 c=C();log=logging.getLogger('hive.reducer');prev=log.level;log.setLevel(logging.INFO);log.addHandler(c)
 try:pv,hv=preview(l,h)
 finally:log.removeHandler(c);log.setLevel(prev)
 assert hv['would_close']==['i'] and not records
 l=rt(l);text=l.migration_diagnostics['recovery'];assert 'Reducer.quarantined_plans()' in text
 for reason in ['owner_unproven','ownerless_linked','ownerless_held']:assert reason in text
 row.update(preview=[pv,hv],hive_INFO_records=records,recovery=text)
 from hive.appliance import HiveAppliance
 default=HiveAppliance();configured=HiveAppliance(rebind_journal=str(T/'configured.jsonl'))
 assert default.reducer._journal_path is None and configured.reducer._journal_path==str(T/'configured.jsonl')
 row['appliance_wiring']=dict(default=None,explicit_path_forwarded=True)

def retained(row):
 # Exact old semantic controls; solely replace superseded recovery text assertion in extraction.
 raw=(E/'review7542.py').read_text();defs=raw[:raw.index('\nout={}\n')];env={'__file__':str(E/'review7542.py'),'__name__':'retained7542'};exec(compile(defs,str(E/'review7542.py'),'exec'),env)
 prior=env['prior'];qraw=(E/'review7519.py').read_text();qdefs=qraw[:qraw.index('\nout={}\n')];old="assert 'authoritative CURRENT quarantine is owner_unproven' in d['recovery']";new="assert 'authoritative CURRENT hold list is Reducer.quarantined_plans()' in d['recovery']";assert qdefs.count(old)==1;qdefs=qdefs.replace(old,new);qp={'__file__':str(E/'review7519.py'),'__name__':'retained7519_7638'};exec(compile(qdefs,str(E/'review7519.py'),'exec'),qp)
 row['adaptation']=dict(source='review7519.py',old=old,new=new,reason='Deliberately corrected diagnostic text; all semantic/lifecycle assertions unchanged',extracted_sha256=hashlib.sha256(qdefs.encode()).hexdigest())
 for name,fn in [('P3-ownerless',env['ownerless']),('owned_positive',env['owned_positive']),('legacy_300',qp['quarantine']),('owned_1440',prior['schedules']),('foreign_owned',prior['foreign']),('H-oracle_mutants',prior['health']),('health_boundaries',env['health_boundaries'])]:
  result={};fn(result);row[name]=result
 # Retain actual F7 mutant detection independent of text-adapted quarantine.
 src=inspect.getsource(a['retained']);tail=src[src.index(' # F7 mutants'):];scope=dict(a);scope['row']=row;exec(compile('if True:\n'+tail,'retained_F7','exec'),scope)

out={}
for name,fn in [('F_foreign_progress',foreign),('incidentless_evidence',incidentless),('F_hold_expiry',hold),('F_unregister_escape',unregister),('journal_controls',journal_good),('F_journal_order',journal_order),('F_journal_refused_fsync',fsync_failure),('F_journal_tail',corrupt),('quiet_guidance_wiring',quiet_and_guidance),('exact_plan_only_witness',a['witness']),('hold_144_schedules',a['schedules']),('refusals_pending',a['refusals_and_pending']),('retention_bounds',a['isolation_and_caps']),('late_link_warnings',a['warnings']),('retained_regressions',retained)]:
 r={}
 try:fn(r);r['passed']=True
 except Exception as ex:r.update(passed=False,error=repr(ex),traceback=traceback.format_exc())
 out[name]=r;print(name,r['passed'],r.get('error',''),flush=True)
(E/'review7638.json').write_text(json.dumps(out,indent=2,default=str)+'\n')
sys.exit(not all(r['passed'] for r in out.values()))
