"""Read-only pinned-source, documentation, guard and prior-manifest verification."""
import hashlib,json,os,socket,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent;S=Path(os.environ['HIVE_SRC'])
def git(*a):return subprocess.check_output(['git',*a],cwd=S)
def save(n,o):(E/n).write_text(json.dumps(o,indent=2)+'\n')
before=json.loads((E/'source-verification-before.json').read_text());after={p:hashlib.sha256((S/p).read_bytes()).hexdigest() for p in before};pinned={p:hashlib.sha256(git('show','HEAD:'+p)).hexdigest() for p in before}
assert before==after==pinned and git('status','--porcelain')==b''
save('source-verification.json',dict(pin=git('rev-parse','HEAD').decode().strip(),tracked_non_experiment_files=len(after),byte_identical_to_before=True,byte_identical_to_pinned_git_blobs=True,tracked_status='',hashes=after))
p=subprocess.run(['python3','experiments/20261008-astra-7656/verify_evidence.py'],cwd=S,text=True,capture_output=True);assert p.returncode==0
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
notes=dict(changed_files=git('diff','--name-only','7a372c3','d0fc184').decode().splitlines(),diff_read='Complete five-file diff; changed paths and interacting reducer paths inspected',documentation=dict(configuration='CLOSED prior Low: README and policy journal argument/env/default/volatile opt-out',migration='CLOSED prior Low: v1 AND v2 explicitly rejected/reissued; authentic 647fac6 record exercised',replay='Full ordered stream required; snapshot/partial restore explicitly unsupported',integrity='Plain unkeyed SHA-256 explicitly corruption/naive-edit detection, not hostile rewrite resistance; appropriate scope, but fence/abort corruption paths fail that scope',recovery_inaccuracies='OPEN Low: marker STAYS claim false after successful unlink+failed dir fsync; any torn-tail step failure leaves original untouched claim false after ftruncate+failed journal fsync',audit='Abort JSONL durably retains actor/reason; live fence_clearances list not reconstructed on restart'),authored_test_changes='Both fsync tests now target journal descriptor so they still reach original append/rollback boundary after fence added; assertions preserved plus no-fence assertion. Does not weaken original proof. Fence fsync failure not separately covered by authored tests found; independent all_fsync_fail/fence_fsync plus creation dir fault now cover it.',snapshot_severity='Documented unsupported path: fail-closed pending/unapplied, availability/recovery limitation; not newly demonstrated incorrect closure. No durable global event archive/checkpoint solution in patch.',resource_scope='Actual 10000 tracked-plan admission proven; arbitrary incident/pending receipt counts and oversized old journal reading remain outside this cap; no OOM claim.',scope='No production/test source edits; report/evidence only')
save('static-review.json',notes)
r=json.loads((E/'review7669.json').read_text());save('helper-adaptations.json',dict(cap_helper=r['retained_caps']['adaptations'],cap_helper_sha256=r['retained_caps']['adapted_helper_sha256'],legacy300=r['retained_regressions']['adaptation'],retained_helpers='Copied scripts are definition inputs; old review mains with old defect expectations are NOT run. Unchanged run_primary.py executes historical semantic harnesses.'))
print(json.dumps(dict(source_files=len(after),source_clean=True,pinned_bytes_verified=True,prior_manifest=p.stdout if False else json.loads((E/'prior-evidence-verification.json').read_text())['stdout'],guard_active=True,notes=notes),indent=2))
