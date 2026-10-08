"""Review artifact copy and high-confidence scan; no git writes or credentials."""
import hashlib,json,re,shutil,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent
S=E.parent.parent/'repos/hive-astra-7638'
D=S/'experiments'/E.name
omit={'tmp','pytest-tmp','build-prerequisites','__pycache__','.pytest_cache'}
D.mkdir(parents=True,exist_ok=True)
for p in E.rglob('*'):
 if not p.is_file() or any(k in omit for k in p.relative_to(E).parts) or p.suffix=='.pyc':continue
 if p.name in {'postpush-verification.json','SHA256SUMS','publication-checks.json','staging-checks.json'}:continue
 q=D/p.relative_to(E);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
patterns={
 'github_token':rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})',
 'private_key':rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
 'aws_access_id':rb'AKIA[0-9A-Z]{16}',
 'openai_style':rb'sk-(?:proj-)?[A-Za-z0-9_-]{40,}',
 'telegram_bot_token':rb'(?<![0-9])[0-9]{8,12}:[A-Za-z0-9_-]{35}(?![A-Za-z0-9_-])',
}
files=sorted(p for p in D.rglob('*') if p.is_file())+[S/'docs/ASTRA_REVIEW_7638.md']
hits=[]
for p in files:
 for name,pat in patterns.items():
  if re.search(pat,p.read_bytes()):hits.append({'file':str(p.relative_to(S)),'pattern':name})
assert not hits,hits
checks=dict(scan='high-confidence credential patterns plus focused fixture/log inspection; not exhaustive',patterns=list(patterns),files_scanned=len(files),matches=hits,largest_bytes=max(p.stat().st_size for p in files),excluded=sorted(omit),target_remote='https://github.com/bgoertzel-sing/hive-appliance.git',target_branch='main',publication_scope=['docs/ASTRA_REVIEW_7638.md','experiments/20261008-astra-7638/'],test_result='746 passed; full suite exactly once',independent_result='15 assertion groups; four confirmed defect groups (2 High, 2 Medium)')
for base in (E,D):(base/'publication-checks.json').write_text(json.dumps(checks,indent=2)+'\n')
files=sorted(p for p in D.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(D))+'\n' for p in files)
report=S/'docs/ASTRA_REVIEW_7638.md';manifest+=hashlib.sha256(report.read_bytes()).hexdigest()+'  ../../docs/ASTRA_REVIEW_7638.md\n'
for base in (E,D):(base/'SHA256SUMS').write_text(manifest)
print(json.dumps(checks,indent=2))
