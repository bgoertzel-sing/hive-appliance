"""Copy only this review's artifacts and manifest, no Git mutation."""
import hashlib,json,shutil
from pathlib import Path
E=Path(__file__).resolve().parent
R=Path('/home/openclaw/research-agent/projects/hive-appliance/repos/hive-appliance')
D=R/'experiments'/E.name;D.mkdir(exist_ok=True)
omit={'tmp','pytest-tmp','build-prerequisites','__pycache__','.pytest_cache'}
for p in E.rglob('*'):
 if not p.is_file() or any(k in omit for k in p.relative_to(E).parts) or p.suffix=='.pyc':continue
 if p.name in {'postpush-verification.json','SHA256SUMS','publication-checks.json'}:continue
 q=D/p.relative_to(E);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
checks=dict(scope=['docs/ASTRA_REVIEW_7701.md','experiments/20261008-astra-7701/'],excluded=sorted(omit),remote='https://github.com/bgoertzel-sing/hive-appliance.git',branch='main',fast_forward_only=True,gate='NOT APPROVED',suite='795 passed exactly once',primary='16 applicable groups completed, six retried for API adaptation',retained_focused='8 applicable groups completed, legacy/default retried',source_files=151,prior_manifest_hashes=[315,351,355],scan='scan_staged.py reads exact index bytes')
for base in [E,D]:(base/'publication-checks.json').write_text(json.dumps(checks,indent=2)+'\n')
files=sorted(p for p in D.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
report=R/'docs/ASTRA_REVIEW_7701.md'
manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(D))+'\n' for p in files)
manifest+=hashlib.sha256(report.read_bytes()).hexdigest()+'  ../../docs/ASTRA_REVIEW_7701.md\n'
for base in [E,D]:(base/'SHA256SUMS').write_text(manifest)
print(json.dumps(dict(hashes=len(files)+1,total_bytes=sum(p.stat().st_size for p in files),largest_bytes=max(p.stat().st_size for p in files),destination=str(D)),indent=2))
