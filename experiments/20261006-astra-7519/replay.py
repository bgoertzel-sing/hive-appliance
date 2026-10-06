"""Portable input-only replay; writes exclusively to a new directory."""
import argparse,os,shutil,subprocess,sys
from pathlib import Path
E=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('destination',type=Path);p.add_argument('--include-pytest',action='store_true');a=p.parse_args()
D=a.destination.resolve();D.mkdir(parents=True,exist_ok=False)
for name in ['source','guard']:shutil.copytree(E/name,D/name,ignore=shutil.ignore_patterns('__pycache__'))
for path in E.glob('*.py'):shutil.copy2(path,D/path.name)
code="from run_review import run,E; import sys; names=['review7519','review7195','review7173','boundary_and_disk','mechanism_probes','probes','older-regressions','independent','new_cases','semantic_7133']; results=[run(n.replace('_','-'),[sys.executable,str(E/(n+'.py'))]) for n in names]; sys.exit(any(r['exit_code'] for r in results))"
env=os.environ.copy();env.update(HIVE_SRC=str(D/'source'),PYTHONDONTWRITEBYTECODE='1')
rc=subprocess.run([sys.executable,'-c',code],cwd=D,env=env).returncode
if a.include_pytest:rc=max(rc,subprocess.run([sys.executable,str(D/'run_review.py'),'--only','pytest'],cwd=D,env=env).returncode)
sys.exit(rc)
