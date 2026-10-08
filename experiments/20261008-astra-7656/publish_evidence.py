"""Copy approved evidence/report scope, scan all bytes and generate manifest. No git writes."""
import hashlib,json,re,shutil
from pathlib import Path
E=Path(__file__).resolve().parent
R=Path('/home/openclaw/research-agent/projects/hive-appliance/repos/hive-appliance')
D=R/'experiments'/E.name
omit={'tmp','pytest-tmp','build-prerequisites','__pycache__','.pytest_cache'}
D.mkdir(parents=True,exist_ok=True)
for p in E.rglob('*'):
 if not p.is_file() or any(k in omit for k in p.relative_to(E).parts) or p.suffix=='.pyc':continue
 if p.name in {'postpush-verification.json','SHA256SUMS','publication-checks.json'}:continue
 q=D/p.relative_to(E);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
patterns={
 'github_token':rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})',
 'private_key':rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
 'aws_access_id':rb'AKIA[0-9A-Z]{16}',
 'openai_style':rb'sk-(?:proj-)?[A-Za-z0-9_-]{40,}',
 'telegram_bot_token':rb'(?<![0-9])[0-9]{8,12}:[A-Za-z0-9_-]{35}(?![A-Za-z0-9_-])',
}
report=R/'docs/ASTRA_REVIEW_7656.md'
files=sorted(p for p in D.rglob('*') if p.is_file())+[report]
hits=[]
for p in files:
 for name,pat in patterns.items():
  if re.search(pat,p.read_bytes()):hits.append(dict(file=str(p.relative_to(R)),pattern=name))
assert not hits,hits
checks=dict(scan='High-confidence credential patterns on every published byte, plus focused fixture/log review; not exhaustive',patterns=list(patterns),files_scanned=len(files),matches=hits,largest_bytes=max(p.stat().st_size for p in files),excluded=sorted(omit),target_remote='https://github.com/bgoertzel-sing/hive-appliance.git',target_branch='main',publication_scope=['docs/ASTRA_REVIEW_7656.md','experiments/20261008-astra-7656/'],test_result='764 passed; full suite exactly once',independent_result='20 assertion groups; reproduced defects not conformance passes; focused followups and static checks exit 0',gate='NOT APPROVED',final_content_hash_severity='Medium; followup7656.json supersedes initial High label',source='144 tracked non-experiment files byte-identical; clean isolated worktree',prior_evidence='191 hashes verified')
for base in (E,D):(base/'publication-checks.json').write_text(json.dumps(checks,indent=2)+'\n')
files=sorted(p for p in D.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(D))+'\n' for p in files)
manifest+=hashlib.sha256(report.read_bytes()).hexdigest()+'  ../../docs/ASTRA_REVIEW_7656.md\n'
for base in (E,D):(base/'SHA256SUMS').write_text(manifest)
# Final scan also covers the newly generated metadata and manifest.
for p in list(D.rglob('*'))+[report]:
 if p.is_file():
  for name,pat in patterns.items():assert not re.search(pat,p.read_bytes()),(str(p),name)
print(json.dumps(checks,indent=2))
