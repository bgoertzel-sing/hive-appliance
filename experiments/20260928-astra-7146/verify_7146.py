import hashlib,json,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent
R=E.parent.parent/'repos/hive-astra-7146'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((E/'source-sha256.json').read_text())
provenance=json.loads((E/'copy-provenance.json').read_text())
extra={}
for folder,names,prefix in [('20260928-astra-7133',['semantic_7133.py','focused_witnesses.py','correct_owner_traces.py'],''),('20260928-astra-7133-tracked',['expanded_probes.py','followup_probes.py','semantic_probes.py','legacy_information_loss.py'],'review-a/')]:
 for name in names:
  original=E.parent/folder/name;copy=E/prefix/name
  extra[prefix+name]=dict(source=str(original),sha256=sha(original),copy_matches=sha(original)==sha(copy))
(E/'extra-copy-provenance.json').write_text(json.dumps(extra,indent=2)+'\n')
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
status=subprocess.check_output(['git','status','--porcelain'],cwd=R,text=True)
record=dict(head=head,git_status=status,tracked_files=len(manifest),source_unchanged=all(sha(R/n)==h for n,h in manifest.items()),original_7075_copies_unchanged=all(sha(E/n)==v['sha256'] and sha(Path(v['source']))==v['sha256'] for n,v in provenance.items()),extra_copies_unchanged=all(v['copy_matches'] for v in extra.values()),pytest_invocations=len(list(E.glob('pytest-started.json'))),pytest_exit=json.loads((E/'pytest-exit.json').read_text())['exit_code'])
assert record['source_unchanged'] and record['original_7075_copies_unchanged'] and record['extra_copies_unchanged'] and status==''
(E/'final-integrity.json').write_text(json.dumps(record,indent=2)+'\n')
report=E.parent.parent/'docs/ASTRA_REVIEW_7146.md'
(E/'report-sha256.json').write_text(json.dumps(dict(path=str(report),sha256=sha(report)),indent=2)+'\n')
lines=[]
for p in sorted(E.rglob('*')):
 if p.is_file() and not any(v in ('tmp','pytest-tmp','source','__pycache__') for v in p.relative_to(E).parts) and p.name!='SHA256SUMS':lines.append(sha(p)+'  '+str(p.relative_to(E)))
(E/'SHA256SUMS').write_text('\n'.join(lines)+'\n')
print(json.dumps(record,indent=2))
