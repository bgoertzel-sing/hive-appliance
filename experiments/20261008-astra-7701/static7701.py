"""Read-only final pinned-source/prior-evidence/network/wiring verification."""
import hashlib,json,os,socket,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent;S=Path(os.environ['HIVE_SRC'])
def git(*a):return subprocess.check_output(['git',*a],cwd=S)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,d):(E/n).write_text(json.dumps(d,indent=2)+'\n')
before=json.loads((E/'source-verification-before.json').read_text())
after={p:sha(S/p) for p in before}
pinned={p:hashlib.sha256(git('show','HEAD:'+p)).hexdigest() for p in before}
assert before==after==pinned
status=git('status','--porcelain').decode();assert status=='',status
assert git('rev-parse','HEAD').decode().strip()=='865fd633bc53561aea140dc3f43fee72b8fd61ee'
assert (E/'source/production.diff').read_bytes()==git('diff','5535545','865fd63')
for p in git('diff','--name-only','5535545','865fd63').decode().splitlines():assert (E/'source'/p).read_bytes()==(S/p).read_bytes()
save('source-verification.json',dict(pin=git('rev-parse','HEAD').decode().strip(),tracked_non_experiment_files=len(after),byte_identical_to_before=True,byte_identical_to_pinned_git_blobs=True,status=status,hashes=after))
prior=[]
for n in ['7669','7678','7694']:
 p=subprocess.run(['python3','experiments/20261008-astra-'+n+'/verify_evidence.py'],cwd=S,capture_output=True,text=True)
 assert p.returncode==0,(n,p.stderr)
 prior.append(dict(round=n,exit=p.returncode,stdout=p.stdout,stderr=p.stderr))
save('prior-evidence-verification.json',prior)
commands=[
 ['git','grep','-n','-E','rebind_plan_owner|last_rebind_result|RebindResult','HEAD','--',':!experiments'],
 ['git','grep','-n','-E','rebind_journal|journal_status|owner_rebinds|verify_journal','HEAD','--','hive/appliance.py','hive/dashboard.py','controller','cli.py'],
 ['git','grep','-n','-i','-E','journal|rebind|snapshot|restore|rollback|unkeyed|MAC','HEAD','--','README.md','docs/POLICY_MULTI_PLAN_SUPERSESSION.md'],
 ['git','show','--format=fuller','--stat','865fd63'],
 ['git','log','-5','--format=fuller'],
 ['git','reflog','show','--format=%H %gs','origin/main']]
wiring=[]
for argv in commands:
 p=subprocess.run(argv,cwd=S,text=True,capture_output=True);assert p.returncode in [0,1]
 wiring.append(dict(argv=argv,exit=p.returncode,stdout=p.stdout,stderr=p.stderr))
save('production-wiring-search.json',wiring)
with socket.socket() as sock:
 try:sock.connect(('203.0.113.1',443))
 except OSError as ex:assert 'External network disabled' in str(ex);error=str(ex)
 else:raise AssertionError('guard missing')
wheels=json.loads((E/'build-prerequisites.json').read_text())
for n,h in wheels.items():assert sha(E/'build-prerequisites'/n)==h
save('offline-verification.json',dict(guard_error=error,guard_sha256=sha(E/'guard/sitecustomize.py'),PIP_NO_INDEX=os.environ.get('PIP_NO_INDEX'),wheel_hashes_verified=wheels,scope='Python socket guard, not OS-wide network sandbox. No paid/remote compute or deployment.'))
save('author-test-provenance.json',dict(claim='Author full 795 suite preceded a docs-only edit',available='Single published implementation commit 865fd63 after report commit 5535545; no independently identified pre-doc tested tree hash supplied or present in available refs.',non_doc_diff_relative_to_claimed_tested_tree='UNVERIFIABLE: tested tree identifier absent; do not assert empty diff.',independent_confirmation='795 passed once on the exact final 865fd63 tree; tracked non-experiment files unchanged before/after. This supersedes the provenance gap for independently tested current bytes, not proof of author chronology.'))
print(json.dumps(dict(source_files=len(after),prior_manifests=prior,offline_verified=True),indent=2))
