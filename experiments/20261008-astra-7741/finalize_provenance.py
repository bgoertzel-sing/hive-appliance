"""Record all inherited harnesses and final adaptations, plus exact output inventory."""
from pathlib import Path
import hashlib,json,difflib
E=Path(__file__).resolve().parent;R=E.parent.parent;P=E.parent/'20261008-astra-7734';rows=[];diff=[]
for p in sorted(list(P.glob('*.py'))+list((P/'guard').glob('*.py'))):
 if p.name.startswith('setup'):continue
 rel=p.relative_to(P);q=E/rel;old=p.read_text();new=q.read_text()
 rows.append(dict(source=str(p.relative_to(R)),destination=str(rel),source_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),adapted_sha256=hashlib.sha256(q.read_bytes()).hexdigest()))
 diff+=list(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile=str(p.relative_to(R)),tofile=str(q.relative_to(R))))
(E/'copy-provenance.json').write_text(json.dumps(rows,indent=2)+'\n');(E/'adaptation-7741.diff').write_text(''.join(diff))
print('inherited Python harnesses',len(rows))
