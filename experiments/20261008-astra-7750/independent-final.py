"""Independent 7003 edge probes; extends 6986 public-repair and path scenarios."""
import sys,pathlib,tempfile,json,os,traceback
E=pathlib.Path(__file__).resolve().parent; R=pathlib.Path(__import__('os').environ.get('HIVE_SRC', str(E.parent.parent)));sys.path.insert(0,str(R))
from controller.reducer import Reducer
from controller.appliance import Appliance
from schemas.types import Event,EventKind,IncidentReport,Receipt,Severity
from hive.reducer import HiveReducer
from hive.types import HiveEvent
from hive.appliance import HiveAppliance
from hive.adapter import LocalAgentAdapter
from reasoning.planner import SimplePlanner
from verifier.exit_code_verifier import ExitCodeVerifier
O={}
def ev(k,p):return Event(kind=k,payload=p)
def inc():return ev(EventKind.INCIDENT,{'id':'i','component':'svc','symptom':'s','severity':'critical'})
def plan(n=2):return ev(EventKind.PLAN,{'id':'p','incident_id':'i','steps':[{'verb':'inspect'}]*n})
def rc(rid,idx,ok=True,**kw):return ev(EventKind.RECEIPT,dict(id=rid,plan_id='p',step_index=idx,verified=ok,**kw))
def schedule(name,stream,expected,restore_at=None):
 l=Reducer();h=HiveReducer();h.register_agent('a'); counts=[];transitions=0
 for j,e in enumerate(stream):
  prev=len(l.open_incidents());l.reduce(e);h.reduce(HiveEvent(source_agent='a',original_event=e))
  a=len(l.open_incidents());b=len(h._open_agent_incidents('a'));assert a==b,(name,j,a,b)
  counts.append(a);transitions+=prev==1 and a==0
  if j==restore_at:
   snap=json.loads(json.dumps(l.snapshot()));l=Reducer();l.restore_snapshot(snap);assert l.snapshot()==snap
 assert counts==expected,(name,counts,expected)
 O[name]={'counts':counts,'local_hive_agree':True,'resolve_transitions':transitions,'local_seen':len(l._seen_receipt_ids),'hive_seen':len(h._seen_receipts)}
 return l,h
schedule('late_all_replay',[inc(),rc('0',0),rc('1',1),rc('0',0),plan(),rc('0',0),rc('1',1),plan()],[1,1,1,1,0,0,0,0])
schedule('early_then_plan',[inc(),rc('0',0),plan(),rc('1',1)],[1,1,1,0])
schedule('duplicates',[inc(),plan(),rc('0',0),rc('0b',0),rc('1',1)],[1,1,1,1,0])
schedule('invalid',[inc(),plan()]+[rc(str(j),x) for j,x in enumerate([True,False,-1,2,'1',1.0,None])]+[rc('good0',0),rc('good1',1)],[1]*10+[0])
schedule('retry',[inc(),plan(),rc('f',0,False),rc('1',1),rc('r',0),rc('f',0,False)],[1,1,1,1,0,0])
schedule('pending_snapshot',[inc(),rc('0',0),rc('1',1),plan(),rc('0',0)],[1,1,1,0,0],restore_at=2)
schedule('progress_snapshot',[inc(),plan(),rc('0',0),rc('0b',0),rc('1',1)],[1,1,1,1,0],restore_at=2)
l=Reducer();l.reduce(inc());l.reduce(plan());s=l.snapshot();s['plan_receipts']={'p':[True,True]};s.pop('seen_receipt_ids',None);l.restore_snapshot(s);assert l._plan_verified['p']==set();l.reduce(rc('a',0));assert len(l.open_incidents())==1;l.reduce(rc('b',1));assert not l.open_incidents();O['legacy_snapshot']='boolean evidence discarded; fresh distinct steps required'
class Exec:
 def __init__(self,fail=False):self.fail=fail;self.calls=[]
 def execute_step(self,step,plan,index):self.calls.append(index);return Receipt(plan_id=plan.id,step_index=index,exit_code=1 if self.fail and index==1 else 0)
with tempfile.TemporaryDirectory(dir='/tmp/hive-astra-7750-runtime') as td:
 t=pathlib.Path(td)
 for fail in (False,True):
  app=Appliance(str(t/f'repair-{fail}.db'));app.set_planner(SimplePlanner());x=Exec(fail);app.set_executor(x);app.set_verifier(ExitCodeVerifier());h=HiveAppliance(health_poll_interval=0);h.register_agent(LocalAgentAdapter('a',app));i=IncidentReport(component=str(t/'missing'),symptom='file_missing',severity=Severity.CRITICAL);assert not i.plan_id;app.record_incident(i);h.tick();rs=app.repair(i);h.tick();h.tick();state=h.reducer.state.agents['a'];out={'verified':[r.verified for r in rs],'calls':x.calls,'local_open':len(app.open_incidents()),'hive_open':state.open_incidents,'health':state.health.value,'outcome':app.repair_outcomes[i.id]};assert x.calls==[0,1];assert out['local_open']==out['hive_open']==int(fail);assert out['health']==('failed' if fail else 'healthy');O[f'public_repair_failure_{fail}']=out;app.close()
 from conversation.client import ConversationStoreClient
 from conversation.store import MessageStore
 from conversation.types import Attachment,Message
 from conversation.attachments import SharedFolderManager
 for custom in (False,True):
  base=t/str(custom);base.mkdir();outside=base/'outside';outside.mkdir();sentinel=outside/'x';sentinel.write_bytes(b'untouched');folder=SharedFolderManager(str(base/'custom')) if custom else None
  c=ConversationStoreClient(store=MessageStore(str(base/'c.db')),index=object(),folder_manager=folder);s=c.attachment_store;root=c.folder_manager.base_dir;assert s._root_folder.base_dir==root
  m=Message(venue='tg',venue_id='r',venue_message_id='1',timestamp=1700000000.,sender_id='u',content='x');c.store.append([m])
  def item(label,path):return Attachment(message_id=m.id,file_id=label,venue='tg',venue_id='r',file_name='x',local_path=str(path))
  (root/'sub').mkdir(parents=True);(root/'out').symlink_to(outside,target_is_directory=True);link=outside/'in';link.symlink_to(root,target_is_directory=True)
  bad=[sentinel,root/'..'/'outside'/'x','sub/x','../outside/x',root/'out'/'x',link/'sub'/'x'];admitted=[]
  for j,path in enumerate(bad):admitted.append(s.append([item(str(j),path)]))
  assert admitted==[0]*len(bad);link.unlink();link.symlink_to(outside,target_is_directory=True)
  a=item('canonical',root/'sub'/'..'/'x');assert s.append([a])==1;stored=s.get(a.id).local_path;assert stored==str(root/'x')
  (root/'inner').symlink_to(root/'sub',target_is_directory=True);b=item('inner',root/'inner'/'y');assert s.append([b])==1;assert s.get(b.id).local_path==str(root/'sub'/'y')
  assert s.update_status(a.id,'pending',local_path=str(root/'sub'/'..'/'z'));assert s.get(a.id).local_path==str(root/'z');assert not s.update_status(a.id,'pending',local_path=str(sentinel))
  cwd=os.getcwd()
  class Writer:
   def download(self,attachment,dest):pathlib.Path(dest).write_bytes(b'new');return True
  try:
   os.chdir(outside);assert s._root_folder.contains(stored);c.download_manager.set_downloader(Writer());result=c.download_manager.process_pending();assert all(r['success'] for r in result),result
   paths=[s.get(v.id).local_path for v in (a,b)];assert all(c.folder_manager.contains(p) for p in paths);assert s.delete(a.id) and s.delete(b.id);assert sentinel.read_bytes()==b'untouched'
  finally:os.chdir(cwd)
  O[f'production_paths_custom_{custom}']={'root_matches':True,'rejected':admitted,'canonical':stored,'download_results':result,'outside_untouched':True};s.close();c.store.close()
(E/'independent-final.json').write_text(json.dumps(O,indent=2,default=str));print(json.dumps(O,indent=2,default=str))
