"""Public result semantics and appliance/audit observability of uncertain memory application."""
import json,os
from pathlib import Path
from unittest.mock import patch
E=Path(__file__).resolve().parent
ns={'__file__':str(E/'focused7701.py'),'__name__':'defs'};src=(E/'focused7701.py').read_text();exec(compile(src[:src.index('\nout={}\n')],str(E/'focused7701.py'),'exec'),ns)
for k in ['fresh','history','hb','hfeed','hnew','snapshot','fpath']:globals()[k]=ns[k]
from hive.appliance import HiveAppliance
p,s,h=fresh('observable7701')
r=hb(hnew());assert r.status=='refused' and not r
volatile=hfeed(hnew(),s);vr=hb(volatile);assert vr.status=='applied' and bool(vr) and vr.durable is False
orig=os.write
def write(fd,data):
 if fpath(fd)==str(p) and b'"rebind_commit"' in data:raise OSError('zero-byte commit')
 return orig(fd,data)
with patch.object(os,'write',write),patch.object(os,'ftruncate',side_effect=OSError('rollback unavailable')):r=hb(h)
assert r.status=='uncertain' and not bool(r) and r.applied and r.durable is None
app=HiveAppliance();app.reducer=h
status=app.status();assert status['rebind_journal_healthy'] is False
before=snapshot(h);uncertain=r.as_dict()
assert 'status' not in h.owner_rebinds[-1] and 'durable' not in h.owner_rebinds[-1]
r2=h.rebind_plan_owner('a1','missing','i',actor='op',reason='refusal')
assert r2.status=='refused' and h.last_rebind_result.status=='refused'
assert h.journal_status()['fence']['kind']=='commit_uncertain' and h.journal_status()['fence']['durable'] is None
(E/'observability7701.json').write_text(json.dumps(dict(uncertain_result=uncertain,before=before,appliance_status=status,after_later_refusal=snapshot(h),volatile_result=vr.as_dict(),interpretation='Structured API/fence distinguish uncertainty. Appliance summary only says unhealthy; owner_rebinds audit describes memory effects, lacks durability/status/op_id. last_rebind_result is transient and can be overwritten; fence retains uncertainty until clearance.'),indent=2,default=str)+'\n')
print('result semantics and observable surfaces checked')
