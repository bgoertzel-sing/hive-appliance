"""Review-only runner. Exclusive logs prevent accidental evidence overwrite."""
import argparse
import hashlib
import importlib.metadata as md
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import time

E = Path(__file__).resolve().parent
S = Path(os.environ.get('HIVE_SRC', E / 'source')).resolve()
NAMES = ['adversarial', 'adversarial-inverted', 'new_cases', 'supplementary',
         'probes', 'older-regressions', 'independent', 'semantic_7133',
         'boundary_and_disk', 'mechanism_probes', 'review7173']

def save(name, obj):
    with (E / name).open('x') as f:
        json.dump(obj, f, indent=2, default=str)
        f.write('\n')

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def env():
    e = os.environ.copy()
    e.update(PYTHONDONTWRITEBYTECODE='1', PIP_NO_INDEX='1', HF_HUB_OFFLINE='1',
             TRANSFORMERS_OFFLINE='1', ANONYMIZED_TELEMETRY='False',
             PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', TMPDIR=str(E / 'tmp'),
             PYTHONPATH=str(E / 'guard'), HIVE_SRC=str(S))
    return e

def run(name, command, cwd=None, timeout=600):
    (E / 'tmp').mkdir(exist_ok=True)
    start = time.time()
    save(name + '-started.json', dict(command=command, cwd=str(cwd or E), started=start))
    timed_out = False
    with (E / (name + '.stdout')).open('x') as out, (E / (name + '.stderr')).open('x') as err:
        p = subprocess.Popen(command, cwd=cwd or E, env=env(), stdout=out, stderr=err,
                             start_new_session=True)
        try:
            rc = p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(p.pid, signal.SIGKILL)
            rc = p.wait()
    result = dict(command=command, cwd=str(cwd or E), exit_code=rc,
                  timed_out=timed_out, wall_seconds=time.time()-start)
    save(name + '-exit.json', result)
    print(name, json.dumps(result), flush=True)
    return result

def prepare(repo):
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=repo)
    pin = git('rev-parse', 'HEAD').decode().strip()
    assert pin == git('rev-parse', 'f1736e5').decode().strip()
    assert not git('status', '--porcelain')
    S.mkdir(exist_ok=False)
    manifest = {}
    for name in filter(None, git('ls-files', '-z').decode().split('\0')):
        src, dst = repo / name, S / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        manifest[name] = digest(src)
    save('source-sha256.json', manifest)
    prior = repo / 'experiments/20260928-astra-7173'
    provenance = {}
    for name in [n + '.py' for n in NAMES] + ['legacy-reducer-e6afe16.py',
            'legacy-reducer-5de0d53.py', 'legacy-reducer-ef18db3.py', 'audit_results.py']:
        shutil.copy2(prior / name, E / name)
        provenance[name] = dict(source=str((prior / name).relative_to(repo)), commit=pin,
                                sha256=digest(E / name))
    save('copy-provenance.json', provenance)
    baseline = {}
    for c in ['e6afe16', '5de0d53', 'ef18db3', 'cfb03f2']:
        raw = git('show', c + ':controller/reducer.py')
        target = E / ('legacy-reducer-' + c + '.py')
        if target.exists():
            assert target.read_bytes() == raw
        else:
            target.write_bytes(raw)
        baseline[c] = dict(commit=git('rev-parse', c).decode().strip(),
                           path='controller/reducer.py', sha256=digest(target))
    save('baseline-provenance.json', baseline)
    versions = {}
    for name in ['pytest', 'build', 'setuptools', 'wheel', 'chromadb', 'onnxruntime']:
        try:
            versions[name] = md.version(name)
        except md.PackageNotFoundError:
            versions[name] = None
    save('environment.json', dict(pin=pin, base=git('rev-parse', 'cfb03f2').decode().strip(),
         python=sys.version, executable=sys.executable, platform=platform.platform(),
         versions=versions, worktree=str(repo), status=git('status', '--porcelain').decode(),
         reviewer='gpt-6-astra explicitly selected; parent owns routing verification'))
    (E / 'production.diff').write_bytes(git('diff', 'cfb03f2..f1736e5', '--', 'controller', 'hive'))
    (E / 'tests.diff').write_bytes(git('diff', 'cfb03f2..f1736e5', '--', 'tests'))
    keys = ['PYTHONDONTWRITEBYTECODE', 'PIP_NO_INDEX', 'HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE',
            'ANONYMIZED_TELEMETRY', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD', 'TMPDIR', 'PYTHONPATH', 'HIVE_SRC']
    save('environment-overrides.json', {k: env()[k] for k in keys})

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', type=Path)
    parser.add_argument('--only', choices=['pytest', 'prior', 'new', 'audit'])
    a = parser.parse_args()
    if a.prepare:
        prepare(a.prepare.resolve())
    if a.only == 'pytest':
        r = run('pytest', [sys.executable, '-m', 'pytest', 'tests/', '-v', '-p', 'no:cacheprovider',
                          '--basetemp=' + str(E / 'pytest-tmp')], S)
        sys.exit(r['exit_code'])
    if a.only == 'prior':
        for name in NAMES:
            run(name.replace('_', '-'), [sys.executable, str(E / (name + '.py'))])
    if a.only in ['new', 'audit']:
        name = 'review7195' if a.only == 'new' else 'audit_results'
        sys.exit(run(name, [sys.executable, str(E / (name + '.py'))])['exit_code'])
