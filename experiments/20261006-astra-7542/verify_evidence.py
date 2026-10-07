"""Verify curated artifact manifest, source/helper hashes and report binding."""
from pathlib import Path
import hashlib,json
E=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest={}
for line in (E/'SHA256SUMS').read_text().splitlines():
 h,n=line.split('  ',1);manifest[n]=h
 assert sha(E/n)==h, n
actual={str(p.relative_to(E)) for p in E.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in ['SHA256SUMS','final-integrity.json']}
assert actual==set(manifest),(actual-set(manifest),set(manifest)-actual)
for n,h in json.loads((E/'source-sha256.json').read_text()).items():assert sha(E/'source'/n)==h,n
for n,v in json.loads((E/'copy-provenance.json').read_text()).items():assert sha(E/n)==v['sha256'],n
f=json.loads((E/'final-integrity.json').read_text());assert sha(E/'SHA256SUMS')==f['manifest_sha256']
report=E.parents[1]/'docs/ASTRA_REVIEW_7542.md'
assert sha(report)==f['report_sha256']
print(json.dumps(dict(verified=True,artifacts=len(manifest),source_pin=f['source_pin'],report_sha256=f['report_sha256'])))
