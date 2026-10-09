"""Read-only final scope and authored whitespace review; record evidence checks."""
import json,subprocess
from pathlib import Path
R=Path('/home/openclaw/research-agent/projects/hive-appliance/repos/hive-appliance');E=Path(__file__).resolve().parent
def run(args):return subprocess.run(args,cwd=R,text=True,capture_output=True)
raw=run(['git','diff','--cached','--check'])
(E/'staged-whitespace.stdout').write_text(raw.stdout)
authored=['docs/ASTRA_REVIEW_7694.md']+['experiments/20261008-astra-7694/'+x for x in ['README.md','RUN.md','static7694.py','clearance7694.py','publish_evidence.py','verify_evidence.py','prepublication7694.py','publication_verify7694.py','archive_sources7694.py','scan_staged.py']]
p=run(['git','diff','--cached','--check','--',*authored]);assert p.returncode==0,p.stdout
files=run(['git','diff','--cached','--name-only']).stdout.splitlines()
assert all(x=='docs/ASTRA_REVIEW_7694.md' or x.startswith('experiments/20261008-astra-7694/') for x in files)
assert run(['git','diff','--name-only']).stdout==''
data=dict(raw_whitespace_exit=raw.returncode,raw_whitespace_notes='Only preserved stdout, corrupt-byte fixtures, archived source/patch and inherited runner blank lines; do not normalize forensic artifacts.',authored_whitespace_exit=p.returncode,scope_only_report_evidence=True,staged_files=len(files),scratch_untracked=True)
(E/'publication-verification.json').write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps(data,indent=2))
