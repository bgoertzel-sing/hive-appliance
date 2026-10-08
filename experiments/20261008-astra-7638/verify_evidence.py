"""Read-only verification of the delivered evidence and report bytes."""
import hashlib
from pathlib import Path
E=Path(__file__).resolve().parent
count=0
for line in (E/'SHA256SUMS').read_text().splitlines():
 expected,name=line.split('  ',1)
 p=(E/name).resolve()
 assert p.is_relative_to(E) or p==E.parent.parent/'docs/ASTRA_REVIEW_7638.md',name
 actual=hashlib.sha256(p.read_bytes()).hexdigest()
 assert actual==expected,name
 count+=1
print('verified',count,'artifact/report hashes')
