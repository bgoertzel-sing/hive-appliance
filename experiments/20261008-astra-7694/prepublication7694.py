"""Read exact Git state before publication; do not modify repository."""
import json,subprocess
from pathlib import Path
R=Path('/home/openclaw/research-agent/projects/hive-appliance/repos/hive-appliance');E=Path(__file__).resolve().parent
def git(*args):return subprocess.check_output(['git',*args],cwd=R,text=True)
head=git('rev-parse','HEAD').strip();remote=git('rev-parse','origin/main').strip()
assert head==remote=='cf6a0601ddc03dcd87daab7f982cb97361ac7ee8'
assert git('branch','--show-current').strip()=='main'
assert git('diff','--cached','--name-only')==''
data=dict(head=head,origin_main=remote,branch=git('branch','--show-current').strip(),status_porcelain_v1=git('status','--porcelain=v1'),status_branch=git('status','--short','--branch'),remotes=git('remote','-v'),last_five=git('log','-5','--oneline','--decorate'),tracked_diff=git('diff','--stat'),index_diff=git('diff','--cached','--stat'),publication_scope=['docs/ASTRA_REVIEW_7694.md','experiments/20261008-astra-7694/'],fast_forward_base_verified=True,postpush_record_outside_manifest='/tmp/hive-astra-7694/postpush-verification.json')
(E/'prepublication-git.json').write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps(data,indent=2))
