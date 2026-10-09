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
             PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', TMPDIR='/tmp/hive-astra-7741-runtime',
             PYTHONPATH=str(E / 'guard'), HIVE_SRC=str(S))
    return e

def run(name, command, cwd=None, timeout=600):
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

