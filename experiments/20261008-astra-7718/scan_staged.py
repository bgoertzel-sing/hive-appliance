"""Read index blobs, enforce publication scope and high-confidence secret scan."""
import json,re,subprocess,sys
from pathlib import Path
R=Path('/home/openclaw/research-agent/projects/hive-appliance/repos/hive-appliance');E=Path(__file__).resolve().parent
files=subprocess.check_output(['git','diff','--cached','--name-only','-z'],cwd=R).decode().split('\0');files=[f for f in files if f]
assert files and all(f=='docs/ASTRA_REVIEW_7718.md' or f.startswith('experiments/20261008-astra-7718/') for f in files)
patterns={'github_token':rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})','private_key':rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----','aws_access_id':rb'AKIA[0-9A-Z]{16}','openai_style':rb'sk-(?:proj-)?[A-Za-z0-9_-]{40,}','telegram_bot_token':rb'(?<![0-9])[0-9]{8,12}:[A-Za-z0-9_-]{35}(?![A-Za-z0-9_-])'}
hits=[];largest=0
for f in files:
 data=subprocess.check_output(['git','show',':'+f],cwd=R);largest=max(largest,len(data))
 for name,p in patterns.items():
  if re.search(p,data):hits.append(dict(file=f,pattern=name))
assert not hits,hits
result=dict(scope_only_report_and_new_evidence=True,staged_files=len(files),patterns=list(patterns),matches=hits,largest_staged_blob=largest,scan='Exact staged index bytes, not just worktree; high-confidence patterns, not exhaustive')
if '--write' in sys.argv:(E/'staging-checks.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
