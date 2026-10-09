import pathlib,subprocess,shutil,hashlib,json,platform,importlib.metadata as md
R=pathlib.Path('/home/openclaw/research-agent/projects/hive-appliance/repos/hive-appliance')
E=pathlib.Path('/tmp/hive-astra-7701/20261008-astra-7701');E.mkdir(parents=True,exist_ok=True)
S=pathlib.Path('/tmp/hive-astra-7701-source')
subprocess.run(['git','worktree','add','--detach',str(S),'865fd633bc53561aea140dc3f43fee72b8fd61ee'],cwd=R,check=True)
P=R/'experiments/20261008-astra-7694'
prov={}
for p in P.glob('*.py'):
 if p.name.startswith(('static','publish','prepublication','publication','scan','verify','archive','make_')):continue
 shutil.copy2(p,E/p.name);prov[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
for name in ['guard','build-prerequisites']:
 src=P/name if name=='guard' else pathlib.Path('/tmp/hive-astra-7694/20261008-astra-7694/build-prerequisites')
 shutil.copytree(src,E/name)
for name in ['build-prerequisites.json','retained-extraction.json','witness-adaptation.diff']:
 shutil.copy2(P/name,E/name)
shutil.copy2(R/'experiments/20261008-astra-7701/model-verification.json',E/'model-verification.json')
def git(*args):return subprocess.check_output(['git',*args],cwd=S)
files=[x for x in git('ls-files').decode().splitlines() if not x.startswith('experiments/')]
(E/'source-verification-before.json').write_text(json.dumps({p:hashlib.sha256((S/p).read_bytes()).hexdigest() for p in files},indent=2)+'\n')
D=E/'source';D.mkdir()
(D/'production.diff').write_bytes(git('diff','5535545','865fd63'))
for p in git('diff','--name-only','5535545','865fd63').decode().splitlines()+['pyproject.toml','requirements.txt','requirements-dev.txt']:
 q=D/p;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(S/p,q)
(E/'copy-provenance.json').write_text(json.dumps(prov,indent=2)+'\n')
(E/'environment.json').write_text(json.dumps(dict(python=platform.python_version(),platform=platform.platform(),packages={p:md.version(p) for p in ['pytest','build']},pin=git('rev-parse','HEAD').decode().strip(),origin_main=git('rev-parse','origin/main').decode().strip()),indent=2)+'\n')
(E/'commands.sh').write_text('#!/bin/sh\nset -eu\nexport HIVE_SRC=/tmp/hive-astra-7701-source\nexport PYTHONDONTWRITEBYTECODE=1\ncd /tmp/hive-astra-7701/20261008-astra-7701\npython3 run_primary.py\n')
print(E)
