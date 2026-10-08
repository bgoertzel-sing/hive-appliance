"""Read-only pinned-source, documentation, guard and prior-manifest verification."""
import hashlib,json,os,socket,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent;S=Path(os.environ['HIVE_SRC'])
def git(*a):return subprocess.check_output(['git',*a],cwd=S)
def save(n,o):(E/n).write_text(json.dumps(o,indent=2)+'\n')
before=json.loads((E/'source-verification-before.json').read_text());after={p:hashlib.sha256((S/p).read_bytes()).hexdigest() for p in before};pinned={p:hashlib.sha256(git('show','HEAD:'+p)).hexdigest() for p in before}
assert before==after==pinned and git('status','--porcelain')==b''
save('source-verification.json',dict(pin=git('rev-parse','HEAD').decode().strip(),tracked_non_experiment_files=len(after),byte_identical_to_before=True,byte_identical_to_pinned_git_blobs=True,tracked_status='',hashes=after))
p=subprocess.run(['python3','experiments/20261008-astra-7669/verify_evidence.py'],cwd=S,text=True,capture_output=True);assert p.returncode==0
save('prior-evidence-verification.json',dict(argv=p.args,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr))
commands=[['git','grep','-n','-E','HiveAppliance\\(|rebind_journal|HIVE_REBIND_JOURNAL|volatile_rebinds','HEAD','--',':!experiments',':!docs/ASTRA*'],['git','grep','-n','-i','-E','journal|rebind|snapshot|restore','HEAD','--','README.md','docs/POLICY_MULTI_PLAN_SUPERSESSION.md','hive/event_bus.py','hive/shared_store.py'],['git','grep','-n','fsync','HEAD','--','tests']]
results=[]
for argv in commands:
 p=subprocess.run(argv,cwd=S,text=True,capture_output=True);results.append(dict(argv=argv,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr))
save('production-wiring-search.json',results)
# Guard is loaded via runner PYTHONPATH; rejection occurs before a syscall.
with socket.socket() as sock:
 try:sock.connect(('203.0.113.1',443))
 except OSError as ex:assert 'External network disabled' in str(ex);guard_error=str(ex)
 else:raise AssertionError('network guard not active')
wheels=json.loads((E/'build-prerequisites.json').read_text())
for name,h in wheels.items():assert hashlib.sha256((E/'build-prerequisites'/name).read_bytes()).hexdigest()==h
save('offline-verification.json',dict(guard_error=guard_error,guard_sha256=hashlib.sha256((E/'guard/sitecustomize.py').read_bytes()).hexdigest(),PIP_NO_INDEX=os.environ.get('PIP_NO_INDEX'),wheel_hashes_verified=wheels,scope='Python socket guard allows loopback/Unix only; pip offline. Not an OS-wide sandbox; no remote compute/network workloads used.'))
notes=dict(changed_files=git('diff','--name-only','7008f0a','2e63084').decode().splitlines(),diff_read='Complete four-file diff and interacting reducer paths inspected; README/policy/test file archived',documentation=dict(recovery_exact='CLOSED Low exact7669 marker STAYS and any-step untouched overclaims replaced with accurate cases',snapshot='Still unsupported, full original ordered stream required; retained suffix-only/synthetic hydrate fail-closed, no native snapshot API',integrity='Unkeyed SHA-256 correctly scoped to accidental/naive corruption, not malicious writer recomputing hashes; temporal ordering assumption not enforced by a journal chain',legacy_fence='Policy explicitly says legacy-format markers fence every journaled rebind; two-entry v1 witness confirms until clearance',diagnostics='abort_durable and marker_present/persisted are accurate in reproduced single and compound faults; textual MAY replay warning clear, no durable warning when both repairs fail',remaining_source_comment='Internal _journal_append docstring still says indeterminate fence stays on disk; stale comment, not accurate protocol description; user-facing two exact previous overclaims fixed'),authored_tests='8 added tests, no prior tests modified. Full suite 782 passed. In-memory held check present but not whole-business-state equality; independent witness confirms only _journal_indeterminate and _journal_aborted change. No authored lost-newline cancellation or forward-record cancellation witness. Claimed restart-never-applies test-module header overbroad for documented compound failure.',gate='NOT APPROVED',findings=dict(exact7669='All four exact OPEN witnesses closed; F-abort-content residual via torn-tail cancellation remains Medium',new_medium=['F-journal-refused-compound','F-abort-tail','F-abort-order-scope (reordered-storage qualification)']),scope='No production/test source edits; report/evidence only')
save('static-review.json',notes)
r=json.loads((E/'review7678.json').read_text());save('helper-adaptations.json',dict(cap_helper=r['retained_caps']['adaptations'],cap_helper_sha256=r['retained_caps']['adapted_helper_sha256'],legacy300=r['retained_regressions']['adaptation'],primary_adaptation='witness-adaptation.diff: same7669 fault injection/event witnesses; expected fixed outcomes and all-marker clearance assertions updated',retained_helpers='Historical mains are definition inputs, NOT additional scripts to execute; unchanged run_primary executes old semantic harnesses exactly once'))
print(json.dumps(dict(source_files=len(after),source_clean=True,pinned_bytes_verified=True,prior_manifest=json.loads((E/'prior-evidence-verification.json').read_text())['stdout'],guard_active=True,notes=notes),indent=2))
