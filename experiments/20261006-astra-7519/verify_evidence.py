from pathlib import Path
import hashlib,json
E=Path(__file__).resolve().parent
for line in (E/'SHA256SUMS').read_text().splitlines():
 digest,name=line.split('  ',1)
 assert hashlib.sha256((E/name).read_bytes()).hexdigest()==digest,name
for name,digest in json.loads((E/'source-sha256.json').read_text()).items():
 assert hashlib.sha256((E/'source'/name).read_bytes()).hexdigest()==digest,name
report=E.parent.parent/'docs/ASTRA_REVIEW_7519.md'
if report.exists():assert hashlib.sha256(report.read_bytes()).hexdigest()==json.loads((E/'final-integrity.json').read_text())['report_sha256']
print('All published evidence and source hashes verified; report verified when adjacent.')
