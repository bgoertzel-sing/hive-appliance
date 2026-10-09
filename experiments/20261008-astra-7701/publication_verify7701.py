"""Read-only assertion of final evidence accounting, beyond manifest checks."""
import json,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent
def read(n):return json.loads((E/n).read_text())
assert read('pytest-exit.json')['exit_code']==0
assert '795 passed in 48.55s' in (E/'pytest.stdout').read_text()
assert len(list(E.glob('pytest-started.json')))==1
a=read('review7694.json');r=read('retained-retry7701.json')
assert len(a)==16
assert all(v['passed'] or r[k]['passed'] for k,v in a.items())
b=read('followup7694.json');assert len(b)==8
assert all(v['passed'] or (k=='legacy_default' and read('legacy-final7701.json')['passed']) for k,v in b.items())
assert all(v['passed'] for v in read('focused7701.json').values())
for n in ['focused7701','clearance7701','performance7701','startup7701','observability7701','marker7701','static7701','legacy-final7701']:
 assert read(n+'-exit.json')['exit_code']==0,n
assert read('clearance7701.json')['injections']==64
assert read('startup7701.json')['injections']==48
assert len(read('policy-schedules.json'))==1440
assert r['retained_hold_144_schedules']['schedules']==144
assert read('source-verification.json')['tracked_non_experiment_files']==151
assert read('model-verification.json')['final_check']['model']=='gpt-6-astra'
subprocess.run(['python3',str(E/'verify_evidence.py')],check=True)
print('final suite/retained/focused/model/source accounting verified; gate remains NOT APPROVED')
