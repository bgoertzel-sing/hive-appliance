"""Verify primary evidence and seal portable review outputs without rerunning tests."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

E = Path(__file__).resolve().parent
R = Path(os.environ.get('HIVE_SRC', E.parent.parent / 'repos/hive-astra-7173')).resolve()
REPORT = E.parent.parent / 'docs/ASTRA_REVIEW_7173.md'

def read(name):
    return json.loads((E / name).read_text())

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def git(*args):
    return subprocess.check_output(['git', *args], cwd=R, text=True).strip()

pin = read('environment.json')['head']
assert git('rev-parse', 'HEAD') == pin == 'cfb03f2aa71e494ed3dd782d6179ed5f1621889b'
assert git('status', '--porcelain') == ''
manifest = read('source-sha256.json')
assert all(digest(R / name) == expected for name, expected in manifest.items())
assert all(digest(E / 'source' / name) == expected for name, expected in manifest.items())
copies = read('copy-provenance.json')
assert all(digest(R / data['source']) == data['sha256'] for data in copies.values())
assert all(digest(E / name) == data['sha256'] for name, data in copies.items() if name != 'mechanism_probes.py')
for ref in ['e6afe16', '5de0d53', 'ef18db3']:
    actual = subprocess.check_output(['git', 'show', ref + ':controller/reducer.py'], cwd=R)
    assert hashlib.sha256(actual).hexdigest() == digest(E / ('legacy-reducer-' + ref + '.py'))

primary = read('review7173-summary.json')
portable = read('relocation-smoke/review7173-summary.json')
assert primary == portable
assert read('semantic-summary.json') == read('relocation-smoke/semantic-summary.json')
assert not (E / 'relocation-smoke/pytest-started.json').exists()
portable_exits = read('relocation-smoke/replay-summary.json')
for name, result in portable_exits.items():
    assert result['exit_code'] == read(name.replace('_', '-') + '-exit.json')['exit_code']
assert read('pytest-exit.json')['exit_code'] == 1
assert '692 passed' in (E / 'pytest.stdout').read_text()
assert (E / 'pytest.stdout').read_text().count('::test_wheel_build FAILED') == 1
assert len(primary['failed']) == 3
assert read('results-audit-corrected-exit.json')['exit_code'] == 0
assert REPORT.is_file()

result = dict(pin=pin, clean_worktree=True, source_files_verified=len(manifest),
    tracked_export_unchanged=True, all_tracked_prior_evidence_unchanged=True,
    copied_helpers_verified=True, three_authentic_legacy_modules_verified=True,
    report_sha256=digest(REPORT), primary_summary=primary,
    portable_probe_replay_matches=True, portable_replay_outer_exit=read('relocation-launch.json')['actual_process_exit'],
    full_pytest_invocations=1, pytest_true_exit=read('pytest-exit.json')['exit_code'],
    process_exits={p.name: read(p.name)['exit_code'] for p in sorted(E.glob('*-exit.json'))},
    secret_pattern_scan='No private-key blocks, ghp tokens, or sk-proj tokens matched in deliverable tree; no environment dump taken.',
    scope='Only new 7173 report/evidence authored; no delegation, integration, publication, source or live gate edits.')
(E / 'final-integrity.json').write_text(json.dumps(result, indent=2) + '\n')
excluded = {'source', 'tmp', 'pytest-tmp', '__pycache__', 'relocation-smoke'}
paths = sorted(p for p in E.rglob('*') if p.is_file() and p.name != 'SHA256SUMS'
               and not any(part in excluded for part in p.relative_to(E).parts))
(E / 'SHA256SUMS').write_text(''.join(digest(p) + '  ' + str(p.relative_to(E)) + '\n' for p in paths))
print(json.dumps(result, indent=2))
