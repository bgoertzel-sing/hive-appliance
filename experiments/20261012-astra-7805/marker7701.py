"""Exact legacy-marker startup bypass on new creation and header-only adoption."""
import json
from pathlib import Path
E=Path(__file__).resolve().parent
ns={'__file__':str(E/'focused7701.py'),'__name__':'defs'};src=(E/'focused7701.py').read_text();exec(compile(src[:src.index('\nout={}\n')],str(E/'focused7701.py'),'exec'),ns)
for k in ['hnew','hfeed','history','snapshot','anchor','hb']:globals()[k]=ns[k]
T=ns['T'];rows=[]
for mode in [m+s for m in ['no_journal_no_anchor','empty_journal_no_anchor','header_no_anchor','header_with_anchor'] for s in ['.fence','.fence.tmp']]:
 suffix='.fence.tmp' if mode.endswith('.fence.tmp') else '.fence';mode=mode[:-len(suffix)];tag=mode+suffix
 p=T/('marker7708-'+tag+'.jsonl')
 if mode.startswith('header'):
  hnew(p)
  if mode=='header_no_anchor':anchor(p).unlink()
 elif mode=='empty_journal_no_anchor':p.write_bytes(b'')
 marker=Path(str(p)+suffix);marker.write_bytes(b'legacy unresolved write fence')
 disk={str(x):x.read_bytes() for x in p.parent.glob(p.name+'*')};h=hfeed(hnew(p),history());before=snapshot(h);r=hb(h)
 bypass=False
 assert h.journal_status()['healthy']==bypass and bool(r)==bypass
 if bypass:assert r.status=='applied' and r.durable is True
 assert marker.exists()
 later=[hfeed(hnew(p),history()) for _ in range(2)]
 for z in later:assert not z.journal_status()['healthy'] and z.journal_status()['fence']['kind']=='legacy' and not z._plan_owner
 assert disk=={str(x):x.read_bytes() for x in p.parent.glob(p.name+'*')}
 rows.append(dict(suffix=suffix,mode=mode,bypass=bypass,before=before,result=r.as_dict(),live=snapshot(h),restarts=[snapshot(z) for z in later]))
(E/'marker7701.json').write_text(json.dumps(dict(cases=rows,verdict='CLOSED: eight variants fence before any creation; unchanged bytes over two restarts.'),indent=2,default=str)+'\n')
print('eight marker variants fenced; no disk changes')
