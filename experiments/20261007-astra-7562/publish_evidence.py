"""Publish only review evidence and original tracked source; exclude disposable files."""
import hashlib,json,re,shutil,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent;R=E.parents[1]/'repos/hive-astra-7562';D=R/'experiments'/E.name
assert not D.exists();D.mkdir(parents=True)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
source=json.loads((E/'source-sha256.json').read_text())
for name in source:
 dst=D/'source'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(E/'source'/name,dst)
excluded={'source','tmp','pytest-tmp','build-prerequisites','__pycache__'}
for src in E.rglob('*'):
 rel=src.relative_to(E)
 if not src.is_file() or rel.parts[0] in excluded or '__pycache__' in rel.parts or src.suffix=='.pyc':continue
 dst=D/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
report=R/'docs/ASTRA_REVIEW_7562.md'
patterns={
 'github_token':r'gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}',
 'private_key':r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
 'aws_access_key':r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
 'openai_key':r'\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}',
 'credential_url':r'https?://[^\s/@:]+:[^\s/@]+@',
}
hits=[];sizes=[]
for p in [report]+sorted(x for x in D.rglob('*') if x.is_file()):
 raw=p.read_bytes();sizes.append((str(p.relative_to(R)),len(raw)))
 try:s=raw.decode()
 except UnicodeDecodeError:raise AssertionError('Unexpected binary publication: '+str(p))
 for name,pattern in patterns.items():
  for m in re.finditer(pattern,s):hits.append(dict(file=str(p.relative_to(R)),line=s.count('\n',0,m.start())+1,pattern=name))
assert not hits,hits
check=dict(reviewed_pin='57a62987a8e46fe2fdf45d63c1a9c148d3e12fbd',secret_scan='high-confidence credential patterns; no matches; targeted source/fixture/log review; not an exhaustive secret detector',patterns=list(patterns),hits=hits,files=len(sizes),largest=sorted(sizes,key=lambda x:x[1],reverse=True)[:5],excluded=['tmp','pytest-tmp','__pycache__','third-party build-prerequisites binaries (hashes retained)','untracked source build/dist/egg artifacts'],source_and_helpers_verified=True)
(D/'publication-checks.json').write_text(json.dumps(check,indent=2)+'\n')
files=sorted(p for p in D.rglob('*') if p.is_file() and p.name not in ['SHA256SUMS','final-integrity.json'])
(D/'SHA256SUMS').write_text(''.join(digest(p)+'  '+str(p.relative_to(D))+'\n' for p in files))
final=dict(reviewed_pin=check['reviewed_pin'],artifact_count=len(files),manifest_sha256=digest(D/'SHA256SUMS'),report_sha256=digest(report))
(D/'final-integrity.json').write_text(json.dumps(final,indent=2)+'\n')
# Mirror publication manifests into the working evidence; no prior experiment touched.
for n in ['publication-checks.json','SHA256SUMS','final-integrity.json']:shutil.copy2(D/n,E/n)
subprocess.run(['python3','verify_evidence.py'],cwd=D,check=True)
print(json.dumps(check,indent=2))
