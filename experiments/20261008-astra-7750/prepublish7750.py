"""Final fetch and pinned-source immutability check before publication."""
import subprocess,json,hashlib
from pathlib import Path
from runner import E,S
R=E.parent.parent;subprocess.run(['git','fetch','origin'],cwd=R,check=True)
git=lambda *a:subprocess.check_output(['git',*a],cwd=R).decode().strip()
b=json.loads((E/'source-verification-before.json').read_text());head=git('rev-parse','HEAD');remote=git('rev-parse','origin/main')
assert head==remote==b['pin'],dict(head=head,origin_main=remote,reviewed=b['pin'])
for f,digest in b['hashes'].items():
 assert hashlib.sha256((S/f).read_bytes()).hexdigest()==digest==hashlib.sha256((R/f).read_bytes()).hexdigest(),f
result=dict(pin=b['pin'],head=head,origin_main=remote,extra_code=False,files=len(b['hashes']),repository_source_unchanged=True,export_unchanged=True,git_status=git('status','--short'),branch=git('branch','--show-current'),publication_scope=['docs/ASTRA_REVIEW_7750.md','experiments/20261008-astra-7750/'],push_policy='main fast-forward only; explicitly authorized by task')
(E/'source-verification-precommit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
