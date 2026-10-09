from pathlib import Path
import difflib
E=Path('/tmp/hive-astra-7708/20261008-astra-7708');P=Path('/tmp/hive-astra-7708-source/experiments/20261008-astra-7701')
p=E/'focused7701.py';s=p.read_text();a=s.index('def startup(row):');b=s.index('def prefixes(row):',a)
s=s[:a]+'''def startup(row):
 rows=[]
 for mode in ['journal_missing_id_present','id_missing_committed_journal','id_missing_header_only','empty_journal_id_present','both_missing','legacy_marker_header_adoption']:
  p,s,h=fresh('startup7708-'+mode)
  if mode=='id_missing_committed_journal':assert hb(h)
  if mode in ['journal_missing_id_present','both_missing']:p.unlink()
  if mode in ['id_missing_committed_journal','id_missing_header_only','both_missing','legacy_marker_header_adoption']:anchor(p).unlink()
  if mode=='empty_journal_id_present':p.write_bytes(b'')
  if mode=='legacy_marker_header_adoption':Path(str(p)+'.fence').write_bytes(b'legacy fence')
  z=hfeed(hnew(p),s);first=snapshot(z);expected=mode=='both_missing'
  assert z.journal_status()['healthy']==expected
  r=hb(z);assert bool(r)==expected
  later=restarts(p,s)
  for n in later:assert n.journal_status()['healthy']==expected
  recovered=None
  if not expected:
   assert z.clear_journal_fence('reviewer','inspect interrupted creation')
   n=hfeed(hnew(p),s);assert n.journal_status()['healthy'] and not n._plan_owner
   recovered=snapshot(n)
  rows.append(dict(mode=mode,first=first,result=r.as_dict(),later=[snapshot(x) for x in later],recovered=recovered))
 row['cases']=rows
''' + s[b:];p.write_text(s)
p=E/'clearance7701.py';s=p.read_text().replace("old=p.read_bytes();oldid=", "\n for suffix in ['.fence','.fence.tmp']:Path(str(p)+suffix).write_bytes(b'legacy marker retained for crash matrix')\n old=p.read_bytes();oldid=");p.write_text(s)
p=E/'marker7701.py';s=p.read_text().replace("for mode in ['no_journal_no_anchor','empty_journal_no_anchor','header_no_anchor','header_with_anchor']:","for mode in [m+s for m in ['no_journal_no_anchor','empty_journal_no_anchor','header_no_anchor','header_with_anchor'] for s in ['.fence','.fence.tmp']]:\n suffix='.fence.tmp' if mode.endswith('.fence.tmp') else '.fence';mode=mode[:-len(suffix)];tag=mode+suffix")
s=s.replace("'marker7701-'+mode", "'marker7708-'+tag").replace("str(p)+'.fence'","str(p)+suffix").replace("bypass=mode!='header_with_anchor'","bypass=False").replace("=='legacy_marker'","=='legacy'")
s=s.replace("h=hfeed(hnew(p),history());before=", "disk={str(x):x.read_bytes() for x in p.parent.glob(p.name+'*')};h=hfeed(hnew(p),history());before=")
s=s.replace("rows.append(dict(mode=mode", "assert disk=={str(x):x.read_bytes() for x in p.parent.glob(p.name+'*')}\n rows.append(dict(suffix=suffix,mode=mode")
s=s.replace("OPEN Medium F-legacy-marker-startup-bypass: creation/adoption early return skips extant legacy fence; durable APPLIED live then two restarts fence/hold without any post-return disk edit.","CLOSED: eight variants fence before any creation; unchanged bytes over two restarts.").replace("three bypasses and matched existing-anchor fence control reproduced","eight marker variants fenced; no disk changes")
p.write_text(s)
d=[]
for n in ['followup7694.py','focused7701.py','clearance7701.py','marker7701.py']:
 d.extend(difflib.unified_diff((P/n).read_text().splitlines(True),(E/n).read_text().splitlines(True),fromfile='7701/'+n,tofile='7708/'+n))
(E/'adaptation-7708.diff').write_text(''.join(d))
