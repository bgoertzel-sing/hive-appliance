"""Independent reset success, validation, every syscall boundary and live recovery witnesses."""
import os,json,sys,copy,logging,traceback
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
E=Path(__file__).resolve().parent
ns={'__file__':str(E/'focused7701.py'),'__name__':'defs'}
src=(E/'focused7701.py').read_text();exec(compile(src[:src.index('\nout={}\n')],str(E/'focused7701.py'),'exec'),ns)
for k in ['hnew','hfeed','history','hb','snapshot','anchor','records','Crash','fpath','hr','held']:globals()[k]=ns[k]
T=E/'reset-cases';T.mkdir(exist_ok=True)
def state(h):
 return dict(owner=copy.deepcopy(h._plan_owner),status=h.journal_status(),pending=len(h._journal_pending),applied=len(h._journal_applied),resets=copy.deepcopy(h.journal_resets))
def pair(p):return {str(q):q.read_bytes() for q in [p,anchor(p)] if q.exists()}
def disk(p):return {q.name:q.read_bytes().hex() for q in p.parent.glob(p.name+'*') if q.is_file()}
def restored(name,mode='healthy'):
 p=T/(name+'.jsonl');s=history();h=hfeed(hnew(p),s);assert hb(h);old=pair(p)
 p.write_bytes(p.read_bytes()+b'{torn')
 f=hfeed(hnew(p),s);held(f);assert f.clear_journal_fence('operator','discard p');held(hfeed(hnew(p),s))
 for q,b in old.items():Path(q).write_bytes(b)
 if mode=='markers':
  for suf in ['.fence','.fence.tmp']:Path(str(p)+suf).write_bytes(b'legacy marker')
 if mode=='corrupt':p.write_bytes(p.read_bytes()+b'{torn')
 if mode=='legacy':p.write_text('{"v":3,"op":"owner_rebind"}\n');anchor(p).unlink()
 if mode=='missing_anchor':anchor(p).unlink()
 if mode=='missing_journal':p.unlink()
 return p,s,hnew(p)

def success(row):
 rows=[]
 for mode in ['healthy','markers','corrupt','legacy','missing_anchor','missing_journal']:
  p,s,h=restored('success-'+mode,mode);old=pair(p);old_jid=h._journal_id
  info=h.reset_journal('review-operator','restore: reviewed discard')
  assert h.journal_status()['healthy'] and not h._journal_pending and info['journal_id']!=old_jid
  assert all(Path(info['archived'][k]).read_bytes()==v for k,v in old.items())
  assert [r['op'] for r in records(p)]==['journal_header','journal_reset']
  assert records(p)[1]['forced_fresh'] is True and records(p)[1]['actor']=='review-operator'
  assert h.clear_journal_fence('review-operator','must be no-op') is False
  # Caller cannot mutate stored audit through returned object.
  info['actor']='mutated';assert h.journal_resets[-1]['actor']=='review-operator'
  hfeed(h,s);held(h)
  rs=[hfeed(hnew(p),s) for _ in range(2)]
  for z in rs:held(z);assert z.journal_status()['healthy']
  assert hb(rs[-1]);reissued=[hfeed(hnew(p),s) for _ in range(2)]
  for z in reissued:assert z._plan_owner=={'a1:p':'i'}
  rows.append(dict(mode=mode,info=info,restarts=[state(z) for z in rs],reissued=[state(z) for z in reissued]))
 row['cases']=rows

def validation(row):
 rows=[]
 for which in ['after_one_event','after_full_replay','blank_actor','blank_reason','wrong_actor','wrong_reason','no_journal']:
  p,s,h=restored('validation-'+which)
  if which=='after_one_event':hfeed(h,s[:1])
  elif which=='after_full_replay':hfeed(h,s)
  elif which=='no_journal':h=hnew(None)
  before=disk(p);st=state(h);actor='op';reason='r'
  if which=='blank_actor':actor=' '
  if which=='blank_reason':reason=' '
  if which=='wrong_actor':actor=None
  if which=='wrong_reason':reason=12
  try:h.reset_journal(actor,reason)
  except (ValueError,RuntimeError) as ex:caught=type(ex).__name__
  else:raise AssertionError('not refused')
  assert disk(p)==before and state(h)==st
  rows.append(dict(case=which,error=caught,all_files_unchanged=True,state_unchanged=True))
 row['cases']=rows

def case(name,mode='healthy',target=None,side='before',error=Crash):
 p,s,h=restored(name,mode);old=pair(p);trace=[];triggered=False;caught=None
 real={k:getattr(os,k) for k in ['open','write','fsync','replace','unlink']}
 def wrap(kind):
  def call(*args,**kw):
   nonlocal triggered
   path=str(args[0]) if kind in ['open','replace','unlink'] else fpath(args[0])
   relevant=(path.startswith(str(p)) or path==str(p.parent)) and (kind!='open' or bool(args[1]&os.O_CREAT))
   if not relevant:return real[kind](*args,**kw)
   n=len(trace);trace.append(dict(index=n,op=kind,path=path,destination=str(args[1]) if kind=='replace' else None))
   if n==target and side=='before':triggered=True;raise error(name)
   r=real[kind](*args,**kw)
   if n==target and side=='after':triggered=True;raise error(name)
   return r
  return call
 with ExitStack() as stack:
  for k in real:stack.enter_context(patch.object(os,k,wrap(k)))
  try:h.reset_journal('review-operator','discard restored p')
  except (Crash,OSError) as ex:caught=type(ex).__name__
 if target is not None:assert triggered and caught
 before_feed=state(h);disk_after=disk(p)
 # Crash object intentionally not resumed; OSError is catchable and live object remains accessible.
 live=None
 if error==OSError and target is not None:
  hfeed(h,s);live=state(h)
 rs=[hfeed(hnew(p),s) for _ in range(2)]
 assert state(rs[0])['owner']==state(rs[1])['owner']
 for z in rs:
  if not z.journal_status()['healthy']:assert not z._plan_owner
 return dict(name=name,mode=mode,target=target,side=side,error=error.__name__,caught=caught,trace=trace,
             before_feed=before_feed,live_after_error_feed=live,restarts=[state(z) for z in rs],
             pair_unchanged=pair(p)==old,disk_after=disk_after)

def interruptions(row):
 rows=[];bases=[]
 for mode in ['healthy','markers']:
  base=case(mode+'-success',mode);bases.append(base)
  for t in base['trace']:
   for side in ['before','after']:
    for error in [Crash,OSError]:rows.append(case(mode+'-'+str(t['index'])+'-'+side+'-'+error.__name__,mode,t['index'],side,error))
 row.update(bases=bases,cases=rows,operations={b['mode']:len(b['trace']) for b in bases},injections=len(rows),
            healthy_old_replay=sum(r['restarts'][0]['owner']=={'a1:p':'i'} for r in rows),
            fenced_restart=sum(not r['restarts'][0]['status']['healthy'] for r in rows),
            healthy_held_restart=sum(r['restarts'][0]['status']['healthy'] and not r['restarts'][0]['owner'] for r in rows),
            live_replay_after_error=sum(bool(r['live_after_error_feed'] and r['live_after_error_feed']['owner']) for r in rows))
 assert row['healthy_old_replay']>0 and row['live_replay_after_error']>0

def live_witness(row):
 # Fail after the new journal has itself been durably installed.
 rows=[]
 for action in ['feed','verify_then_clear']:
  p,s,h=restored('live-'+action);real=hr.HiveReducer._replace_durably
  def replace(self,path,data):
   r=real(self,path,data)
   if path==str(p):raise OSError('after new journal durable, before reset memory commit')
   return r
  with patch.object(hr.HiveReducer,'_replace_durably',replace):
   try:h.reset_journal('op','discard p')
   except OSError:pass
   else:raise AssertionError('expected failure')
  clean_restart=hfeed(hnew(p),s);held(clean_restart)
  before=state(h);assert before['status']['healthy'] and before['pending']==1 and not before['resets']
  if action=='verify_then_clear':
   assert h.verify_journal() is False
   assert h.clear_journal_fence('op','recover failed reset')
  hfeed(h,s);assert h._plan_owner=={'a1:p':'i'}
  after=state(h);rs=[hfeed(hnew(p),s) for _ in range(2)]
  if action=='verify_then_clear':
   for z in rs:assert z._plan_owner=={'a1:p':'i'}
  else:
   for z in rs:held(z)
  rows.append(dict(action=action,new_disk_records=[r['op'] for r in records(p)],before=before,clean_restart=state(clean_restart),after=after,restarts=[state(z) for z in rs]))
 row['cases']=rows

out={}
for name,fn in [('successful_restore',success),('validation',validation),('interruptions',interruptions),('live_failure',live_witness)]:
 r={}
 try:fn(r);r['passed']=True
 except Exception as ex:r.update(passed=False,error=repr(ex),traceback=traceback.format_exc())
 out[name]=r;print(name,r['passed'],r.get('error',''),flush=True)
(E/'reset7718.json').write_text(json.dumps(out,indent=2,default=str)+'\n')
print(json.dumps({k:v for k,v in out.get('interruptions',{}).items() if k not in ['bases','cases']}))
sys.exit(not all(x['passed'] for x in out.values()))
