import hashlib,json,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent;R=E.parent.parent/'repos/hive-astra-7160';report=E.parent.parent/'docs/ASTRA_REVIEW_7160.md'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=R,text=True)
m=json.loads((E/'source-sha256.json').read_text());p=json.loads((E/'copy-provenance.json').read_text())
changed=[n for n,v in p.items() if sha(E/n)!=v['sha256']]
r=dict(head=git('rev-parse','HEAD').strip(),git_status=git('status','--porcelain'),tracked_files=len(m),worktree_source_unchanged=all(sha(R/n)==h for n,h in m.items()),export_source_unchanged=all(sha(E/'source'/n)==h for n,h in m.items()),prior_evidence_unchanged=all(sha(Path(v['source']))==v['sha256'] for v in p.values()),copied_helpers_changed=changed,pytest_start_markers=len(list(E.glob('pytest-started.json'))),pytest_exit=json.loads((E/'pytest-exit.json').read_text()),report_sha256=sha(report))
assert r['git_status']=='' and r['worktree_source_unchanged'] and r['export_source_unchanged'] and r['prior_evidence_unchanged'] and changed==['run_review.py'] and r['pytest_start_markers']==1
(E/'final-integrity.json').write_text(json.dumps(r,indent=2)+'\n')
lines=[]
for f in sorted(E.rglob('*')):
 if f.is_file() and not any(v in ('tmp','pytest-tmp','source','__pycache__') for v in f.relative_to(E).parts) and f.name!='SHA256SUMS':lines.append(sha(f)+'  '+str(f.relative_to(E)))
(E/'SHA256SUMS').write_text('\n'.join(lines)+'\n');print(json.dumps(r,indent=2))
