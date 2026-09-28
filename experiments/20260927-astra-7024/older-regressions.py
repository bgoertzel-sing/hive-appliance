"""Deterministic scoped review probes. PASS means observed assertion held, not product safety.
All filesystem effects confined to evidence. Includes bounded real ShellExecutor writes.
Copied from 6979; independently rerun by Astra 6986.
"""
import ast, dataclasses, json, logging, pathlib, sqlite3, sys, tempfile, threading, time, traceback
from unittest.mock import patch
E=pathlib.Path(__file__).resolve().parent
R=pathlib.Path(__import__('os').environ.get('HIVE_SRC', str(E.parent.parent)))
sys.path.insert(0,str(R))
from conversation.types import Thread, Message, Attachment, DownloadStatus
from conversation.attachments import AttachmentStore, SharedFolderManager, AttachmentDownloadManager
from hive.appliance import HiveAppliance
from hive.adapter import StubAgentAdapter, LocalAgentAdapter
from hive.types import AgentHealth, HiveActionResult
from controller.appliance import Appliance
from schemas.types import Event, EventKind, IncidentReport, Receipt
from reasoning.planner import SimplePlanner
from verifier.exit_code_verifier import ExitCodeVerifier
from recovery.upgrade import UpgradeController, UpgradeManifest, UpgradeStep
from recovery.checkpoint import CheckpointManager
RESULTS=[]
def case(name,fn):
    try:
        with tempfile.TemporaryDirectory(prefix=name+'-',dir=E/'tmp') as tmp:
            detail=fn(pathlib.Path(tmp))
        RESULTS.append({'name':name,'probe':'PASS','detail':detail})
    except BaseException as ex:
        RESULTS.append({'name':name,'probe':'HARNESS_OR_ASSERTION_FAILURE','error':repr(ex),'traceback':traceback.format_exc()})
    print(json.dumps(RESULTS[-1],default=str),flush=True)
def att(**kw):
    d=dict(message_id='parent',file_id='file',venue='tg',venue_id='room',created_at=1700000000.,file_name='x.bin'); d.update(kw); return Attachment(**d)
def health(h):
    s=h.reducer.state.agents['a']; return {'health':s.health.value,'count':s.open_incidents}
def incident(id='inc-A'):
    return Event(kind=EventKind.INCIDENT,payload={'id':id,'symptom':'disk_full','severity':'critical'})
def receipt(id='inc-A',verified=True):
    return Event(kind=EventKind.RECEIPT,payload={'incident_id':id,'verified':verified,'plan_id':'plan-A','attempt_id':'attempt-A'})
def hive():
    h=HiveAppliance(health_poll_interval=0); a=StubAgentAdapter('a'); h.register_agent(a); return h,a

def thread_checks(tmp):
    from conversation.threading import Thread as Alias, ThreadAssembler
    assert Alias is Thread
    t=Thread(); assert t.last_activity==0.0
    empty={'last_activity':t.last_activity,'serialized':t.to_dict()}
    for n in (300,100,500,200): t.add_message(Message(timestamp=n,sender_id='u'))
    assert t.last_activity==500 and t.started_at==100
    t.ended_at=50; assert t.last_activity==500
    t.messages.append(Message(timestamp=999)); assert t.last_activity==999
    t.last_activity=1200; assert t.ended_at==1200 and t.last_activity==999
    d=t.to_dict(); assert d['last_activity']==999 and d['ended_at']==1200 and d['message_count']==5
    t.last_activity=None; assert t.last_activity==999 and t.duration==0
    z=Thread(started_at=100,ended_at=0); assert z.last_activity==100
    t.sort_messages(); assert t.ended_at==999 and t.duration_seconds==899
    msgs=[Message(venue='tg',venue_id='r',venue_message_id=str(n),timestamp=n,sender_id='u',content='hello') for n in (300,100,200)]
    assembled=ThreadAssembler(min_thread_messages=1).assemble(msgs)
    assert sum(x.message_count for x in assembled)==3
    assert max(x.last_activity for x in assembled)==300
    # Canonical class does not accept old alias constructor keyword or its enriched serialized dict.
    errors=[]
    for kwargs in ({'last_activity':9},d):
        try: Thread(**kwargs)
        except TypeError as ex: errors.append(str(ex))
    assert len(errors)==2
    return {'getter_cases':'pass','empty':empty,'setter_then_serialized':d,'alias_identity':True,'constructor_compatibility_errors':errors,'note':'setter changes ended_at but nonempty getter remains message maximum; no Thread.from_dict contract exists'}

def nonhealthy(tmp):
    out={}
    for polled in (AgentHealth.HEALTHY,AgentHealth.DEGRADED,AgentHealth.FAILED):
        h,a=hive(); a.set_health(polled,0); a.inject_event(incident()); result=h.tick(); out[polled.value]=health(h)
        assert not result['executed_results'] and not result['errors']
    assert out['healthy']=={'health':'failed','count':1}
    assert out['degraded']['count']==out['failed']['count']==0
    return out

def resolution(tmp):
    h,a=hive(); a.inject_event(incident()); h.tick(); first=health(h)
    # Suppress next health poll to observe receipt effect before merge.
    h._health_poll_interval=10**12
    a.inject_event(receipt('unrelated')); h.tick(); unrelated=health(h)
    assert unrelated=={'health':'healthy','count':0}
    h._health_poll_interval=0; h.tick(); poisoned=health(h)
    assert poisoned==first
    # Two active incidents; repeat same receipt resolves two counts.
    h2,a2=hive(); a2.add_events([incident('A'),incident('B')]); h2.tick()
    h2._health_poll_interval=10**12
    rec=receipt('A'); a2.add_events([rec,rec]); h2.tick(); duplicate=health(h2)
    assert duplicate['count']==0
    return {'after_incident':first,'unrelated_receipt':unrelated,'next_healthy_poll':poisoned,'replayed_receipt_two_incidents':duplicate,'event_path':'StubAgentAdapter.add_events/inject_event -> HiveAppliance.tick -> HiveEventBus -> HiveReducer.reduce'}

def real_resolution(tmp):
    app=Appliance(str(tmp/'app.db')); h=HiveAppliance(health_poll_interval=0); h.register_agent(LocalAgentAdapter('a',app))
    try:
        from schemas.types import Plan
        inc=IncidentReport(id='real-incident',component='disk',symptom='disk_full')
        plan=Plan(incident_id=inc.id,steps=[{'verb':'inspect','command':'true'}]); inc.plan_id=plan.id
        app.record_incident(inc); app.record_plan(plan)
        h.tick(); before=health(h)
        assert len(app.open_incidents())==1
        # Persisted incident links this actual plan; public receipt resolves it locally.
        app.record_receipt(Receipt(plan_id=plan.id,step_index=0,verified=True,target='disk'))
        h.tick(); after=health(h); local=LocalAgentAdapter('a',app).health_summary()
        assert len(app.open_incidents())==0 and local.open_incidents==0 and after['count']>0
        return {'before':before,'agent_local_incidents_after':len(app.open_incidents()),'agent_local_after':{'health':local.health.value,'count':local.open_incidents},'hive_after':after}
    finally: app.close()

class Writer:
    def __init__(self,data=b'new'): self.data=data
    def get_file_info(self,_): return {'size':len(self.data)}
    def download(self,_,destination,max_bytes=0): pathlib.Path(destination).write_bytes(self.data); return True
class BlockingWriter(Writer):
    def __init__(self): super().__init__(b'old'); self.enter=threading.Event(); self.release=threading.Event()
    def download(self,_,destination,max_bytes=0):
        pathlib.Path(destination).write_bytes(self.data); self.enter.set()
        if not self.release.wait(5): raise RuntimeError('probe release timed out')
        return True

def worker_normal(tmp):
    s=AttachmentStore(str(tmp/'db')); f=SharedFolderManager(str(tmp/'root')); m=AttachmentDownloadManager(s,f,Writer()); item=att(); assert m.enqueue(item)
    m.start(.01); worker=m._worker; m.start(.01); assert m._worker is worker
    end=time.monotonic()+3
    while s.get(item.id).download_status!='completed' and time.monotonic()<end: time.sleep(.01)
    m.stop(2); assert worker is not None and not worker.is_alive() and m._worker is None
    assert s.get(item.id).download_status=='completed'
    m.stop(); m.start(.01); second=m._worker; m.stop(2); assert not second.is_alive()
    s.close(); return {'completed':True,'saved_worker_alive_after_stop':worker.is_alive(),'restart_saved_worker_alive':second.is_alive()}

def worker_timeout(tmp):
    s=AttachmentStore(str(tmp/'db')); b=BlockingWriter(); m=AttachmentDownloadManager(s,SharedFolderManager(str(tmp/'root')),b); m.enqueue(att())
    old=None; new=None
    try:
        m.start(.01); old=m._worker; assert b.enter.wait(2)
        m.stop(.01); forgotten=m._worker is None and old.is_alive(); assert forgotten
        m.start(.01); new=m._worker; assert new is not old and new.is_alive() and old.is_alive()
        return {'stop_returned_with_old_alive':forgotten,'restart_creates_two_workers':True}
    finally:
        b.release.set(); m.stop(2)
        if old: old.join(2)
        if new: new.join(2)
        assert not old.is_alive() and not new.is_alive(); s.close()

def statuses(tmp):
    s=AttachmentStore(str(tmp/'db'))
    assert s.append([att(download_status='INVALID')])==0
    m=AttachmentDownloadManager(s,SharedFolderManager(str(tmp/'root')),Writer()); assert not m.enqueue(att(download_status='INVALID'))
    s.append([att()]); rejected=False
    try: s.update_status(att().id,'INVALID')
    except ValueError: rejected=True
    assert rejected
    claim=s.claim_pending(1)[0]; accepted=s.finish_attempt(claim.id,claim.attempt_id,'INVALID')
    assert accepted and s.get(claim.id).download_status=='INVALID'
    s.close(); return {'append_rejects':True,'enqueue_rejects':True,'update_status_rejects':True,'finish_attempt_accepts_invalid':accepted}

def paths(tmp):
    out={}
    for thumbnail in (False,True):
        base=tmp/('thumb' if thumbnail else 'main'); root=base/'root'; outside=base/'outside'; root.mkdir(parents=True); outside.mkdir(); (root/'tg').symlink_to(outside,target_is_directory=True)
        f=SharedFolderManager(str(root)); rejected=False
        try: (f.resolve_thumbnail_path if thumbnail else f.resolve_path)(att())
        except ValueError: rejected=True
        created=[str(p.relative_to(outside)) for p in outside.rglob('*')]
        assert rejected and created
        out['thumbnail' if thumbnail else 'main']={'rejected':rejected,'outside_directories_created':created}
    # A public metadata write bypasses manager enqueue containment and is trusted by process_pending.
    s=AttachmentStore(str(tmp/'db')); outside=tmp/'external.bin'; m=AttachmentDownloadManager(s,SharedFolderManager(str(tmp/'safe')),Writer())
    assert not m.enqueue(att(local_path=str(outside)))
    assert s.append([att(local_path=str(outside))])==1
    assert m.process_pending()[0]['success'] and outside.read_bytes()==b'new'
    s.delete(att().id); assert not outside.exists(); s.close()
    out['direct_store_path']={'manager_enqueue_rejects':True,'store_append_then_process_writes_external':True,'delete_unlinks_external':True}
    return out

def stale_publish(tmp):
    s=AttachmentStore(str(tmp/'db')); s2=AttachmentStore(str(tmp/'db')); f=SharedFolderManager(str(tmp/'root'))
    m=AttachmentDownloadManager(s,f,Writer(b'old')); item=att(); m.enqueue(item)
    old=s.claim_pending(1,lease_seconds=-1)[0]; newer=s2.claim_pending(1)[0]
    winner=AttachmentDownloadManager(s2,f,Writer(b'new')); win=winner._download_one(newer)
    path=pathlib.Path(s2.get(item.id).local_path); assert win['success'] and path.read_bytes()==b'new'
    lose=m._download_one(old)
    row=s2.get(item.id); assert not lose['success'] and row.download_status=='completed' and not path.exists()
    s.close(); s2.close(); return {'winner':win,'stale':lose,'db_status':row.download_status,'winner_file_exists':path.exists(),'note':'real claim/finish APIs; direct _download_one preserves deterministic schedule after reclaim'}

def active_partial(tmp):
    s=AttachmentStore(str(tmp/'db')); f=SharedFolderManager(str(tmp/'root')); m=AttachmentDownloadManager(s,f,Writer()); item=att(); m.enqueue(item); active=s.claim_pending(1)[0]
    final=pathlib.Path(active.local_path); part=final.with_name('.'+final.name+'.'+active.attempt_id+'.part'); part.write_bytes(b'active')
    result=m.reconcile(); assert result['orphan_partials']==1 and not part.exists() and s.get(item.id).download_status=='downloading'
    s.close(); return {'reconcile':result,'unexpired_active_partial_deleted':True}

class CountingExecutor:
    def __init__(self,code=0,mutate=None): self.calls=0; self.code=code; self.mutate=mutate
    def execute_step(self,step,plan,index):
        self.calls+=1
        if self.mutate: self.mutate()
        return Receipt(plan_id=plan.id if plan else '',step_index=index,exit_code=self.code)

def repair_checkpoint(tmp):
    app=Appliance(str(tmp/'db')); app.set_planner(SimplePlanner()); ex=CountingExecutor(); app.set_executor(ex); app.set_verifier(ExitCodeVerifier())
    inc=IncidentReport(component=str(tmp/'not-executed'),symptom='file_missing')
    try:
        with patch.object(app._checkpoint_mgr,'create',side_effect=OSError('checkpoint unavailable')):
            receipts=app.repair(inc)
        assert ex.calls==2 and inc.resolved and len(receipts)==2
        return {'executor_calls_despite_checkpoint_failure':ex.calls,'incident_resolved':inc.resolved}
    finally: app.close()

def repair_rollback(tmp):
    app=Appliance(str(tmp/'db')); app.set_planner(SimplePlanner()); app.set_executor(CountingExecutor(1)); app.set_verifier(ExitCodeVerifier())
    try:
        with patch.object(app._checkpoint_mgr,'load',side_effect=OSError('rollback unavailable')) as load:
            receipts=app.repair(IncidentReport(component=str(tmp/'x'),symptom='file_missing'))
        assert load.call_count==1 and len(receipts)==1 and not receipts[0].verified
        return {'rollback_load_calls':load.call_count,'returned_receipts':len(receipts),'rollback_exception_reported':False}
    finally: app.close()

def upgrade(tmp):
    app=Appliance(str(tmp/'db')); before=json.loads(json.dumps(app.state_snapshot())); mutated={'done':False}
    def mutate():
        mutated['done']=True
        app.reducer.reduce(Event(kind=EventKind.OBSERVATION,subject='upgrade-probe',payload={'value':'changed'}))
    ex=CountingExecutor(1,mutate); app.set_executor(ex); app.set_verifier(ExitCodeVerifier())
    manifest=UpgradeManifest(id='unsafe',steps=[UpgradeStep(verb='noop',rollback_command='NOT EXECUTED')])
    try:
        with patch.object(app._checkpoint_mgr,'load',wraps=app._checkpoint_mgr.load) as load:
            result=app.upgrade(manifest)
        assert not result.success and result.rolled_back and load.call_count==0 and app.state_snapshot()!=before
        checkpoint_gate=False
        with patch.object(app._checkpoint_mgr,'create',side_effect=OSError('no checkpoint')):
            try: app.upgrade(manifest)
            except OSError: checkpoint_gate=True
        assert checkpoint_gate and ex.calls==1
        return {'result':result.to_dict(),'checkpoint_load_calls':load.call_count,'state_still_changed':True,'upgrade_checkpoint_failure_blocks_executor':checkpoint_gate}
    finally: app.close()

def sqlite_and_static(tmp):
    c=sqlite3.connect(':memory:'); c.execute('create table x(a)'); c.execute('insert into x values(1)'); before=c.execute('select changes()').fetchone()[0]; c.commit(); after=c.execute('select changes()').fetchone()[0]; assert before==after==1
    silent=[]
    for p in R.rglob('*.py'):
        if 'tests' in p.parts: continue
        tree=ast.parse(p.read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.ExceptHandler) and len(node.body)==1 and isinstance(node.body[0],ast.Pass):
                silent.append({'path':str(p.relative_to(R)),'line':node.lineno,'exception':ast.unparse(node.type) if node.type else 'bare'})
    assert [f.name for f in dataclasses.fields(HiveActionResult)].count('output')==1
    assert (R/'pyproject.toml').read_text().count('"recovery*"')==1
    return {'sqlite_changes_before_commit':before,'after_commit':after,'silent_handlers':silent,'duplicate_output_recovery_fixed':True,'build_lib_in_review_checkout':(R/'build/lib').exists()}


# Current-commit adaptations: same public setup and adversarial schedules, new assertions.
def fixed_a1(tmp):
    s=AttachmentStore(str(tmp/'db')); s2=AttachmentStore(str(tmp/'db')); f=SharedFolderManager(str(tmp/'root'))
    old_writer=BlockingWriter(); m=AttachmentDownloadManager(s,f,old_writer); item=att(); assert m.enqueue(item)
    old=s.claim_pending(1,lease_seconds=-1)[0]; result={}
    t=threading.Thread(target=lambda: result.update(m._download_one(old))); t.start()
    try:
        assert old_writer.enter.wait(2)
        new=s2.claim_pending(1)[0]; assert old.attempt_id!=new.attempt_id
        win=AttachmentDownloadManager(s2,f,Writer(b'new'))._download_one(new)
        path=pathlib.Path(s2.get(item.id).local_path); assert win['success'] and path.read_bytes()==b'new'
        old_writer.release.set(); t.join(3); assert not t.is_alive()
        row=s2.get(item.id)
        assert not result['success'] and row.download_status=='completed' and pathlib.Path(row.local_path)==path and path.read_bytes()==b'new'
        return {'winner':win,'stale':result,'winner_bytes':'new','winner_survives':True,'schedule':'expired lease; A blocked mid-download while independent SQLite store claims and completes B; then A resumes'}
    finally:
        old_writer.release.set(); t.join(3); s.close(); s2.close()

def fixed_a2(tmp):
    s=AttachmentStore(str(tmp/'db')); f=SharedFolderManager(str(tmp/'root')); m=AttachmentDownloadManager(s,f,Writer()); item=att(); m.enqueue(item); active=s.claim_pending(1)[0]
    final=f.attempt_artifact_path(f.resolve_path(active),active.attempt_id)
    part=final.with_name('.'+final.name+'.'+active.attempt_id+'.part'); part.write_bytes(b'active')
    orphan=part.with_name('.orphan.dead.part'); orphan.write_bytes(b'orphan')
    r=m.reconcile(); assert part.read_bytes()==b'active' and not orphan.exists() and r['active_partials_kept']==1 and s.get(item.id).download_status=='downloading'
    s.close(); return r

def fixed_h1(tmp):
    out={}
    for polled in AgentHealth:
        h,a=hive(); a.set_health(polled,0); a.inject_event(incident()); r=h.tick(); out[polled.value]=health(h)
        assert out[polled.value]['count']==1 and not r['errors']
    return out

def fixed_h2_original(tmp):
    h,a=hive(); a.inject_event(incident()); h.tick(); first=health(h); h._health_poll_interval=10**12
    a.inject_event(receipt('unrelated')); h.tick(); unrelated=health(h); assert unrelated==first
    h2,a2=hive(); a2.add_events([incident('A'),incident('B')]); h2.tick(); h2._health_poll_interval=10**12
    rec=receipt('A'); a2.add_events([rec,rec]); h2.tick(); assert health(h2)['count']==1
    a2.inject_event(receipt('B')); h2.tick(); h2._health_poll_interval=0; h2.tick(); assert health(h2)['count']==0
    return {'unrelated_receipt':unrelated,'replay_leaves_second_incident_open':True,'resolved_history_no_longer_poisons_poll':True}

def h2_residual(tmp):
    h,a=hive(); a.inject_event(incident()); h.tick(); h._health_poll_interval=10**12
    a.inject_event(Event(kind=EventKind.RECEIPT,payload={'id':'unrelated-untargeted','verified':True})); h.tick()
    untargeted=health(h); assert untargeted['count']==0
    # Real plan has two steps: the first receipt is not completion.
    from schemas.types import Plan
    app=Appliance(str(tmp/'db')); h=HiveAppliance(health_poll_interval=0); h.register_agent(LocalAgentAdapter('a',app))
    try:
        inc=IncidentReport(id='composite',component='disk',symptom='disk_full')
        p=Plan(incident_id=inc.id,steps=[{'verb':'inspect','command':'true'},{'verb':'inspect','command':'true'}]); inc.plan_id=p.id
        app.record_incident(inc); app.record_plan(p); h.tick(); h._health_poll_interval=10**12
        app.record_receipt(Receipt(plan_id=p.id,step_index=0,verified=True)); h.tick()
        composite={'local_open':len(app.open_incidents()),'hive':health(h)}
        assert composite['local_open']==1 and composite['hive']['count']==0
        h._health_poll_interval=0; h.tick(); composite['after_poll']=health(h)
        return {'untargeted_verified_receipt_clears_incident':untargeted,'premature_composite_resolution':composite}
    finally: app.close()

def fixed_local_resolution(tmp):
    from schemas.types import Plan
    app=Appliance(str(tmp/'db')); h=HiveAppliance(health_poll_interval=0); h.register_agent(LocalAgentAdapter('a',app))
    try:
        inc=IncidentReport(id='real',component='disk',symptom='disk_full'); p=Plan(incident_id=inc.id,steps=[{'verb':'inspect','command':'true'}]); inc.plan_id=p.id
        app.record_incident(inc); app.record_plan(p); h.tick()
        app.record_receipt(Receipt(plan_id=p.id,step_index=0,verified=True)); h.tick(); h.tick()
        assert len(app.open_incidents())==0 and health(h)['count']==0
        return health(h)
    finally: app.close()

def fixed_u1(tmp):
    out={}
    for mode in ('create_raises','readback_missing','rollback_missing','rollback_raises','restore_ok'):
        base=tmp/mode; base.mkdir(); app=Appliance(str(base/'db')); app.set_planner(SimplePlanner()); app.set_verifier(ExitCodeVerifier())
        inc=IncidentReport(component='probe',symptom='file_missing'); app.record_incident(inc)
        before=json.loads(json.dumps(app.state_snapshot())); ex=CountingExecutor(1,lambda: app.reducer.state.update({'changed':{'x':1}})); app.set_executor(ex)
        real_load=app._checkpoint_mgr.load; calls=[0]
        def load(cid):
            calls[0]+=1
            if mode=='readback_missing': return None
            if calls[0]>1 and mode=='rollback_missing': return None
            if calls[0]>1 and mode=='rollback_raises': raise OSError('rollback unavailable')
            return real_load(cid)
        try:
            with patch.object(app._checkpoint_mgr,'load',side_effect=load):
                if mode=='create_raises':
                    with patch.object(app._checkpoint_mgr,'create',side_effect=OSError('checkpoint unavailable')): rs=app.repair(inc)
                else: rs=app.repair(inc)
            outcome=app.repair_outcomes[inc.id]; records=app.store.query(kind=EventKind.RECOVERY)
            assert records and records[-1].payload['outcome']==outcome
            if mode in ('create_raises','readback_missing'): assert ex.calls==0 and rs==[] and outcome=='blocked_no_checkpoint' and not inc.resolved
            elif mode.startswith('rollback_'): assert ex.calls==1 and outcome=='rollback_failed' and records[-1].payload['error']
            else: assert ex.calls==1 and outcome=='rolled_back' and app.state_snapshot()==before
            out[mode]={'executor_calls':ex.calls,'outcome':outcome,'durable_event':records[-1].payload}
        finally: app.close()
    return out

def fixed_u2(tmp):
    app=Appliance(str(tmp/'db')); app.record_incident(IncidentReport(component='disk',symptom='disk_full')); before=json.loads(json.dumps(app.state_snapshot()))
    ex=CountingExecutor(1,lambda: app.reducer.state.update({'changed':{'x':1}})); app.set_executor(ex); app.set_verifier(ExitCodeVerifier()); manifest=UpgradeManifest(id='probe',steps=[UpgradeStep(verb='inspect',command='false',rollback_command='NOT EXECUTED')])
    try:
        with patch.object(app._checkpoint_mgr,'load',wraps=app._checkpoint_mgr.load) as load: result=app.upgrade(manifest)
        assert result.rolled_back and load.call_count==1 and app.state_snapshot()==before
        with patch.object(app._checkpoint_mgr,'load',return_value=None): missing=app.upgrade(manifest)
        assert not missing.rolled_back and missing.rollback_error
        return {'restoration':result.to_dict(),'state_equal_before':True,'missing_checkpoint':missing.to_dict()}
    finally: app.close()

def u2_external(tmp):
    from executor.shell_executor import ShellExecutor
    import shlex
    app=Appliance(str(tmp/'db')); app.set_executor(ShellExecutor()); app.set_verifier(ExitCodeVerifier()); f=tmp/'effect.txt'; f.write_text('before')
    try:
        manifest=UpgradeManifest(id='external',steps=[UpgradeStep(verb='inspect',command='printf changed > '+shlex.quote(str(f))+'; false',rollback_command='printf before > '+shlex.quote(str(f)))])
        r=app.upgrade(manifest)
        assert not r.success and r.rolled_back and f.read_text()=='changed'
        return {'result':r.to_dict(),'file_after_failed_upgrade':f.read_text(),'rollback_command_not_executed':True,'scope':'bounded temp-file ShellExecutor action only'}
    finally: app.close()

def fixed_u3(tmp):
    from schemas.types import Plan
    app=Appliance(str(tmp/'db')); inc=IncidentReport(component='disk',symptom='disk_full'); p=Plan(incident_id=inc.id,steps=[{'verb':'inspect','command':'true'},{'verb':'inspect','command':'true'}]); inc.plan_id=p.id
    try:
        app.record_incident(inc); app.record_plan(p); app.record_receipt(Receipt(plan_id=p.id,step_index=0,verified=True)); before=json.loads(json.dumps(app.state_snapshot())); ck=app.checkpoint()
        app.reducer.incidents.clear(); app.reducer.state.clear(); assert app.restore(ck.id) and app.state_snapshot()==before and len(app.open_incidents())==1
        app.record_incident(inc); assert len(app.reducer.incidents)==1
        app.record_receipt(Receipt(plan_id=p.id,step_index=1,verified=True)); assert len(app.open_incidents())==0
        return {'roundtrip_equal':True,'open_incidents_after_restore':1,'incident_replay_dedup':True,'composite_progress_preserved':True}
    finally: app.close()

def fixed_l1(tmp):
    s=AttachmentStore(str(tmp/'db')); b=BlockingWriter(); m=AttachmentDownloadManager(s,SharedFolderManager(str(tmp/'root')),b); m.enqueue(att()); old=None
    try:
        m.start(.01); old=m._worker; assert b.enter.wait(2); stopped=m.stop(.01); assert stopped is False and m._worker is old and old.is_alive()
        try: m.start(.01)
        except RuntimeError: rejected=True
        else: rejected=False
        assert rejected and m._worker is old and m._stop_event.is_set()
        b.release.set(); assert m.stop(2); m.start(.01); new=m._worker; assert new is not old; assert m.stop(2)
        return {'stop_returned':stopped,'live_reference_preserved':True,'restart_rejected_until_exit':rejected,'later_restart_ok':True}
    finally:
        b.release.set(); m.stop(2)
        if old: old.join(2)
        s.close()

def fixed_s1(tmp):
    s=AttachmentStore(str(tmp/'db')); s.append([att()]); a=s.claim_pending(1)[0]; denied=[]
    try:
        for status in ('INVALID','pending','downloading'):
            try: s.finish_attempt(a.id,a.attempt_id,status)
            except ValueError: denied.append(status)
        assert len(denied)==3 and s.get(a.id).download_status=='downloading'
        try: s._conn.execute("UPDATE attachments SET download_status='INVALID'")
        except sqlite3.IntegrityError: db_reject=True; s._conn.rollback()
        else: db_reject=False
        assert db_reject and s.finish_attempt(a.id,a.attempt_id,'completed')
        return {'finish_rejected':denied,'DB_rejected':db_reject,'valid_finish':True}
    finally: s.close()

def fixed_p1(tmp):
    out={}
    for thumbnail in (False,True):
        base=tmp/str(thumbnail); root=base/'root'; outside=base/'outside'; root.mkdir(parents=True); outside.mkdir(); (root/'tg').symlink_to(outside,target_is_directory=True); f=SharedFolderManager(str(root))
        try: (f.resolve_thumbnail_path if thumbnail else f.resolve_path)(att())
        except ValueError: rejected=True
        else: rejected=False
        assert rejected and not list(outside.rglob('*')); out[str(thumbnail)]={'rejected':True,'external_mkdir':False}
    return out

def fixed_p2(tmp):
    out={}
    for mode in ('append','update','delete_unknown_root','delete_configured_root'):
        base=tmp/mode; base.mkdir(); outside=base/'external'; outside.write_bytes(b'untouched'); f=SharedFolderManager(str(base/'root')); s=AttachmentStore(str(base/'db'),attachments_root=str(f.base_dir) if mode=='delete_configured_root' else None); m=AttachmentDownloadManager(s,f,Writer()); a=att(local_path=str(outside))
        try:
            if mode=='update': a.local_path=''; assert m.enqueue(a); assert s.update_status(a.id,'pending',local_path=str(outside))
            else: assert s.append([a])==1
            metadata_external=s.get(a.id).local_path==str(outside)
            if mode in ('append','update'):
                r=m.process_pending(); assert r[0]['success']; row=s.get(a.id); assert f.contains(row.local_path) and pathlib.Path(row.local_path).read_bytes()==b'new'
            assert s.delete(a.id) and outside.read_bytes()==b'untouched'
            out[mode]={'metadata_external_accepted':metadata_external,'external_file_unchanged':True}
        finally: s.close()
    return out

def cli_fixed(tmp):
    import cli, contextlib, io
    from types import SimpleNamespace
    out={}
    for shape in ('legacy','canonical'):
        data={'name':'probe','steps':[{'name':'inspect','command':'true'}]} if shape=='legacy' else UpgradeManifest(id='probe',steps=[UpgradeStep(verb='inspect',command='true')]).to_dict()
        mf=tmp/(shape+'.json'); mf.write_text(json.dumps(data)); buf=io.StringIO()
        with contextlib.redirect_stdout(buf): cli.cmd_upgrade(SimpleNamespace(recovery_ready=True,manifest=str(mf),store=str(tmp/(shape+'.db'))))
        assert 'SUCCESS' in buf.getvalue() and 'Steps: 1/1' in buf.getvalue(); out[shape]=buf.getvalue()
    try: UpgradeStep(name='legacy-direct')
    except TypeError as e: out['direct_constructor_still_unsupported']=str(e)
    else: raise AssertionError('API unexpectedly changed')
    return out



# ===================== Opus 5.5 review 6979 adaptations (1ab8e5f) =====================
from controller.reducer import Reducer as LocalReducer  # noqa: E402  (checked below)
from hive.reducer import HiveReducer
from hive.types import HiveEvent
from schemas.types import Plan
import shlex, os, io, contextlib

def hev(agent, kind, payload):
    return HiveEvent(source_agent=agent, original_event=Event(kind=kind, source='t', subject='svc', payload=payload))
def hr():
    r=HiveReducer(); r.register_agent('a'); return r
def hopen(r, agent='a'):
    return [i['incident_id'] for i in r._open_agent_incidents(agent)]
def INC(id, **kw):
    d={'id':id,'symptom':'s','severity':'warn'}; d.update(kw); return d
def PLAN(pid, n, inc=''):
    return {'id':pid,'incident_id':inc,'steps':[{'verb':'v%d'%k} for k in range(n)]}
def RC(rid, pid='', idx=None, verified=True, inc=''):
    d={'id':rid,'verified':verified}
    if pid: d['plan_id']=pid
    if idx is not None: d['step_index']=idx
    if inc: d['incident_id']=inc
    return d

# ---- H2: prior residual probe with inverted (now-desired) assertions
def h2_prior_residual_now(tmp):
    h,a=hive(); a.inject_event(incident()); h.tick(); h._health_poll_interval=10**12
    a.inject_event(Event(kind=EventKind.RECEIPT,payload={'id':'unrelated-untargeted','verified':True})); h.tick()
    untargeted=health(h); assert untargeted=={'health':'failed','count':1}, untargeted
    app=Appliance(str(tmp/'db')); h=HiveAppliance(health_poll_interval=0); h.register_agent(LocalAgentAdapter('a',app))
    try:
        inc=IncidentReport(id='composite',component='disk',symptom='disk_full')
        p=Plan(incident_id=inc.id,steps=[{'verb':'inspect','command':'true'},{'verb':'inspect','command':'true'}]); inc.plan_id=p.id
        app.record_incident(inc); app.record_plan(p); h.tick(); h._health_poll_interval=10**12
        app.record_receipt(Receipt(plan_id=p.id,step_index=0,verified=True)); h.tick()
        step0={'local_open':len(app.open_incidents()),'hive':health(h)}
        assert step0['local_open']==1 and step0['hive']['count']==1, step0
        app.record_receipt(Receipt(plan_id=p.id,step_index=1,verified=True)); h.tick()
        step1={'local_open':len(app.open_incidents()),'hive':health(h)}
        assert step1['local_open']==0 and step1['hive']['count']==0, step1
        h._health_poll_interval=0; h.tick(); after_poll=health(h); assert after_poll['count']==0
        return {'untargeted_verified_receipt':untargeted,'after_step0':step0,'after_step1':step1,'after_poll':after_poll}
    finally: app.close()

def h2_edges(tmp):
    out={}
    # a. out-of-order step receipts
    r=hr(); r.reduce(hev('a',EventKind.INCIDENT,INC('i'))); r.reduce(hev('a',EventKind.PLAN,PLAN('p',3,'i')))
    r.reduce(hev('a',EventKind.RECEIPT,RC('r2','p',2))); r.reduce(hev('a',EventKind.RECEIPT,RC('r0','p',0)))
    mid=hopen(r); r.reduce(hev('a',EventKind.RECEIPT,RC('r1','p',1)))
    out['a_out_of_order']={'open_after_2_of_3':mid,'open_after_3_of_3':hopen(r)}
    assert mid==['i'] and hopen(r)==[]
    # b. duplicate step index under distinct receipt ids + exact replay + out-of-range index
    r=hr(); r.reduce(hev('a',EventKind.INCIDENT,INC('i'))); r.reduce(hev('a',EventKind.PLAN,PLAN('p',2,'i')))
    for e in (RC('r0','p',0),RC('r0','p',0),RC('r0b','p',0),RC('rX','p',5),RC('rN','p',-1)): r.reduce(hev('a',EventKind.RECEIPT,e))
    out['b_duplicate_index_hive_open']=hopen(r); assert hopen(r)==['i']
    # b2. same schedule on the LOCAL controller reducer via a real Appliance (divergence check)
    app=Appliance(str(tmp/'dup.db'))
    try:
        inc=IncidentReport(id='dup',component='disk',symptom='disk_full'); p=Plan(incident_id=inc.id,steps=[{'verb':'inspect','command':'true'}]*2); inc.plan_id=p.id
        app.record_incident(inc); app.record_plan(p)
        app.record_receipt(Receipt(plan_id=p.id,step_index=0,verified=True)); app.record_receipt(Receipt(plan_id=p.id,step_index=0,verified=True))
        out['b2_local_controller_open_after_two_step0_receipts']=len(app.open_incidents())
    finally: app.close()
    # c. receipts for an unknown plan
    r=hr(); r.reduce(hev('a',EventKind.INCIDENT,INC('i')))
    r.reduce(hev('a',EventKind.RECEIPT,RC('c1','ghost',0))); c_plan_only=hopen(r)
    r.reduce(hev('a',EventKind.RECEIPT,RC('c2','ghost',0,inc='i'))); c_inc_plus_ghost=hopen(r)
    out['c_unknown_plan']={'plan_only_unlinked_incident_open':c_plan_only,'incident_id_plus_unknown_plan_open':c_inc_plus_ghost}
    assert c_plan_only==['i']
    r=hr(); r.reduce(hev('a',EventKind.INCIDENT,INC('i'))); r.reduce(hev('a',EventKind.PLAN,PLAN('p',2,'i')))
    r.reduce(hev('a',EventKind.RECEIPT,RC('c3','ghost',0,inc='i'))); r.reduce(hev('a',EventKind.RECEIPT,RC('c4','ghost',1,inc='i')))
    out['c_unknown_plan_vs_linked_composite_open']=hopen(r); assert hopen(r)==['i']
    # d. PLAN arriving after its receipts
    #  d1: incident already linked to p (IncidentReport.plan_id set before record_incident, as in prior probes)
    r=hr(); r.reduce(hev('a',EventKind.INCIDENT,INC('i',plan_id='p')))
    r.reduce(hev('a',EventKind.RECEIPT,RC('d0','p',0))); d1_after_step0=hopen(r)
    r.reduce(hev('a',EventKind.PLAN,PLAN('p',2,'i'))); d1_after_plan=hopen(r)
    out['d1_linked_incident_receipt_before_plan']={'open_after_step0_of_2':d1_after_step0,'open_after_late_plan':d1_after_plan}
    #  d2: incident unlinked (the Appliance.repair() order: incident recorded before plan_id assigned)
    r=hr(); r.reduce(hev('a',EventKind.INCIDENT,INC('i')))
    r.reduce(hev('a',EventKind.RECEIPT,RC('e0','p',0))); r.reduce(hev('a',EventKind.RECEIPT,RC('e1','p',1)))
    r.reduce(hev('a',EventKind.PLAN,PLAN('p',2,'i'))); d2_after_plan=hopen(r)
    r.reduce(hev('a',EventKind.RECEIPT,RC('e0','p',0))); r.reduce(hev('a',EventKind.RECEIPT,RC('e1','p',1))); d2_after_replay=hopen(r)
    out['d2_unlinked_all_receipts_before_plan']={'open_after_late_plan':d2_after_plan,'open_after_replaying_same_receipt_ids':d2_after_replay}
    # e. failed step then a verified retry of the same step, same plan
    r=hr(); r.reduce(hev('a',EventKind.INCIDENT,INC('i'))); r.reduce(hev('a',EventKind.PLAN,PLAN('p',1,'i')))
    r.reduce(hev('a',EventKind.RECEIPT,RC('f0','p',0,verified=False))); r.reduce(hev('a',EventKind.RECEIPT,RC('f1','p',0)))
    e_same_plan=hopen(r)
    r.reduce(hev('a',EventKind.PLAN,PLAN('p2',1,'i'))); r.reduce(hev('a',EventKind.RECEIPT,RC('g0','p2',0)))
    out['e_failed_then_retry']={'same_plan_open':e_same_plan,'new_plan_open':hopen(r)}
    assert e_same_plan==['i'] and hopen(r)==[]
    # f. contradictory identity + cross-agent receipt
    r=hr(); r.register_agent('b'); r.reduce(hev('a',EventKind.INCIDENT,INC('i',plan_id='p1')))
    r.reduce(hev('a',EventKind.RECEIPT,RC('x','pX',inc='i'))); r.reduce(hev('b',EventKind.RECEIPT,RC('y','p1',inc='i')))
    out['f_contradictory_and_cross_agent_open']=hopen(r); assert hopen(r)==['i']
    # g. step_index typed as bool
    r=hr(); r.reduce(hev('a',EventKind.INCIDENT,INC('i'))); r.reduce(hev('a',EventKind.PLAN,PLAN('p',2,'i')))
    r.reduce(hev('a',EventKind.RECEIPT,RC('b0','p',False))); r.reduce(hev('a',EventKind.RECEIPT,RC('b1','p',True)))
    out['g_bool_step_indices_open']=hopen(r)
    return out

def h2_real_repair_flow(tmp):
    out={}
    for code in (0,1):
        app=Appliance(str(tmp/('repair%d.db'%code))); app.set_planner(SimplePlanner()); app.set_executor(CountingExecutor(code)); app.set_verifier(ExitCodeVerifier())
        h=HiveAppliance(health_poll_interval=0); h.register_agent(LocalAgentAdapter('a',app))
        try:
            from schemas.types import Severity
            inc=IncidentReport(component=str(tmp/'nf'),symptom='file_missing',severity=Severity.CRITICAL); app.record_incident(inc); h.tick(); before=health(h)
            rs=app.repair(inc); h.tick(); after=health(h)
            plans=[e.payload for e in app.store.query(kind=EventKind.PLAN)]
            hive_internal=[{'id':i['incident_id'],'plan_id':i['plan_id'],'resolved':i['resolved']} for i in h.reducer._agent_incidents['a']]
            h._health_poll_interval=10**12
            out['exit%d'%code]={'hive_reducer_incident_records':hive_internal,'local_reducer_incidents':[{'id':i.id,'plan_id':i.plan_id,'resolved':i.resolved} for i in app.reducer.incidents],'in_memory_incident_obj_resolved':inc.resolved,'steps':[len(p.get('steps',[])) for p in plans],'receipts':len(rs),'local_open':len(app.open_incidents()),'hive_before':before,'hive_after':after,'outcome':app.repair_outcomes.get(inc.id)}
        finally: app.close()
    # Observed: hive reducer resolves the composite incident itself; the displayed count stays 1 because the LOCAL
    # controller reducer never links plan->incident in Appliance.repair() (pre-existing; incident recorded with plan_id='')
    # and update_agent_health takes max(polled, reducer).  Assertions encode that observation.
    assert out['exit0']['hive_reducer_incident_records'][0]['resolved'] is True and out['exit0']['outcome']=='resolved'
    assert out['exit0']['local_open']==1 and out['exit0']['hive_after']['count']==1
    assert out['exit1']['hive_reducer_incident_records'][0]['resolved'] is False and out['exit1']['hive_after']['count']==1
    return out

def h1_h2_interaction(tmp):
    out={}
    for polled in AgentHealth:
        h,a=hive(); a.set_health(polled,0)
        a.add_events([Event(kind=EventKind.INCIDENT,payload={'id':'c','symptom':'x','severity':'critical'}),
                      Event(kind=EventKind.PLAN,payload=PLAN('p',2,'c')),
                      Event(kind=EventKind.RECEIPT,payload=RC('s0','p',0)),
                      Event(kind=EventKind.RECEIPT,payload=RC('s1','p',1,verified=False))])
        h.tick(); partial=health(h); assert partial=={'health':'failed','count':1}, (polled,partial)
        out[polled.value]=partial
    h,a=hive(); a.set_health(AgentHealth.HEALTHY,0)
    a.add_events([Event(kind=EventKind.INCIDENT,payload={'id':'c','symptom':'x','severity':'critical'}),Event(kind=EventKind.PLAN,payload=PLAN('p',2,'c')),Event(kind=EventKind.RECEIPT,payload=RC('s0','p',0)),Event(kind=EventKind.RECEIPT,payload=RC('s1','p',1))])
    h.tick(); h.tick(); out['completed_then_healthy_poll']=health(h); assert health(h)['count']==0
    return out

# ---- U2
def u2_metadata_now(tmp):
    app=Appliance(str(tmp/'db')); app.record_incident(IncidentReport(component='disk',symptom='disk_full')); before=json.loads(json.dumps(app.state_snapshot()))
    ex=CountingExecutor(1,lambda: app.reducer.state.update({'changed':{'x':1}})); app.set_executor(ex); app.set_verifier(ExitCodeVerifier())
    manifest=UpgradeManifest(id='probe',steps=[UpgradeStep(verb='inspect',command='false',rollback_command='NOT EXECUTED')])
    try:
        with patch.object(app._checkpoint_mgr,'load',wraps=app._checkpoint_mgr.load) as load: result=app.upgrade(manifest)
        # CountingExecutor(1) also fails the rollback command -> metadata restored, actions NOT rolled back
        assert load.call_count==1 and app.state_snapshot()==before and result.metadata_restored and not result.actions_rolled_back and not result.rolled_back and ex.calls==2
        with patch.object(app._checkpoint_mgr,'load',return_value=None): missing=app.upgrade(manifest)
        assert not missing.rolled_back and not missing.metadata_restored and missing.rollback_error
        return {'restoration':result.to_dict() if hasattr(result,'to_dict') else vars(result),'state_equal_before':True,'executor_calls_incl_rollback':ex.calls,'missing_checkpoint':{'rolled_back':missing.rolled_back,'metadata_restored':missing.metadata_restored,'actions_rolled_back':missing.actions_rolled_back,'rollback_error':missing.rollback_error}}
    finally: app.close()

def _shell_app(tmp,name):
    from executor.shell_executor import ShellExecutor
    app=Appliance(str(tmp/(name+'.db'))); app.set_executor(ShellExecutor()); app.set_verifier(ExitCodeVerifier()); return app
def _flags(r):
    return {'success':r.success,'steps_completed':r.steps_completed,'rolled_back':r.rolled_back,'metadata_restored':r.metadata_restored,'actions_rolled_back':r.actions_rolled_back,'rollback_error':r.rollback_error,'rollback_results':[{'index':x.get('index'),'success':x.get('success')} for x in r.rollback_results]}

def u2_shell(tmp):
    out={}; q=lambda p: shlex.quote(str(p))
    # a. prior external probe: rollback_command restores file
    app=_shell_app(tmp,'a'); f=tmp/'a.txt'; f.write_text('before')
    try:
        r=app.upgrade(UpgradeManifest(id='ext',steps=[UpgradeStep(verb='inspect',command='printf changed > %s; false'%q(f),rollback_command='printf before > %s'%q(f))]))
        out['a_rollback_ok']={'flags':_flags(r),'file':f.read_text()}; assert not r.success and r.rolled_back and r.metadata_restored and r.actions_rolled_back and f.read_text()=='before'
    finally: app.close()
    # b. failing rollback_command
    app=_shell_app(tmp,'b'); f=tmp/'b.txt'; f.write_text('before')
    try:
        r=app.upgrade(UpgradeManifest(id='extfail',steps=[UpgradeStep(verb='inspect',command='printf changed > %s; false'%q(f),rollback_command='printf partial > %s; exit 3'%q(f))]))
        out['b_rollback_fails']={'flags':_flags(r),'file':f.read_text()}; assert not r.success and not r.rolled_back and r.metadata_restored and not r.actions_rolled_back and r.rollback_error and f.read_text()=='partial'
    finally: app.close()
    # c. multi-step order: completed steps newest-first after failed step; unexecuted step not rolled back
    app=_shell_app(tmp,'c'); log=tmp/'c.log'; log.write_text('')
    try:
        st=[UpgradeStep(verb='inspect',command='printf s%d, >> %s%s'%(k,q(log),'; false' if k==2 else ''),rollback_command='printf r%d, >> %s'%(k,q(log))) for k in range(4)]
        r=app.upgrade(UpgradeManifest(id='multi',steps=st))
        out['c_multi_order']={'flags':_flags(r),'log':log.read_text()}; assert log.read_text()=='s0,s1,s2,r2,r1,r0,' and r.rolled_back
    finally: app.close()
    # d. a completed step lacks rollback_command: others still undone, rolled_back False
    app=_shell_app(tmp,'d'); log=tmp/'d.log'; log.write_text('')
    try:
        st=[UpgradeStep(verb='inspect',command='printf s0, >> %s'%q(log),rollback_command='printf r0, >> %s'%q(log)),
            UpgradeStep(verb='inspect',command='printf s1, >> %s'%q(log)),
            UpgradeStep(verb='inspect',command='printf s2, >> %s; false'%q(log),rollback_command='printf r2, >> %s'%q(log))]
        r=app.upgrade(UpgradeManifest(id='gap',steps=st))
        out['d_missing_rollback_command']={'flags':_flags(r),'log':log.read_text()}; assert log.read_text()=='s0,s1,s2,r2,r0,' and not r.rolled_back and 'no rollback_command' in r.rollback_error and r.metadata_restored
    finally: app.close()
    # e. success path never runs rollback
    app=_shell_app(tmp,'e'); f=tmp/'e.txt'; f.write_text('before')
    try:
        r=app.upgrade(UpgradeManifest(id='ok',steps=[UpgradeStep(verb='inspect',command='printf new > %s'%q(f),rollback_command='printf before > %s'%q(f))]))
        out['e_success']={'flags':_flags(r),'file':f.read_text()}; assert r.success and f.read_text()=='new' and not r.rollback_results
    finally: app.close()
    return out

def u2_cli(tmp):
    import cli
    from types import SimpleNamespace
    out={}; q=lambda p: shlex.quote(str(p))
    for name,rb in (('rb_ok','printf before > {f}'),('rb_fail','false')):
        f=tmp/(name+'.txt'); f.write_text('before')
        m=UpgradeManifest(id=name,steps=[UpgradeStep(verb='inspect',command='printf changed > %s; false'%q(f),rollback_command=rb.format(f=q(f)))]).to_dict()
        mf=tmp/(name+'.json'); mf.write_text(json.dumps(m)); buf=io.StringIO()
        with contextlib.redirect_stdout(buf): cli.cmd_upgrade(SimpleNamespace(recovery_ready=True,manifest=str(mf),store=str(tmp/(name+'.db'))))
        out[name]={'stdout':buf.getvalue(),'file':f.read_text()}
    assert 'Rolled back: YES' in out['rb_ok']['stdout'] and out['rb_ok']['file']=='before'
    assert 'Rolled back: NO' in out['rb_fail']['stdout'] and out['rb_fail']['file']=='changed'
    return out

# ---- P2
def p2_store_now(tmp):
    out={}; root=tmp/'root'; (root/'tg').mkdir(parents=True); outside=tmp/'outside'; outside.mkdir()
    s=AttachmentStore(str(tmp/'db'),attachments_root=str(root))
    try:
        ext=str(outside/'x.bin'); inside=str(root/'tg'/'x.bin')
        out['append_external']=s.append([att(local_path=ext)])
        out['append_inside']=s.append([att(file_id='f2',local_path=inside)])
        b=att(file_id='f3'); s.append([b])
        out['update_status_external']=s.update_status(b.id,'pending',local_path=ext)
        out['update_status_inside']=s.update_status(b.id,'pending',local_path=inside)
        c=s.claim_pending(1)[0]
        out['finish_attempt_external']=s.finish_attempt(c.id,c.attempt_id,'completed',local_path=ext)
        out['row_after_rejected_finish']={'status':s.get(c.id).download_status,'local_path':s.get(c.id).local_path}
        # relative traversal
        out['append_abs_dotdot']=s.append([att(file_id='f4',local_path=str(root/'tg'/'..'/'..'/'outside'/'y.bin'))])
        cwd=os.getcwd()
        try:
            os.chdir(root); out['append_relative_cwd_inside_root']=s.append([att(file_id='f5',local_path='tg/rel.bin')])
            out['append_relative_dotdot_cwd_inside_root']=s.append([att(file_id='f6',local_path='../outside/rel.bin')])
            os.chdir(tmp); out['append_relative_cwd_outside_root']=s.append([att(file_id='f7',local_path='tg/rel.bin')])
        finally: os.chdir(cwd)
        out['stored_relative_path']=s.get(att(file_id='f5').id).local_path if s.get(att(file_id='f5').id) else None
        # symlinks
        (root/'out_link').symlink_to(outside,target_is_directory=True)
        out['append_symlink_in_root_to_outside']=s.append([att(file_id='s1',local_path=str(root/'out_link'/'z.bin'))])
        (root/'dangling').symlink_to(outside/'nonexistent.bin')
        out['append_dangling_symlink_file_to_outside']=s.append([att(file_id='s2',local_path=str(root/'dangling'))])
        (outside/'in_link').symlink_to(root,target_is_directory=True)
        lex=str(outside/'in_link'/'tg'/'w.bin')
        out['append_outside_symlink_into_root']=s.append([att(file_id='s3',local_path=lex)])
        row=s.get(att(file_id='s3').id); out['stored_path_for_outside_symlink']=row.local_path if row else None
        # retarget the external symlink: stored path now denotes an outside location
        if row:
            (outside/'in_link').unlink(); (outside/'in_link').symlink_to(outside,target_is_directory=True); (outside/'tg').mkdir()
            out['stored_path_after_retarget_resolves_to']=str(pathlib.Path(row.local_path).resolve())
            out['rooted_store_contains_after_retarget']=s._root_folder.contains(row.local_path)
        # invalid status + external path: which error wins
        try: out['update_invalid_status_external_path']=s.update_status(b.id,'INVALID',local_path=ext)
        except ValueError as e: out['update_invalid_status_external_path']='ValueError'
    finally: s.close()
    assert out['append_external']==0 and out['update_status_external'] is False and out['finish_attempt_external'] is False
    assert out['append_inside']==1 and out['update_status_inside'] is True and out['append_abs_dotdot']==0
    assert out['append_symlink_in_root_to_outside']==0 and out['append_dangling_symlink_file_to_outside']==0
    # unrooted store unchanged
    u=AttachmentStore(str(tmp/'u.db'))
    try: out['unrooted_append_external']=u.append([att(local_path=str(outside/'x.bin'))])
    finally: u.close()
    return out

def fixed_p2_now(tmp):
    """Prior 6949 P2 probe, same setup; delete_configured_root now needs a legacy row written by an unrooted store."""
    out={}
    for mode in ('append','update','delete_unknown_root','delete_configured_root'):
        base=tmp/mode; base.mkdir(); outside=base/'external'; outside.write_bytes(b'untouched'); f=SharedFolderManager(str(base/'root')); rooted=mode=='delete_configured_root'
        s=AttachmentStore(str(base/'db'),attachments_root=str(f.base_dir) if rooted else None); m=AttachmentDownloadManager(s,f,Writer()); a=att(local_path=str(outside))
        try:
            rooted_append=None
            if mode=='update': a.local_path=''; assert m.enqueue(a); assert s.update_status(a.id,'pending',local_path=str(outside))
            elif rooted:
                rooted_append=s.append([a]); assert rooted_append==0
                legacy=AttachmentStore(str(base/'db')); assert legacy.append([a])==1; legacy.close()
            else: assert s.append([a])==1
            metadata_external=s.get(a.id).local_path==str(outside)
            if mode in ('append','update'):
                r=m.process_pending(); assert r[0]['success']; row=s.get(a.id); assert f.contains(row.local_path) and pathlib.Path(row.local_path).read_bytes()==b'new'
            assert s.delete(a.id) and outside.read_bytes()==b'untouched'
            out[mode]={'rooted_store':rooted,'rooted_append_result':rooted_append,'metadata_external_persisted':metadata_external,'external_file_unchanged':True}
        finally: s.close()
    return out

def p2_production_wiring(tmp):
    from conversation.client import ConversationStoreClient
    from conversation.store import MessageStore
    class DummyIndex: pass
    ms=MessageStore(str(tmp/'conv'/'messages.db'))
    c=ConversationStoreClient(store=ms,index=DummyIndex())
    outside=tmp/'outside.bin'; outside.write_bytes(b'untouched')
    msg=Message(venue='tg',venue_id='room',venue_message_id='1',timestamp=1700000000.,sender_id='u',content='hi'); ms.append([msg]); msg=ms.recent(limit=1)[0] if hasattr(ms,'recent') else msg
    s=c.attachment_store
    out={'default_attachment_store_root':None if s._root_folder is None else str(s._root_folder.base_dir),'folder_manager_root':str(c.folder_manager.base_dir)}
    item=att(message_id=msg.id,local_path=str(outside)); out['default_store_append_external']=s.append([item])
    out['persisted_external_path']=s.get(item.id).local_path==str(outside) if s.get(item.id) else False
    c.download_manager.set_downloader(Writer())
    try:
        res=c.download_manager.process_pending(); out['process_pending']=[{k:v for k,v in x.items() if k in ('success','error')} for x in res]
    except Exception as e: out['process_pending']=repr(e)
    out['outside_after_process']=outside.read_bytes().decode()
    row=s.get(item.id); out['row_after_process']={'status':row.download_status,'local_path_is_external':row.local_path==str(outside),'contained_in_folder':c.folder_manager.contains(row.local_path)}
    out['delete']=s.delete(item.id); out['outside_after_delete']=outside.exists() and outside.read_bytes().decode()
    assert out['default_attachment_store_root'] is None
    return out

def static_constructors(tmp):
    hits=[]
    for p in R.rglob('*.py'):
        if 'tests' in p.parts: continue
        for n,line in enumerate(p.read_text().splitlines(),1):
            if 'AttachmentStore(' in line and 'class ' not in line: hits.append({'path':str(p.relative_to(R)),'line':n,'src':line.strip()})
    return hits


for name,fn in [("P2_rooted_all_mutators",p2_store_now),("H2_prior_residual",h2_prior_residual_now)]: case(name,fn)
(E/"older-regressions.json").write_text(json.dumps(RESULTS,indent=2,default=str))
sys.exit(any(r["probe"]!="PASS" for r in RESULTS))
