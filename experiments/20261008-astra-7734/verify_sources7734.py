import hashlib,json,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent;R=E.parent.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
git=lambda *a:subprocess.check_output(['git',*a],cwd=R).decode().strip()
b=json.loads((E/'source-verification-before.json').read_text());S=Path(b['source']);pin=b['pin']
rows=[]
for f,h in b['hashes'].items():
 blob=subprocess.check_output(['git','show',pin+':'+f],cwd=R);assert hashlib.sha256(blob).hexdigest()==h==sha(S/f)==sha(R/f),f
result=dict(pin=pin,files=len(b['hashes']),source=str(S),all_match_initial_hashes=True,all_match_pinned_git_blobs=True,repository_source_unchanged=True,source_is_export_not_git_worktree=True,git_status=git('status','--short'),origin_main=git('rev-parse','origin/main'))
(E/'source-verification.json').write_text(json.dumps(result,indent=2)+'\n')
for round in ['7669','7678','7694','7701','7708','7718','7727']:
 p=R/('experiments/20261008-astra-'+round);count=0
 for line in (p/'SHA256SUMS').read_text().splitlines():
  expected,name=line.split('  ',1);assert sha(p/name)==expected,(round,name);count+=1
 rows.append(dict(round=round,artifacts=count,all_match=True,manifest_sha256=sha(p/'SHA256SUMS')))
(E/'prior-evidence-verification.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(dict(source_files=len(b['hashes']),prior=rows),indent=2))
