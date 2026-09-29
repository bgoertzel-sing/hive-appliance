"""Seal the citation-corrected report and completed obligation without losing the initial seal."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

E = Path(__file__).resolve().parent
def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
prior = json.loads((E / 'final-integrity.json').read_text())
for line in (E / 'SHA256SUMS').read_text().splitlines():
    expected, name = line.split('  ', 1)
    if name != 'OBLIGATION.md':
        assert digest(E / name) == expected, name
for old, new in [('final-integrity.json', 'initial-integrity.json'),
                 ('SHA256SUMS', 'SHA256SUMS.initial')]:
    assert not (E / new).exists()
    (E / old).rename(E / new)
info = json.loads((E / 'environment.json').read_text())
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=info['worktree'])
prior['report_sha256'] = digest(E.parent.parent / 'docs/ASTRA_REVIEW_7195.md')
prior['acceptance_complete'] = True
prior['initial_seal_note'] = 'Preserved before report source-citation correction and obligation completion; no raw tests changed.'
excluded = {'source', 'tmp', 'pytest-tmp', 'relocation-smoke', '__pycache__'}
pattern = re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY|ghp_[A-Za-z0-9]{30,}|sk-proj-[A-Za-z0-9_-]{30,}')
hits = []
for p in E.rglob('*'):
    if p.is_file() and not p.is_symlink() and not (set(p.relative_to(E).parts) & excluded):
        if p.suffix in {'.py', '.json', '.md', '.stdout', '.stderr'} and pattern.search(p.read_bytes()):
            hits.append(str(p.relative_to(E)))
assert not hits, hits
prior['credential_pattern_scan'] = 'No matching private-key blocks or selected high-specificity token formats; not a universal secret detector.'
(E / 'final-integrity.json').write_text(json.dumps(prior, indent=2) + '\n')
files = [p for p in E.rglob('*') if p.is_file() and not p.is_symlink()
         and not (set(p.relative_to(E).parts) & excluded) and p.name != 'SHA256SUMS']
with (E / 'SHA256SUMS').open('x') as f:
    for p in sorted(files):
        f.write(digest(p) + '  ' + str(p.relative_to(E)) + '\n')
print(json.dumps(prior, indent=2))
