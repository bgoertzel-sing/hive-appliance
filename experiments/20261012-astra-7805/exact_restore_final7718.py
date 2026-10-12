"""Exact 7708 restore timeline, taking immutable observations before reissue."""
import json,logging
from pathlib import Path
E=Path(__file__).resolve().parent
ns={'__file__':str(E/'reset7718.py'),'__name__':'defs'}
src=(E/'reset7718.py').read_text();exec(compile(src[:src.index('\nout={}\n')],str(E/'reset7718.py'),'exec'),ns)
p,s,h=ns['restored']('exact-restore-final-timeline')
logs=[]
class Capture(logging.Handler):
 def emit(self,r):logs.append(dict(level=r.levelname,message=r.getMessage()))
handler=Capture();logger=logging.getLogger('hive.reducer');logger.setLevel(logging.WARNING);logger.addHandler(handler)
try:
 old=ns['pair'](p);healthy_restored=ns['state'](h)
 assert h.clear_journal_fence('op','does not reset healthy pair') is False
 info=h.reset_journal('op','restore without discarded authorization')
 assert all(Path(dst).read_bytes()==old[src] for src,dst in info['archived'].items())
 ns['hfeed'](h,s);ns['held'](h);after_reset=ns['state'](h)
 restarts=[]
 for _ in range(2):
  z=ns['hfeed'](ns['hnew'](p),s);ns['held'](z);restarts.append(ns['state'](z))
 assert ns['hb'](z)
 reissued=[]
 for _ in range(2):
  z=ns['hfeed'](ns['hnew'](p),s);assert z._plan_owner=={'a1:p':'i'};reissued.append(ns['state'](z))
 assert any('Rebind journal RESET by op' in x['message'] for x in logs)
 assert ns['records'](p)[1]['actor']=='op'
 out=dict(healthy_restored=healthy_restored,info=info,archive_bytes_match=True,after_reset=after_reset,two_restarts_before_reissue=restarts,two_restarts_after_reissue=reissued,logs=logs,passed=True,
 note='Observations frozen before mutation. reset7718 successful_restore cases assert held before reissue, but its second reducer is subsequently rebound before serializing that earlier list; this supplemental timeline removes that display ambiguity.')
 (E/'exact-restore-final7718.json').write_text(json.dumps(out,indent=2)+'\n')
 print('Exact restore: archived both files; discarded p held across two restarts; reissued p survives two restarts; audit/log visible')
finally:logger.removeHandler(handler)
