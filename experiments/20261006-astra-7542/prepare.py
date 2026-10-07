import sys, json, hashlib, subprocess, shutil, platform, importlib.metadata as md
from pathlib import Path
from runner import save,run,digest
E=Path(__file__).resolve().parent
R=E.parents[1]/'repos/hive-astra-7542'
def git(*a): return subprocess.check_output(['git',*a],cwd=R)
pin='85c505d1608680f1ac965ad5fad46a573c032b35'
assert git('rev-parse','HEAD').decode().strip()==pin==git('rev-parse','origin/main').decode().strip()
assert not git('status','--porcelain')
run('review-branch',['git','checkout','-b','review/astra-7542'],R)
S=E/'source';S.mkdir()
manifest={}
for n in git('ls-files','-z').decode().split('\0'):
 if not n or n.startswith('experiments/'): continue
 src=R/n;dst=S/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);manifest[n]=digest(src)
save('source-sha256.json',manifest)
save('environment.json',dict(pin=pin,origin_main=pin,status='clean at initial pin',python=sys.version,platform=platform.platform(),versions={n:md.version(n) for n in ['pytest','build','setuptools','wheel']},reviewer='gpt-6-astra',model_evidence='model-verification.json'))
(E/'production.diff').write_bytes(git('diff','c876525..'+pin,'--','controller/reducer.py','hive/reducer.py','docs/POLICY_MULTI_PLAN_SUPERSESSION.md','tests/test_astra7160.py','tests/test_astra7519.py','tests/test_p0_fixes.py'))
prior=E.parent/'20261006-astra-7519'
provenance={}
for n in ['review7519.py','review7173.py','review7195.py','new_cases.py','probes.py','older-regressions.py','independent.py','semantic_7133.py','boundary_and_disk.py','mechanism_probes.py','legacy-reducer-e6afe16.py','legacy-reducer-ef18db3.py','legacy-reducer-5de0d53.py','legacy-reducer-cfb03f2.py']:
 shutil.copy2(prior/n,E/n);provenance[n]=dict(source='20261006-astra-7519/'+n,sha256=digest(E/n))
shutil.copytree(prior/'guard',E/'guard')
save('copy-provenance.json',provenance)
