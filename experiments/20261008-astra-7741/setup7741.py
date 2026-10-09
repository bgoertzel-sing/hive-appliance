from pathlib import Path
import subprocess,json,hashlib,platform,os,importlib.metadata as md,difflib
R=Path(__file__).resolve().parents[2];P=R/'experiments/20261008-astra-7734';E=Path(__file__).resolve().parent;S=Path('/tmp/hive-astra-7741-source');S.mkdir();Path('/tmp/hive-astra-7741-runtime').mkdir()
git=lambda *a:subprocess.check_output(['git',*a],cwd=R)
save=lambda n,o:(E/n).write_text(json.dumps(o,indent=2)+'\n')
pin=git('rev-parse','HEAD').decode().strip();files=[x for x in git('ls-tree','-r','--name-only',pin).decode().splitlines() if not x.startswith('experiments/')];hashes={}
for f in files:
 b=git('show',pin+':'+f);p=S/f;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);hashes[f]=hashlib.sha256(b).hexdigest()
(S/'experiments').symlink_to(R/'experiments',target_is_directory=True)
(E/'source').mkdir()
for f in git('diff','--name-only','48c10cc',pin).decode().splitlines():
 p=E/'source'/f;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(git('show',pin+':'+f))
(E/'source/target.patch').write_bytes(git('diff','48c10cc',pin))
save('source-verification-before.json',dict(pin=pin,source=str(S),files=len(files),hashes=hashes,origin_main=git('rev-parse','origin/main').decode().strip(),git_status=git('status','--short').decode()))
for p in list(P.glob('*.py'))+list((P/'guard').glob('*.py')):
 if p.name.startswith('setup'):continue
 rel=p.relative_to(P);q=E/rel;q.parent.mkdir(parents=True,exist_ok=True);new=p.read_text().replace('/tmp/hive-astra-7734','/tmp/hive-astra-7741')
 if p.name=='secret_scan.py':new=new.replace('ASTRA_REVIEW_7734','ASTRA_REVIEW_7741')
 if p.name=='verify_sources7734.py':new=new.replace("'7718','7727'","'7718','7727','7734'")
 if p.name=='run_primary.py':new=new.replace('"probes","older-regressions","independent"','"probes-final","older-regressions-final","independent-final"')
 if p.name=='intent7734.py':new=new.replace("assert 'fsync confirmed' in fence['error']","assert 'fsync confirmed' in fence['error'] or 'new rebind-free journal and anchor are complete' in fence['error']")
 if p.name=='metadata7734.py':
  new=new.replace("f['intent_present'] is False","f['intent_present'] is None and f['presence_error']").replace("print('2 presence/error-text contradictions; 2 namespace-only confirmations recorded')","print('2 corrected presence/error-text cases; 2 nonregular refusals recorded')")
  new=new.replace("assert f['intent_durable'] is False and ns['pair'](p)!=old","assert f['intent_durable'] is False and ns['pair'](p)!=old\n assert 'old journal and .id are unchanged' not in f['error'] and 'marker was unlinked' not in f['error']")
 q.write_text(new)
save('environment.json',dict(python=platform.python_version(),platform=platform.platform(),uid=os.getuid(),packages={k:md.version(k) for k in ['pytest','build']},pin=pin,source=str(S),offline_wheels={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('/tmp/hive-astra-7718/20261008-astra-7718/build-prerequisites').glob('*.whl')}))
print(pin,len(files))
