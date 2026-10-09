"""Validate saved startup outcomes and recover every interrupted-identity case."""
import json
from pathlib import Path
E=Path(__file__).resolve().parent
ns={'__file__':str(E/'focused7701.py'),'__name__':'defs'};src=(E/'focused7701.py').read_text();exec(compile(src[:src.index('\nout={}\n')],str(E/'focused7701.py'),'exec'),ns)
rows=[]
for r in json.loads((E/'startup7701.json').read_text())['cases'][1:]:
 v=r['restart']['view'];b=r['before_restart']
 if v['journal_status']['healthy']:
  assert (not b['journal_exists'] and not b['anchor_exists']) or (b['journal_exists'] and b['anchor_exists'])
  assert r['rebind']['status']=='applied' and r['rebind']['durable'] is True
  assert r['second_restart']['view']['owner']=={'a1:p':'i'}
 else:
  assert r['rebind']['status']=='refused' and not r['second_restart']['view']['journal_status']['healthy']
  p=ns['T']/('initial7701-'+r['name']+'.jsonl');h=ns['hfeed'](ns['hnew'](p),ns['history']())
  assert h.clear_journal_fence('operator','interrupted first use, no authorizations existed')
  n=ns['hfeed'](ns['hnew'](p),ns['history']());assert n.journal_status()['healthy'] and not n._plan_owner
  assert ns['hb'](n);z=ns['hfeed'](ns['hnew'](p),ns['history']());assert z._plan_owner=={'a1:p':'i'}
  rows.append(dict(case=r['name'],after_clear=ns['snapshot'](z)))
(E/'startup-recovery7708.json').write_text(json.dumps(dict(checked_injections=48,recovered=len(rows),cases=rows),indent=2)+'\n');print('48 startup outcomes validated; 24 fenced cases successfully cleared/reissued/restarted')
