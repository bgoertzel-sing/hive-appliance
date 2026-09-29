"""Replay copied inputs into a fresh directory, with no Git/prior workspace dependency."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('destination', type=Path)
parser.add_argument('--only', choices=['probes', 'pytest', 'all'], default='probes')
args = parser.parse_args()
dest = args.destination.resolve()
dest.mkdir(parents=True, exist_ok=False)
for p in HERE.glob('*.py'):
    shutil.copy2(p, dest / p.name)
shutil.copytree(HERE / 'guard', dest / 'guard')
shutil.copytree(HERE / 'source', dest / 'source')
os.environ['HIVE_SRC'] = str(dest / 'source')
spec = importlib.util.spec_from_file_location('replay_runner', dest / 'run_review.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
results = {}
if args.only in ['all', 'pytest']:
    results['pytest'] = runner.run('pytest', [sys.executable, '-m', 'pytest', 'tests/', '-v',
        '-p', 'no:cacheprovider', '--basetemp=' + str(dest / 'pytest-tmp')], dest / 'source')
if args.only in ['all', 'probes']:
    for name in runner.NAMES + ['review7173']:
        results[name] = runner.run(name.replace('_', '-'), [sys.executable, str(dest / (name + '.py'))])
runner.save('replay-summary.json', results)
sys.exit(int(any(r['exit_code'] != 0 for r in results.values())))
