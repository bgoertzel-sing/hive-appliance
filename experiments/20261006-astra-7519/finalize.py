"""Verify provenance and produce a curated publication copy; no source edits."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess
E=Path(__file__).resolve().parent;R=E.parent.parent/'repos/hive-astra-7519';P=E.parent/'20260928-astra-7195'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=R)
pin='9194f52d72a0e853427fd725d2683cc39db39339'
assert git('rev-parse','HEAD').decode().strip()==pin
assert git('rev-parse','origin/main').decode().strip()==pin
source=json.loads((E/'source-sha256.json').read_text())
for name,h in source.items():assert digest(R/name)==digest(E/'source'/name)==h,name
provenance=json.loads((E/'copy-provenance.json').read_text())
for name,meta in provenance.items():
 assert digest(P/name)==meta.get('original_sha256',meta['sha256']),name
 assert digest(E/name)==meta['sha256'],name
legacy={}
for c in ['e6afe16','ef18db3','5de0d53','cfb03f2']:
 raw=git('show',c+':controller/reducer.py');assert raw==(E/('legacy-reducer-'+c+'.py')).read_bytes()
 legacy[c]=dict(commit=git('rev-parse',c).decode().strip(),sha256=hashlib.sha256(raw).hexdigest())
# Exclude disposable execution products, retain all primary outputs and inputs.
def selected():
 return sorted(p for p in E.rglob('*') if p.is_file() and not any(x in {'tmp','pytest-tmp','__pycache__'} for x in p.relative_to(E).parts) and (p.relative_to(E).parts[0]!='source' or str(p.relative_to(E/'source')) in source))
patterns=[r'gh[pousr]_[A-Za-z0-9]{30,}',r'github_pat_[A-Za-z0-9_]{50,}',r'sk-(?:proj-)?[A-Za-z0-9_-]{40,}',r'AKIA[0-9A-Z]{16}',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----']
hits=[]
for p in selected()+[R/'docs/ASTRA_REVIEW_7519.md']:
 text=p.read_text(errors='replace')
 for pat in patterns:
  if re.search(pat,text):hits.append(str(p.relative_to(E) if p.is_relative_to(E) else p.relative_to(R)))
assert not hits,hits
integrity=dict(pin=pin,prepublication_origin_main=git('rev-parse','origin/main').decode().strip(),tracked_source_files=len(source),source_and_worktree_hashes_verified=True,prior_copied_evidence_unchanged=True,legacy_provenance=legacy,report_sha256=digest(R/'docs/ASTRA_REVIEW_7519.md'),secret_scan=dict(method='high-specificity credential and private-key patterns over all published files plus report; manual diff/log review',hits=hits),excluded_disposable_directories=['tmp','pytest-tmp','__pycache__'],primary_child_count=len(list(E.glob('*-exit.json'))))
(E/'final-integrity.json').write_text(json.dumps(integrity,indent=2)+'\n')
files=[p for p in selected() if p.name!='SHA256SUMS']
(E/'SHA256SUMS').write_text(''.join(digest(p)+'  '+str(p.relative_to(E))+'\n' for p in files))
D=R/'experiments'/E.name;D.mkdir(parents=True,exist_ok=False)
for p in files+[E/'SHA256SUMS']:
 target=D/p.relative_to(E);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
print(json.dumps(dict(publication_files=len(files)+1,bytes=sum(p.stat().st_size for p in files),integrity=integrity),indent=2))
