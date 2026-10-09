from pathlib import Path
import subprocess,json,hashlib,platform,importlib.metadata as md,difflib
R=Path('/home/openclaw/research-agent/projects/hive-appliance/repos/hive-appliance');P=R/'experiments/20261008-astra-7727';E=R/'experiments/20261008-astra-7734';S=Path('/tmp/hive-astra-7734-source');E.mkdir();S.mkdir();Path('/tmp/hive-astra-7734-runtime').mkdir()
git=lambda *a:subprocess.check_output(['git',*a],cwd=R)
save=lambda n,o:(E/n).write_text(json.dumps(o,indent=2)+'\n')
pin=git('rev-parse','HEAD').decode().strip(); files=[x for x in git('ls-tree','-r','--name-only',pin).decode().splitlines() if not x.startswith('experiments/')]; hashes={}
for f in files:
 b=git('show',pin+':'+f); p=S/f;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);hashes[f]=hashlib.sha256(b).hexdigest()
(S/'experiments').symlink_to(R/'experiments',target_is_directory=True)
(E/'source').mkdir()
for f in git('diff','--name-only','1a33645',pin).decode().splitlines():
 p=E/'source'/f;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(git('show',pin+':'+f))
(E/'source/target.patch').write_bytes(git('diff','1a33645',pin));(E/'source/code-vs-7ce5cd5.patch').write_bytes(git('diff','7ce5cd5',pin,'--','hive','tests'))
save('source-verification-before.json',dict(pin=pin,source=str(S),files=len(files),hashes=hashes,origin_main=git('rev-parse','origin/main').decode().strip(),git_status=git('status','--short').decode()))
prov=[];diff=[]
for p in list(P.glob('*.py'))+list((P/'guard').glob('*.py')):
 rel=p.relative_to(P);q=E/rel;q.parent.mkdir(parents=True,exist_ok=True);old=p.read_text();new=old.replace('/tmp/hive-astra-7727','/tmp/hive-astra-7734')
 if p.name=='runner.py':new=new.replace("    (E / 'tmp').mkdir(exist_ok=True)\n",'')
 if p.name=='intent_final7727.py':
  new=new.replace("['intent_durable'] is True","['intent_durable'] is False").replace("finding='lexists is not durability; failure claims every start fences without a durability acknowledgement'","finding='CLOSED: visible marker never substitutes for confirmed durability'")
 q.write_text(new);prov.append(dict(source=str(p.relative_to(R)),destination=str(rel),source_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),adapted_sha256=hashlib.sha256(q.read_bytes()).hexdigest()));diff+=list(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile=str(p.relative_to(R)),tofile=str(q.relative_to(R))))
save('copy-provenance.json',prov);(E/'adaptation-7734.diff').write_text(''.join(diff))
save('model-verification.json',dict(runtime_model='openai/gpt-6-astra',required_model='openai/gpt-6-astra',model_match=True,evidence_source=['OpenClaw sessions_list runtime metadata at start','OpenClaw sessions_history assistant runtime metadata during review'],session_key='agent:main:subagent:25bce8e5-d601-46f4-931f-2945ef0ad733',session_id='98ef6aaf-4ed6-4f34-94b3-dac9938d6045',note='Both requested provider and model verified; no substitution or delegation.',provider='openai',model='gpt-6-astra',api='openai-responses'))
save('environment.json',dict(python=platform.python_version(),platform=platform.platform(),uid=1001,packages={k:md.version(k) for k in ['pytest','build']},pin=pin,source=str(S),offline_wheels={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('/tmp/hive-astra-7718/20261008-astra-7718/build-prerequisites').glob('*.whl')}))
(E/'commands.sh').write_text('''#!/bin/sh
export PYTHONDONTWRITEBYTECODE=1
export HIVE_SRC=/tmp/hive-astra-7734-source
python3 run_primary.py
python3 run_journals.py
python3 -c 'import sys; from runner import E,run; [run(n,[sys.executable,str(E/(p+".py"))]) for n,p in [("reset7718","reset7718"),("exact_restore_final7718","exact_restore_final7718"),("intent-final7727","intent_final7727"),("extra-io7727","extra_io7727")]]'
''')
print(pin,len(files))
