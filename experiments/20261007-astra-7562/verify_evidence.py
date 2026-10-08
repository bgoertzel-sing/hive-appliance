"""Verify published evidence, tracked source, copied helpers and report bytes."""
import hashlib,json
from pathlib import Path
E=Path(__file__).resolve().parent

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=(E/'SHA256SUMS').read_text().splitlines()
for line in rows:
 expected,name=line.split('  ',1);assert digest(E/name)==expected,name
for name,expected in json.loads((E/'source-sha256.json').read_text()).items():
 assert digest(E/'source'/name)==expected,name
for name,rec in json.loads((E/'copy-provenance.json').read_text()).items():
 assert digest(E/name)==rec['sha256'],name
final=json.loads((E/'final-integrity.json').read_text())
assert digest(E/'SHA256SUMS')==final['manifest_sha256']
assert digest(E.parent.parent/'docs/ASTRA_REVIEW_7562.md')==final['report_sha256']
assert final['reviewed_pin']=='57a62987a8e46fe2fdf45d63c1a9c148d3e12fbd'
print('Verified',len(rows),'artifacts, all source/helper hashes, and report.')
