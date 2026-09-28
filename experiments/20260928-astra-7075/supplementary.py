import pathlib,json,sys
E=pathlib.Path(__file__).resolve().parent
exec((E/'new_cases.py').read_text().split("run('failure_success_buffer'")[0])
# The buffered contradiction exists while q is open, then q resolves before p arrives.
run('buffer_contradiction_then_other_resolved',[
 I(),I('other'),R('bad',0,p='p',i='other'),R('good',1),P('q','other',1),R('q0',p='q'),P(),R('retry',0)
],[1,2,2,2,2,1,1,0])
run('buffer_contradiction_then_other_resolved_snapshot',[
 I(),I('other'),R('bad',0,p='p',i='other'),R('good',1),P('q','other',1),R('q0',p='q'),P(),R('retry',0)
],[1,2,2,2,2,1,1,0],restore_at=5)
# Control: contradiction received while q already registered is rejected promptly by both.
run('contradiction_received_after_other_plan',[
 I(),I('other'),P('q','other',1),R('bad',0,p='p',i='other'),R('good',1),R('q0',p='q'),P(),R('retry',0)
],[1,2,2,2,2,1,1,0])
# Prelinked incident-only receipts: both buffers must become eligible from plan metadata.
ii=I();ii.payload['plan_id']='p'
run('prelinked_incident_only_different_plan_incident',[ii,I('other'),R('is',0,p='',i='i'),P('p','other',1)],[1,2,2,0])
(E/'supplementary.json').write_text(json.dumps(O,indent=2))
s={'total':len(O),'passed':sum(v['passed'] for v in O.values()),'failed':{k:v['errors'] for k,v in O.items() if not v['passed']}}
print(json.dumps(s,indent=2));sys.exit(bool(s['failed']))
