"""Copy review inputs to a NEW directory and replay without Git access."""
import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument('destination', type=Path)
p.add_argument('--only', choices=['probes', 'pytest', 'all'], default='probes')
a = p.parse_args()
dest = a.destination.resolve()
dest.mkdir(parents=True, exist_ok=False)
for name in ['run_review.py', 'review7195.py', 'audit_results.py']:
    shutil.copy2(HERE / name, dest / name)
for name in ['adversarial', 'adversarial-inverted', 'new_cases', 'supplementary',
             'probes', 'older-regressions', 'independent', 'semantic_7133',
             'boundary_and_disk', 'mechanism_probes', 'review7173']:
    shutil.copy2(HERE / (name + '.py'), dest / (name + '.py'))
for source in HERE.glob('legacy-reducer-*.py'):
    shutil.copy2(source, dest / source.name)
shutil.copytree(HERE / 'guard', dest / 'guard')
shutil.copytree(HERE / 'source', dest / 'source')
os.environ['HIVE_SRC'] = str(dest / 'source')
spec = importlib.util.spec_from_file_location('runner', dest / 'run_review.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
results = {}
if a.only in ['pytest', 'all']:
    results['pytest'] = runner.run('pytest', [sys.executable, '-m', 'pytest', 'tests/', '-v',
        '-p', 'no:cacheprovider', '--basetemp=' + str(dest / 'pytest-tmp')], dest / 'source')
if a.only in ['probes', 'all']:
    for name in runner.NAMES + ['review7195', 'audit_results']:
        results[name] = runner.run(name.replace('_', '-'), [sys.executable, str(dest / (name + '.py'))])
runner.save('replay-summary.json', results)
sys.exit(int(any(v['exit_code'] != 0 for v in results.values())))
