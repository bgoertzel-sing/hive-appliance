"""Exact legacy-marker startup bypass on new creation and header-only adoption."""
import json
from pathlib import Path
E=Path(__file__).resolve().parent
ns={'__file__':str(E/'focused7701.py'),'__name__':'defs'};src=(E/'focused7701.py').read_text();exec(compile(src[:src.index('\nout={}\n')],str(E/'focused7701.py'),'exec'),ns)
for k in ['hnew','hfeed','history','snapshot','anchor','hb']:globals()[k]=ns[k]
T=ns['T'];rows=[]
for mode in ['no_journal_no_anchor','empty_journal_no_anchor','header_no_anchor','header_with_anchor']:
 p=T/('marker7701-'+mode+'.jsonl')
 if mode.startswith('header'):
  hnew(p)
  if mode=='header_no_anchor':anchor(p).unlink()
 elif mode=='empty_journal_no_anchor':p.write_bytes(b'')
 marker=Path(str(p)+'.fence');marker.write_bytes(b'legacy unresolved write fence')
 h=hfeed(hnew(p),history());before=snapshot(h);r=hb(h)
 bypass=mode!='header_with_anchor'
 assert h.journal_status()['healthy']==bypass and bool(r)==bypass
 if bypass:assert r.status=='applied' and r.durable is True
 assert marker.exists()
 later=[hfeed(hnew(p),history()) for _ in range(2)]
 for z in later:assert not z.journal_status()['healthy'] and z.journal_status()['fence']['kind']=='legacy_marker' and not z._plan_owner
 rows.append(dict(mode=mode,bypass=bypass,before=before,result=r.as_dict(),live=snapshot(h),restarts=[snapshot(z) for z in later]))
(E/'marker7701.json').write_text(json.dumps(dict(cases=rows,verdict='OPEN Medium F-legacy-marker-startup-bypass: creation/adoption early return skips extant legacy fence; durable APPLIED live then two restarts fence/hold without any post-return disk edit.'),indent=2,default=str)+'\n')
print('three bypasses and matched existing-anchor fence control reproduced')
