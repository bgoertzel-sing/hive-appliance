"""Content scan of report and regular evidence files, without printing matched values."""
import re,json
from pathlib import Path
E=Path(__file__).resolve().parent;report=E.parent.parent/'docs/ASTRA_REVIEW_7741.md'
patterns={
 'private-key':rb'-----BEGIN [A-Z ]*PRIVATE'+rb' KEY-----',
 'provider-secret':rb'\bsk-'+rb'(?:proj-|ant-)?[A-Za-z0-9_-]{24,}',
 'github-secret':rb'\bgh[pousr]_'+rb'[A-Za-z0-9]{30,}',
 'cloud-access-key':rb'\bAKIA'+rb'[A-Z0-9]{16}\b',
 'bot-credential':rb'\b[0-9]{7,12}:'+rb'[A-Za-z0-9_-]{30,}\b',
 'credential-assignment':rb'(?i)(?:api_key|access_token|auth_token|password|client_secret)\s*[=:]\s*[\x22\x27]'+rb'[A-Za-z0-9_+/=.-]{24,}[\x22\x27]',
}
files=sorted(p for p in E.rglob('*') if p.is_file() and not p.is_symlink() and p.name not in ['SHA256SUMS','secret-scan.json']);files.append(report);matches=[];total=0
for p in files:
 b=p.read_bytes();total+=len(b)
 for kind,pat in patterns.items():
  if re.search(pat,b):matches.append(dict(path=str(p.relative_to(E)) if p.is_relative_to(E) else '../../docs/'+p.name,pattern=kind))
result=dict(scope='Report plus every regular evidence file present at scan; no symlink following; excludes generated scan-result JSON and hash manifest',files=len(files),bytes=total,patterns=list(patterns),matches=matches,passed=not matches,limitation='High-signal credential-pattern scan, not a proof that arbitrary encoded secrets cannot exist')
(E/'secret-scan.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));assert not matches
