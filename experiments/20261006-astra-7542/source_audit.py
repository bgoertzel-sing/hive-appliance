import subprocess, json, hashlib
from pathlib import Path
E=Path(__file__).resolve().parent;R=E.parents[1]/'repos/hive-astra-7542'
commands=[['git','remote','-v'],['git','status','--short','--branch'],['git','branch','--show-current'],['git','log','-5','--oneline','--decorate'],['git','rev-parse','HEAD','origin/main'],['git','log','--oneline','--follow','--','tests/test_p0_fixes.py'],['git','show','0744154:tests/test_p0_fixes.py'],['git','diff','--stat','c876525..85c505d']]
rows=[]
for cmd in commands:
 p=subprocess.run(cmd,cwd=R,capture_output=True,text=True);assert p.returncode==0
 rows.append(dict(command=cmd,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr))
(E/'git-source-audit.json').write_text(json.dumps(rows,indent=2)+'\n')
manifest=json.loads((E/'source-sha256.json').read_text())
assert all(hashlib.sha256((E/'source'/n).read_bytes()).hexdigest()==h for n,h in manifest.items())
assert all(hashlib.sha256((R/n).read_bytes()).hexdigest()==h for n,h in manifest.items())
# Verify all retained prior helper bytes have remained unchanged.
prov=json.loads((E/'copy-provenance.json').read_text())
assert all(hashlib.sha256((E/n).read_bytes()).hexdigest()==v['sha256'] for n,v in prov.items())
print(json.dumps(dict(source_files_verified=len(manifest),helpers_verified=len(prov),source_pin='85c505d1608680f1ac965ad5fad46a573c032b35',git_commands=len(rows))))
