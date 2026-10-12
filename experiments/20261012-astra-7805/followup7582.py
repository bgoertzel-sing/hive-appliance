"""Focused new-finding controls and audit clipping; does not rerun the full suite."""
import copy,json,logging,os,sys
from pathlib import Path
E=Path(__file__).resolve().parent
raw=(E/'review7582.py').read_text();defs=raw[:raw.index('\nout={}\n')];ns={'__file__':str(E/'review7582.py'),'__name__':'definitions'};exec(compile(defs,str(E/'review7582.py'),'exec'),ns)
I,P,R,new,feed,view,preview,rebind,opens,rt=[ns[k] for k in ['I','P','R','new','feed','view','preview','rebind','opens','rt']]
out={}
# Same receipt, owner declared first: no closure (literal identity oracle).
controls=[]
for address in ['incident','dual']:
 l,h=new()
 for e in [I('i','p'),I('j','p'),P(i='i'),R(p='' if address=='incident' else 'p',i='j')]:feed(l,h,e)
 assert opens(l,h)==[['i','j'],['i','j']]
 controls.append(dict(address=address,result=view(l,h),verified=[list(l._plan_verified['p']),list(h._plan_verified_steps['a1:p'])]))
out['foreign_receipt_owned_controls']=controls
# All buffered receipts credited or consumed; audit truncates IDs but not count.
l,h=new()
for e in [I('i','p'),I('j'),P(n=60),P(i='j')]:feed(l,h,e)
for k in range(60):feed(l,h,R('held'+str(k),p='',i='j',k=k))
pv,hv=preview(l,h,'j');assert len(pv['held_receipts'])==len(hv['held_receipts'])==60;assert pv['would_close']==hv['would_close']==['j'];assert rebind(l,h,'j')==[True,True]
la=l.migration_diagnostics['owner_rebinds'][-1];ha=h.owner_rebinds[-1]
assert la['pending_before']==ha['pending_before']==60;assert la['effect_counts']['credited']==60;assert len(la['effect_ids']['credited'])==32 and len(ha['held_receipt_ids'])==50
assert opens(l,h)==[['i'],['i']]
out['receipt_audit_caps']=dict(local=la,hive=ha,preview_receipt_counts=[len(pv['held_receipts']),len(hv['held_receipts'])])
# Purity includes all live fields; the simulated hive nevertheless emits INFO.
l,h=new()
for e in [I('i','p'),I('j','p'),P(),R(),P(i='i')]:feed(l,h,e)
messages=[]
class Capture(logging.Handler):
 def emit(self,r):messages.append(dict(level=r.levelname,message=r.getMessage()))
handler=Capture();log=logging.getLogger('hive.reducer');old=log.level;log.setLevel(logging.INFO);log.addHandler(handler)
try:
 before=copy.deepcopy(vars(h));hv=h.preview_rebind('a1','p','i');assert vars(h)==before;assert opens(l,h)==[['i','j'],['i','j']]
finally:log.removeHandler(handler);log.setLevel(old)
assert any('incident i resolved' in x['message'] for x in messages)
out['hive_preview_log_side_effect']=dict(messages=messages,live_open=opens(l,h),would_close=hv['would_close'],severity='Low')
# Local recovery guidance now labels only the legacy subset authoritative.
l=rt(l);assert l.quarantined_plans()==['p'] and not l._owner_unproven
out['stale_restore_guidance']=dict(recovery=l.migration_diagnostics['recovery'],owner_unproven=list(l._owner_unproven),current_quarantine=l.quarantined_plans(),severity='Low')
(E/'followup7582.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:'observed' for k in out}))
