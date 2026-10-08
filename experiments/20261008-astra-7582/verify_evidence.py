"""Verify published artifact hashes, pinned source, copied helpers and report."""
import hashlib,json
from pathlib import Path
E=Path(__file__).resolve().parent
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=(E/'SHA256SUMS').read_text().splitlines()
for line in rows:
 expected,name=line.split('  ',1);assert digest(E/name)==expected,name
for name,expected in json.loads((E/'source-sha256.json').read_text()).items():assert digest(E/'source'/name)==expected,name
for name,rec in json.loads((E/'copy-provenance.json').read_text()).items():assert digest(E/name)==rec['sha256'],name
f=json.loads((E/'final-integrity.json').read_text());assert digest(E/'SHA256SUMS')==f['manifest_sha256'];assert digest(E.parent.parent/'docs/ASTRA_REVIEW_7582.md')==f['report_sha256'];assert f['reviewed_pin']=='4d5fdff7902963b2d07329e959f938451a109107'
print('Verified',len(rows),'artifacts, source/helper hashes and report.')
