from pathlib import Path
import subprocess,hashlib,json,shutil,sys,platform,importlib.metadata as md
E=Path(__file__).resolve().parent
R=E.parent.parent/'repos/hive-astra-7519'
P=E.parent/'20260928-astra-7195'
def git(*a):return subprocess.check_output(['git',*a],cwd=R)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,x):(E/n).write_text(json.dumps(x,indent=2)+'\n')
assert git('rev-parse','HEAD').decode().strip()==git('rev-parse','origin/main').decode().strip()=='9194f52d72a0e853427fd725d2683cc39db39339'
assert not git('status','--porcelain')
S=E/'source'; S.mkdir()
hashes={}
for name in git('ls-files','-z').decode().split('\0'):
 if not name or name.startswith('experiments/'):continue
 p=S/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(R/name,p);hashes[name]=digest(p)
save('source-sha256.json',hashes)
prov={}
for name in ['run_review.py','probes.py','older-regressions.py','independent.py','boundary_and_disk.py','mechanism_probes.py','review7173.py','review7195.py','legacy-reducer-e6afe16.py','legacy-reducer-ef18db3.py','legacy-reducer-5de0d53.py','legacy-reducer-cfb03f2.py']:
 shutil.copy2(P/name,E/name);prov[name]=dict(source='20260928-astra-7195/'+name,sha256=digest(E/name))
shutil.copytree(P/'guard',E/'guard',ignore=shutil.ignore_patterns('__pycache__'))
save('copy-provenance.json',prov)
save('environment.json',dict(pin=git('rev-parse','HEAD').decode().strip(),origin=git('remote','get-url','origin').decode().strip(),python=sys.version,platform=platform.platform(),versions={n:md.version(n) for n in ['pytest','build','setuptools','wheel']},initial_status=git('status','--porcelain').decode(),model='gpt-6-astra',model_verification='sessions_list for agent:main:subagent:36a139fc-49ec-4033-b1a6-09f7e8ec3bed; session_status unavailable'))
(E/'production.diff').write_bytes(git('diff','f1736e5..HEAD','--','controller','hive'))
