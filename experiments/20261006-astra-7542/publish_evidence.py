"""Curate a byte-identical evidence copy and bind it to the report; no Git writes."""
import hashlib,json,re,shlex,shutil,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent;R=E.parents[1]/'repos/hive-astra-7542';D=R/'experiments'/E.name
report=R/'docs/ASTRA_REVIEW_7542.md'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
source=json.loads((E/'source-sha256.json').read_text())
for n,h in source.items():assert sha(E/'source'/n)==h==sha(R/n),n
for n,v in json.loads((E/'copy-provenance.json').read_text()).items():assert sha(E/n)==v['sha256'],n
starts=[json.loads(p.read_text()) for p in E.glob('*-started.json')];starts.sort(key=lambda r:r['started'])
(E/'commands.sh').write_text('#!/bin/sh\n# Exact recorded child invocations, in launch order; NOT an overwrite-safe replay script.\n# Use replay.py for reproduction into a new directory.\n'+''.join('\n(cd '+shlex.quote(r['cwd'])+' && '+shlex.join(r['command'])+')\n' for r in starts))
for start in E.glob('*-started.json'):
 label=start.name.removesuffix('-started.json')
 for suffix in ['-exit.json','.stdout','.stderr']:assert (E/(label+suffix)).exists()
def selected():
 for p in sorted(E.rglob('*')):
  if not p.is_file():continue
  rel=p.relative_to(E)
  if rel.parts[0] in ['tmp','pytest-tmp'] or '__pycache__' in rel.parts or p.suffix=='.pyc':continue
  if rel.parts[0]=='source' and str(Path(*rel.parts[1:])) not in source:continue
  if p.name in ['SHA256SUMS','final-integrity.json','prepush-validation.json']:continue
  yield p
files=list(selected())
patterns={
 'github_token':r'\bgh[pousr]_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{30,}\b',
 'openai_style_token':r'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{35,}\b',
 'aws_access_key':r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
 'private_key':r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
 'slack_token':r'\bxox[baprs]-[A-Za-z0-9-]{20,}\b',
 'credential_url':r'https?://[^\s/:@]+:[^\s/@]+@[^\s/]+',
}
hits=[]
for p in files+[report]:
 text=p.read_bytes().decode('utf8',errors='replace')
 for label,pat in patterns.items():
  for m in re.finditer(pat,text):hits.append(dict(path=str(p.relative_to(E)) if p!=report else 'docs/ASTRA_REVIEW_7542.md',kind=label,line=text.count('\n',0,m.start())+1))
assert not hits,hits
base=subprocess.check_output(['git','rev-parse','origin/main'],cwd=R,text=True).strip()
val=dict(source_pin='85c505d1608680f1ac965ad5fad46a573c032b35',fetched_origin_main=base,source_files_verified=len(source),helper_files_verified=len(json.loads((E/'copy-provenance.json').read_text())),child_invocations_with_complete_records=len(starts),secret_scan=dict(method='high-confidence token/private-key/credential-URL regex',patterns=patterns,files_scanned=len(files)+1,hits=hits,limitation='Pattern scan, not a credential authenticity test; inherited public fixtures and deliberate local paths retained.'),allowed_changes=['docs/ASTRA_REVIEW_7542.md','experiments/20261006-astra-7542/'],full_suite_runs=1)
(E/'prepush-validation.json').write_text(json.dumps(val,indent=2)+'\n')
files=list(selected())+[E/'prepush-validation.json']
manifest=''.join(sha(p)+'  '+str(p.relative_to(E))+'\n' for p in sorted(files))
(E/'SHA256SUMS').write_text(manifest)
final=dict(source_pin=val['source_pin'],report_sha256=sha(report),manifest_sha256=sha(E/'SHA256SUMS'),artifact_count=len(files),status='completed; findings and limitations in report')
(E/'final-integrity.json').write_text(json.dumps(final,indent=2)+'\n')
D.mkdir(parents=True,exist_ok=False)
for p in files+[E/'SHA256SUMS',E/'final-integrity.json']:
 dst=D/p.relative_to(E);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst);assert sha(dst)==sha(p)
print(json.dumps(dict(copied=len(files)+2,bytes=sum(p.stat().st_size for p in files),source_files=len(source),secret_pattern_hits=0,report_sha256=sha(report),origin_main=base)))
