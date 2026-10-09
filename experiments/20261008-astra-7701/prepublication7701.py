"""Record source/remote/staging isolation immediately before publication."""
import subprocess,json,hashlib
from pathlib import Path
E=Path(__file__).resolve().parent
R=Path('/home/openclaw/research-agent/projects/hive-appliance/repos/hive-appliance')
S=Path('/tmp/hive-astra-7701-source')
def git(*a):return subprocess.check_output(['git',*a],cwd=R).decode()
pin='865fd633bc53561aea140dc3f43fee72b8fd61ee'
assert git('branch','--show-current').strip()=='main'
assert git('rev-parse','HEAD').strip()==pin==git('rev-parse','origin/main').strip()
assert not git('diff','--cached','--name-only')
changed=git('diff','--name-only').splitlines()
assert all(x=='docs/ASTRA_REVIEW_7701.md' or x.startswith('experiments/20261008-astra-7701/') for x in changed)
before=json.loads((E/'source-verification-before.json').read_text())
assert all(hashlib.sha256((S/p).read_bytes()).hexdigest()==h for p,h in before.items())
assert subprocess.check_output(['git','status','--porcelain'],cwd=S)==b''
(E/'prepublication-git.json').write_text(json.dumps(dict(head=pin,origin_main=pin,branch='main',remote=git('remote','get-url','origin').strip(),status=git('status','--short'),initial_index_empty=True,source_reverified_files=len(before),scope='Only report and new evidence; scratch left alone',publication_intent='One review/evidence commit to origin/main, fast-forward only; 795 suite passed exactly once; production gate NOT APPROVED'),indent=2)+'\n')
print('source, remote, index and scope checked')
