"""Read-only delivered evidence/report verification, with complete manifest coverage."""
import hashlib
from pathlib import Path
E=Path(__file__).resolve().parent
report=E.parent.parent/'docs/ASTRA_REVIEW_7669.md'
seen=set()
for line in (E/'SHA256SUMS').read_text().splitlines():
 expected,name=line.split('  ',1)
 p=(E/name).resolve()
 assert p.is_relative_to(E) or p==report,name
 assert p not in seen,name
 assert hashlib.sha256(p.read_bytes()).hexdigest()==expected,name
 seen.add(p)
actual={p.resolve() for p in E.rglob('*') if p.is_file() and p.name!='SHA256SUMS'}|{report}
assert seen==actual,dict(unmanifested=list(actual-seen),missing=list(seen-actual))
print('verified',len(seen),'artifact/report hashes; complete manifest coverage')
