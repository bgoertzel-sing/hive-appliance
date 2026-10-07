"""Replay into NEW output; full suite only when explicitly requested."""
import argparse, hashlib, json, os, shutil, subprocess, sys
from pathlib import Path
E=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--include-pytest',action='store_true');a=p.parse_args()
out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
manifest=json.loads((E/'source-sha256.json').read_text())
for n,h in manifest.items():
 src=E/'source'/n;assert hashlib.sha256(src.read_bytes()).hexdigest()==h
 dst=out/'source'/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
inputs=list(json.loads((E/'copy-provenance.json').read_text()))+['runner.py','review7542.py','execute_regressions.py']
for n in inputs:shutil.copy2(E/n,out/n)
shutil.copytree(E/'guard',out/'guard',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
sys.path.insert(0,str(out))
from runner import run
if a.include_pytest:run('pytest',[sys.executable,'-m','pytest','tests/','-v','-p','no:cacheprovider','--basetemp='+str(out/'pytest-tmp')],out/'source')
run('review7542',[sys.executable,str(out/'review7542.py')])
for n in ['review7195','review7173','boundary_and_disk','mechanism_probes','probes','older-regressions','independent','new_cases','semantic_7133']:
 run(n.replace('_','-'),[sys.executable,str(out/(n+'.py'))])
print('Read all *-exit.json: semantic-7133 has three retained obsolete legacy expectations; a successful witness is not a closed finding.')
