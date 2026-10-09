import pathlib,shutil,subprocess,json,hashlib,platform,importlib.metadata as md,difflib
R=pathlib.Path('/home/openclaw/research-agent/projects/hive-appliance/repos/hive-appliance'); E=pathlib.Path('/tmp/hive-astra-7708/20261008-astra-7708');S=pathlib.Path('/tmp/hive-astra-7708-source');P=R/'experiments/20261008-astra-7701'
subprocess.run(['git','worktree','add','--detach',str(S),'8945bdcb06415a11a5647fbb0e4decc59e021784'],cwd=R,check=True)
prov={}
for p in P.glob('*.py'):
 if p.name.startswith(('static','publish','prepublication','publication','scan','verify','prepare','setup','adapt','retry','legacy_final')):continue
 shutil.copy2(p,E/p.name);prov[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
shutil.copytree(P/'guard',E/'guard');shutil.copytree('/tmp/hive-astra-7701/20261008-astra-7701/build-prerequisites',E/'build-prerequisites')
for n in ['build-prerequisites.json','retained-extraction.json','witness-adaptation.diff','adaptation-7701.diff']:shutil.copy2(P/n,E/n)
(E/'copy-provenance.json').write_text(json.dumps(prov,indent=2))
def git(*a):return subprocess.check_output(['git',*a],cwd=S)
f=[x for x in git('ls-files').decode().splitlines() if not x.startswith('experiments/')];(E/'source-verification-before.json').write_text(json.dumps({p:hashlib.sha256((S/p).read_bytes()).hexdigest() for p in f},indent=2))
D=E/'source';D.mkdir();(D/'production.diff').write_bytes(git('diff','1a87ae9','HEAD'))
for p in git('diff','--name-only','1a87ae9','HEAD').decode().splitlines()+['pyproject.toml','requirements.txt','requirements-dev.txt']:
 q=D/p;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(S/p,q)
(E/'environment.json').write_text(json.dumps(dict(python=platform.python_version(),platform=platform.platform(),packages={p:md.version(p) for p in ['pytest','build']},pin=git('rev-parse','HEAD').decode().strip(),origin_main=git('rev-parse','origin/main').decode().strip()),indent=2))
p=E/'followup7694.py';p.write_text(p.read_text().replace("=='legacy_marker'","=='legacy'"))
(E/'adaptation-7708.diff').write_text(''.join(difflib.unified_diff((P/p.name).read_text().splitlines(True),p.read_text().splitlines(True),fromfile='7701/'+p.name,tofile='7708/'+p.name)))
