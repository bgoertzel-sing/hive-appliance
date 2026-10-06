from pathlib import Path
import shutil,hashlib,json,difflib,sys
from run_review import E,run
P=E.parent/'20260928-astra-7195'
prov=json.loads((E/'copy-provenance.json').read_text())
for name in ['new_cases.py','semantic_7133.py']:
 raw=(P/name).read_bytes();(E/name).write_bytes(raw)
 prov[name]=dict(source='20260928-astra-7195/'+name,original_sha256=hashlib.sha256(raw).hexdigest())
 if name=='new_cases.py':
  old=raw.decode();lines=old.splitlines(True)
  new="".join(line.replace(",[1]*7+[0,0])",",[1]*6+[0,0,0])") if line.startswith("run('two_plans_one_incident_failure'") else line for line in lines)
  assert old!=new
  (E/name).write_text(new)
  (E/'adaptation.diff').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='7195/new_cases.py',tofile='7519/new_cases.py')))
 prov[name]['sha256']=hashlib.sha256((E/name).read_bytes()).hexdigest()
(E/'copy-provenance.json').write_text(json.dumps(prov,indent=2)+'\n')
for name in ['new_cases','semantic_7133']:run(name.replace('_','-'),[sys.executable,str(E/(name+'.py'))])
