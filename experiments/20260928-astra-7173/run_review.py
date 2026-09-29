"""Portable review launcher. Never repeat pytest in an existing evidence tree."""
import difflib
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
R = Path(os.environ.get('HIVE_SRC', E.parent.parent / 'repos/hive-astra-7173')).resolve()
S = E / 'source'
PRIOR = R / 'experiments/20260928-astra-7160'
NAMES = ['adversarial', 'adversarial-inverted', 'new_cases', 'supplementary',
         'probes', 'older-regressions', 'independent', 'semantic_7133',
         'boundary_and_disk', 'mechanism_probes']

def save(name, value):
    (E / name).write_text(json.dumps(value, indent=2, default=str) + '\n')

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def git(*args):
    return subprocess.check_output(['git', *args], cwd=R, text=True)

def environment():
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE='1', PIP_NO_INDEX='1', HF_HUB_OFFLINE='1',
               TRANSFORMERS_OFFLINE='1', ANONYMIZED_TELEMETRY='False',
               PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', TMPDIR=str(E / 'tmp'),
               PYTHONPATH=str(E / 'guard'), HIVE_SRC=str(R))
    return env

def run(name, command, cwd=None, timeout=600):
    (E / 'tmp').mkdir(exist_ok=True)
    start = time.time()
    with (E / (name + '-started.json')).open('x') as f:
        json.dump(dict(command=command, cwd=str(cwd or E), started=start), f)
    timed_out = False
    with (E / (name + '.stdout')).open('x') as out, (E / (name + '.stderr')).open('x') as err:
        p = subprocess.Popen(command, cwd=cwd or E, env=environment(),
                             stdout=out, stderr=err, start_new_session=True)
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

def prepare():
    pin = git('rev-parse', 'HEAD').strip()
    assert pin == git('rev-parse', 'cfb03f2').strip()
    assert not git('status', '--porcelain')
    S.mkdir(exist_ok=True)
    manifest = {}
    for name in filter(None, git('ls-files', '-z').split('\0')):
        src, dst = R / name, S / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        manifest[name] = digest(src)
    save('source-sha256.json', manifest)
    versions = {}
    for name in ('pytest', 'build', 'setuptools', 'wheel', 'chromadb', 'onnxruntime'):
        try:
            versions[name] = md.version(name)
        except md.PackageNotFoundError:
            versions[name] = None
    save('environment.json', dict(head=pin, base=git('rev-parse', 'ef18db3').strip(),
         python=sys.version, executable=sys.executable, platform=platform.platform(),
         versions=versions, initial_git_status=git('status', '--porcelain'),
         model='gpt-6-astra explicitly selected; parent verifies routing'))
    (E / 'commit.diff').write_text(git('diff', 'ef18db3..cfb03f2', '--', 'controller/reducer.py', 'hive/reducer.py'))
    (E / 'modified-tests.diff').write_text(git('diff', 'ef18db3..cfb03f2', '--', 'tests'))
    provenance = {}
    helpers = [n + '.py' for n in NAMES] + ['legacy-reducer-e6afe16.py',
               'legacy-reducer-5de0d53.py']
    for name in helpers:
        src, dst = PRIOR / name, E / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        provenance[name] = dict(source=str(src.relative_to(R)), commit=pin, sha256=digest(src))
    # Mechanical API adaptation only; do not rewrite historical expectations.
    p = E / 'mechanism_probes.py'
    old = p.read_text()
    new = old.replace("rebind_plan_owner('p','i')", "rebind_plan_owner('p','i', actor='review7173', reason='legacy witness', allow_non_candidate=True)")
    new = new.replace("rebind_plan_owner('p',target)", "rebind_plan_owner('p',target, actor='review7173', reason='legacy witness', allow_non_candidate=True)")
    new = new.replace("rebind_plan_owner('p','other')", "rebind_plan_owner('p','other', actor='review7173', reason='legacy witness', allow_non_candidate=True)")
    new = new.replace("rebind_plan_owner('p'+str(k),'i'+str(k))", "rebind_plan_owner('p'+str(k),'i'+str(k), actor='review7173', reason='recorded candidate')")
    p.write_text(new)
    (E / 'adaptation.diff').write_text(''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile='7160/mechanism_probes.py', tofile='7173/mechanism_probes.py')))
    save('copy-provenance.json', provenance)
    keys = ['PYTHONDONTWRITEBYTECODE', 'PIP_NO_INDEX', 'HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE',
            'ANONYMIZED_TELEMETRY', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD', 'TMPDIR', 'PYTHONPATH', 'HIVE_SRC']
    save('review-env-overrides.json', {k: environment()[k] for k in keys})

if __name__ == '__main__':
    if '--extra' in sys.argv:
        baseline = E / 'legacy-reducer-ef18db3.py'
        data = subprocess.check_output(['git', 'show', 'ef18db3:controller/reducer.py'], cwd=R)
        baseline.write_bytes(data)
        save('baseline-provenance.json', dict(commit=git('rev-parse', 'ef18db3').strip(),
             path='controller/reducer.py', sha256=digest(baseline)))
        run('review7173', [sys.executable, str(E / 'review7173.py')])
        sys.exit(0)
    prepare()
    run('pytest', [sys.executable, '-m', 'pytest', 'tests/', '-v', '-p', 'no:cacheprovider',
                  '--basetemp=' + str(E / 'pytest-tmp')], S)
    for name in NAMES:
        run(name.replace('_', '-'), [sys.executable, str(E / (name + '.py'))])
