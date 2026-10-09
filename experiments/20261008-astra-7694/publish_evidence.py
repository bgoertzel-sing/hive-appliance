"""Copy report/evidence scope and build a complete manifest; no git writes."""
import hashlib,json,shutil
from pathlib import Path
E=Path(__file__).resolve().parent
R=Path('/home/openclaw/research-agent/projects/hive-appliance/repos/hive-appliance')
D=R/'experiments'/E.name;D.mkdir(parents=True,exist_ok=True)
omit={'tmp','pytest-tmp','build-prerequisites','__pycache__','.pytest_cache'}
for p in E.rglob('*'):
 if not p.is_file() or any(k in omit for k in p.relative_to(E).parts) or p.suffix=='.pyc':continue
 if p.name in {'postpush-verification.json','SHA256SUMS','publication-checks.json'}:continue
 q=D/p.relative_to(E);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
report=R/'docs/ASTRA_REVIEW_7694.md'
checks=dict(scope=['docs/ASTRA_REVIEW_7694.md','experiments/20261008-astra-7694/'],excluded=sorted(omit),remote='https://github.com/bgoertzel-sing/hive-appliance.git',branch='main',gate='NOT APPROVED',full_suite='785 passed exactly once',primary_groups='16/16',focused_groups='12/12 includes asserted defects',source_files=149,prior_manifest_hashes=[315,351],scan='scan_staged.py verifies exact index bytes; see staging-checks.json')
for base in (E,D):(base/'publication-checks.json').write_text(json.dumps(checks,indent=2)+'\n')
files=sorted(p for p in D.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(D))+'\n' for p in files)
manifest+=hashlib.sha256(report.read_bytes()).hexdigest()+'  ../../docs/ASTRA_REVIEW_7694.md\n'
for base in (E,D):(base/'SHA256SUMS').write_text(manifest)
print(json.dumps(dict(files=len(files)+1,largest_bytes=max(p.stat().st_size for p in files),total_bytes=sum(p.stat().st_size for p in files),target=str(D)),indent=2))
