from pathlib import Path
import difflib
E=Path(__file__).resolve().parent
old=(E/'review7678.py').read_text();old=old[:old.index('\nout={}\n')]
# Preserve exact content/canonical and aggregate witnesses; adapt only v4 records/hash/diagnostics.
new=old[:old.index('\ndef faults(row):')]
new=new.replace('7678','7694').replace("entry=json.loads(jp.read_text());entry['incident_id']='j';jp.write_text(json.dumps(entry)+'\\n');m=hfeed(hnew(jp),s)","lines=[json.loads(x) for x in jp.read_text().splitlines()];entry=lines[0];entry['incident_id']='j';jp.write_text(''.join(json.dumps(x)+'\\n' for x in lines));m=hfeed(hnew(jp),s)")
new=new.replace("m.journal_unapplied()[0]['why']","m.journal_status()['corrupt_records'][0]['why']")
new=new.replace('entry=json.loads(original)','entries=[json.loads(x) for x in original.splitlines()];entry=entries[0]')
new=new.replace("jp.write_text(json.dumps(reverse(entry),ensure_ascii=False,separators=(', ', ' : '))+'\\n')","jp.write_text(''.join(json.dumps(reverse(e),ensure_ascii=False,separators=(', ', ' : '))+'\\n' for e in entries))")
new=new.replace('._entry_hash(', '._rec_hash(')
new+=old[old.index('\ndef aggregate(row):'):old.index('\ndef controls(row):')]
# Select retained semantic functions unchanged; v4-specific fixtures follow in separate script.
new+='''
out={}
functions=[('F_journal_content',content),('canonical_hashing',canonical),('aggregate_real_10000',aggregate)]
for name in ['unregister','journal_order','rejected_and_partial','recovery_text']:functions.append(('retained_'+name,q[name]))
g=q['g']
for name,fn in [('foreign',g['foreign']),('incidentless',g['incidentless']),('hold',g['hold']),('quiet_guidance',g['quiet_and_guidance']),('plan_only_witness',g['a']['witness']),('hold_144_schedules',g['a']['schedules']),('refusals_pending',g['a']['refusals_and_pending']),('late_link_warnings',g['a']['warnings']),('regressions',g['retained'])]:functions.append(('retained_'+name,fn))
for name,fn in functions:
 r={}
 try:fn(r);r['passed']=True
 except Exception as ex:r.update(passed=False,error=repr(ex),traceback=traceback.format_exc())
 out[name]=r;print(name,r['passed'],r.get('error',''),flush=True);save('review7694.json',out)
save('review7694-summary.json',dict(groups=len(out),passed=sum(r['passed'] for r in out.values()),failed=[k for k,v in out.items() if not v['passed']]))
sys.exit(not all(r['passed'] for r in out.values()))
'''
(E/'review7694.py').write_text(new)
(E/'witness-adaptation.diff').write_text(''.join(difflib.unified_diff((E/'review7678.py').read_text().splitlines(True),new.splitlines(True),fromfile='7678/review7678.py',tofile='7694/review7694.py')))
