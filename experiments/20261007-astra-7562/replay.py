"""Replay into a NEW directory; never overwrites published evidence."""
import argparse,json,os,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--include-pytest',action='store_true');a=p.parse_args()
E=Path(__file__).resolve().parent;D=a.output.resolve();D.mkdir(exist_ok=False)
for n in ['runner.py','review7562.py','authority_followup.py']+list(json.loads((E/'copy-provenance.json').read_text())):
 shutil.copy2(E/n,D/n)
shutil.copytree(E/'source',D/'source');shutil.copytree(E/'guard',D/'guard')
(D/'commands.sh').write_text('# Reproduction child commands\n')
if a.include_pytest:
 subprocess.run([sys.executable,'-m','pip','download','--no-deps','--only-binary=:all:','--dest',str(D/'build-prerequisites'),'setuptools==82.0.1','wheel==0.46.3','packaging==26.0'],check=True)
 os.environ['PIP_FIND_LINKS']=str(D/'build-prerequisites')
os.environ['HIVE_SRC']=str(D/'source');sys.path.insert(0,str(D))
from runner import run
if a.include_pytest:run('pytest',[sys.executable,'-m','pytest','tests/','-v','-p','no:cacheprovider','--basetemp='+str(D/'pytest-tmp')],D/'source')
for n in ['review7195','review7173','boundary_and_disk','mechanism_probes','probes','older-regressions','independent','new_cases','semantic_7133','review7562','authority_followup']:
 run(n.replace('_','-'),[sys.executable,str(D/(n+'.py'))],D)
print('Read individual exit JSON and report known-failure qualifications; output:',D)
