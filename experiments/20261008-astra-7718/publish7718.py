"""Publish report and review evidence only, never scratch or production files."""
import pathlib,shutil,json,subprocess,hashlib,os
E=pathlib.Path('/tmp/hive-astra-7718/20261008-astra-7718');R=pathlib.Path('/home/openclaw/research-agent/projects/hive-appliance/repos/hive-appliance');D=R/'experiments/20261008-astra-7718';S=pathlib.Path('/tmp/hive-astra-7718-source')
def git(*a):return subprocess.check_output(['git',*a],cwd=R).decode()
pin='0ec1a2dc9b56b8011903180f07f94cd1f3f3d39f'
subprocess.run(['git','fetch','origin'],cwd=R,check=True)
assert git('rev-parse','HEAD').strip()==git('rev-parse','origin/main').strip()==pin
assert git('branch','--show-current').strip()=='main'
assert not git('diff','--name-only') and not git('diff','--cached','--name-only')
assert not subprocess.check_output(['git','status','--porcelain'],cwd=S)
(E/'prepublication-git.json').write_text(json.dumps(dict(local=pin,remote_tracking=pin,branch='main',status=git('status','--short')),indent=2)+'\n')
(E/'publication-checks.json').write_text(json.dumps(dict(scope=['docs/ASTRA_REVIEW_7718.md','experiments/20261008-astra-7718/'],source_pin=pin,branch='main',fetched_origin_unchanged=True,source_files_verified=155,source_clean=True,old_manifest_counts=json.loads((E/'prior-evidence-verification.json').read_text()),excluded=['tmp/','pytest-tmp/','__pycache__/','build-prerequisites/'],postpush_record='/tmp/hive-astra-7718/postpush-verification.json',commit_push_status='To be executed and independently verified after manifest/staging; not claimed by this prepublication artifact'),indent=2)+'\n')
assert not D.exists();shutil.copytree(E,D,ignore=shutil.ignore_patterns('tmp','pytest-tmp','__pycache__','build-prerequisites','*.pyc'))
shutil.copy2('/tmp/hive-astra-7718/report.md',R/'docs/ASTRA_REVIEW_7718.md')
subprocess.run(['git','add','--','docs/ASTRA_REVIEW_7718.md','experiments/20261008-astra-7718'],cwd=R,check=True)
subprocess.run(['python3',str(D/'scan_staged.py'),'--write'],cwd=R,check=True)
files=sorted([p for p in D.rglob('*') if p.is_file() and p.name!='SHA256SUMS']+[R/'docs/ASTRA_REVIEW_7718.md'])
(D/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+os.path.relpath(p,D)+'\n' for p in files))
subprocess.run(['git','add','--','docs/ASTRA_REVIEW_7718.md','experiments/20261008-astra-7718'],cwd=R,check=True)
subprocess.run(['python3',str(D/'verify_evidence.py')],cwd=R,check=True)
subprocess.run(['python3',str(D/'scan_staged.py')],cwd=R,check=True)
subprocess.run(['git','diff','--cached','--check','--','docs/ASTRA_REVIEW_7718.md',str(D/'README.md'),str(D/'RUN.md')],cwd=R,check=True)
print('ready',len(files),'manifested report/artifacts')
