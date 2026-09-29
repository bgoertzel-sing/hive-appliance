"""Verify pin and evidence, then create portable source and integrity manifests."""
import difflib
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile

E = Path(__file__).resolve().parent
def read(name):
    return json.loads((E / name).read_text())
def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name, value):
    with (E / name).open('x') as f:
        json.dump(value, f, indent=2)
        f.write('\n')

info = read('environment.json')
repo = Path(info['worktree'])
manifest = read('source-sha256.json')
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip() == info['pin']
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo)
assert all(digest(repo / name) == h == digest(E / 'source' / name) for name, h in manifest.items())
for c, data in read('baseline-provenance.json').items():
    assert digest(E / ('legacy-reducer-' + c + '.py')) == data['sha256']
adaptations = []
for name, data in read('copy-provenance.json').items():
    original = repo / data['source']
    assert digest(original) == data['sha256']
    if digest(E / name) != data['sha256']:
        assert name == 'review7173.py'
        adaptations.extend(difflib.unified_diff(original.read_text().splitlines(True),
            (E / name).read_text().splitlines(True), fromfile='pinned7173/' + name, tofile='review7195/' + name))
with (E / 'adaptation.diff').open('x') as f:
    f.write(''.join(adaptations))

assert read('pytest-exit.json')['exit_code'] == 1 and not read('pytest-exit.json')['timed_out']
pytest = (E / 'pytest.stdout').read_text()
assert '698 passed' in pytest and '1 failed' in pytest
assert 'No matching distribution found for setuptools>=61' in pytest
assert len(re.findall(r'^tests/test_astra7173.py::.* PASSED', pytest, re.M)) == 6
assert read('review7195-summary.json') == dict(groups=7, passed=7, failed=[])
assert read('review7173-summary.json') == dict(total=10, passed=10, failed=[])
assert len(read('review7195.json')['n9_per_receipt_overwritten_and_unchanged']['cases']) == 64
assert len(read('probes-result.json')) == 14 and all(r['probe'] == 'PASS' for r in read('probes-result.json'))
assert len(read('older-regressions.json')) == 2 and all(r['probe'] == 'PASS' for r in read('older-regressions.json'))
assert read('results-audit.json')['explicit_disk_recovery_passes'] == 6
reloc = E / 'relocation-smoke'
def relocated(name):
    return json.loads((reloc / name).read_text())
for name in ['semantic-summary.json', 'review7173-summary.json', 'review7195-summary.json', 'new-cases-summary.json']:
    assert read(name) == relocated(name)
for name in ['adversarial', 'adversarial-inverted', 'new-cases', 'supplementary', 'probes',
             'older-regressions', 'independent', 'semantic-7133', 'boundary-and-disk',
             'mechanism-probes', 'review7173', 'review7195']:
    assert read(name + '-exit.json')['exit_code'] == relocated(name + '-exit.json')['exit_code']
assert not (reloc / 'pytest-started.json').exists()
with tarfile.open(E / 'source.tar.gz', 'x:gz') as archive:
    for name in sorted(manifest):
        archive.add(E / 'source' / name, arcname='source/' + name, recursive=False)
report = E.parent.parent / 'docs/ASTRA_REVIEW_7195.md'
assert report.is_file()
save('final-integrity.json', dict(pin=info['pin'], worktree_clean=True,
    source_files_verified=len(manifest), baseline_modules_verified=4,
    adapted_helpers=['review7173.py'], report_sha256=digest(report),
    source_archive_sha256=digest(E / 'source.tar.gz'),
    probe_relocation_matches=True, full_pytest_invocations=1,
    no_production_edits=True, no_old_evidence_edits=True))
excluded = {'source', 'tmp', 'pytest-tmp', 'relocation-smoke', '__pycache__'}
files = [p for p in E.rglob('*') if p.is_file() and not p.is_symlink()
         and not (set(p.relative_to(E).parts) & excluded) and p.name != 'SHA256SUMS']
with (E / 'SHA256SUMS').open('x') as f:
    for p in sorted(files):
        f.write(digest(p) + '  ' + str(p.relative_to(E)) + '\n')
print(json.dumps(read('final-integrity.json'), indent=2))
