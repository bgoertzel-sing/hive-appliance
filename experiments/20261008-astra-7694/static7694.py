"""Read-only source, evidence, wiring, offline guard, documentation and coverage audit."""
import hashlib,json,os,socket,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent;S=Path(os.environ['HIVE_SRC'])
def git(*a):return subprocess.check_output(['git',*a],cwd=S)
def save(n,o):(E/n).write_text(json.dumps(o,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
before=json.loads((E/'source-verification-before.json').read_text())
after={p:sha(S/p) for p in before}
pinned={p:hashlib.sha256(git('show','HEAD:'+p)).hexdigest() for p in before}
status=git('status','--porcelain').decode()
assert before==after==pinned and all(x=='?? scratch/' for x in status.splitlines())
assert git('rev-parse','HEAD').decode().startswith('cf6a060')
save('source-verification.json',dict(pin=git('rev-parse','HEAD').decode().strip(),tracked_non_experiment_files=len(after),byte_identical_to_before=True,byte_identical_to_pinned_git_blobs=True,status=status,hashes=after))
diff=git('diff','d1239f9','cf6a060')
assert (E/'source/production.diff').read_bytes()==diff
changed=git('diff','--name-only','d1239f9','cf6a060').decode().splitlines()
for path in changed:
 if (S/path).exists():assert (E/'source'/path).read_bytes()==(S/path).read_bytes(),path
assert (E/'source/test_astra7669-deleted.py').read_bytes()==git('show','d1239f9:tests/test_astra7669.py')
results=[]
for round in ['7669','7678']:
 path='experiments/20261008-astra-'+round+'/verify_evidence.py'
 if (S/path).exists():
  p=subprocess.run(['python3',path],cwd=S,text=True,capture_output=True);assert p.returncode==0,p.stderr
  results.append(dict(argv=p.args,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr))
save('prior-evidence-verification.json',results)
commands=[['git','grep','-n','-E','rebind_journal|HiveAppliance\\(|HIVE_REBIND_JOURNAL|clear_journal_fence|journal_status|rebind_journal_healthy','HEAD','--',':!experiments',':!docs'],['git','grep','-n','-i','-E','journal|rebind|snapshot|restore','HEAD','--','README.md','docs/POLICY_MULTI_PLAN_SUPERSESSION.md'],['git','grep','-n','fsync','HEAD','--','tests']]
results=[]
for argv in commands:
 p=subprocess.run(argv,cwd=S,text=True,capture_output=True);assert p.returncode in [0,1]
 results.append(dict(argv=argv,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr))
save('production-wiring-search.json',results)
with socket.socket() as sock:
 try:sock.connect(('203.0.113.1',443))
 except OSError as ex:assert 'External network disabled' in str(ex);guard_error=str(ex)
 else:raise AssertionError('network guard inactive')
wheels=json.loads((E/'build-prerequisites.json').read_text())
for name,h in wheels.items():assert sha(E/'build-prerequisites'/name)==h
save('offline-verification.json',dict(guard_error=guard_error,guard_sha256=sha(E/'guard/sitecustomize.py'),PIP_NO_INDEX=os.environ.get('PIP_NO_INDEX'),wheel_hashes_verified=wheels,scope='Python socket guard, not OS sandbox; no remote/paid compute.'))
coverage=[
 dict(deleted='test_marker_unlink_then_dir_fsync_failure_never_replays',mapping=['test_astra7656.py::test_clean_refusal_leaves_no_fence','followup7694.v4_fault_matrix','followup7694.exact7678_archived_witnesses'],assessment='Old writer unlink/abort step removed. Refused-restart invariant retained, not the obsolete syscall path.'),
 dict(deleted='test_abort_also_fails_marker_rewritten_restart_fenced',mapping=['test_astra7678.py::test_pending_write_and_rollback_fail_refused_and_never_replayed','test_astra7678.py::test_commit_write_and_rollback_fail_is_applied_not_refused','followup7694.v4_fault_matrix','followup7694.exact7678_archived_witnesses'],assessment='Compensating abort/marker removed; both new uncertain outcomes covered.'),
 dict(deleted='test_marker_with_edited_op_id_fences_everything',mapping=['test_astra7656.py::test_legacy_fence_marker_fences_everything','followup7694.old_markers'],assessment='Presence alone now fences all; edited ID and missing entry specifically retained independently.'),
 dict(deleted='test_valid_marker_not_naming_last_entry_fences_everything',mapping=['test_astra7656.py::test_legacy_fence_marker_fences_everything','followup7694.old_markers'],assessment='Selective marker validation intentionally removed; nonlast marker presence blocks all. No hash-valid v2-specific assertion in current pytest; obsolete validation path.'),
 dict(deleted='test_intact_marker_still_fences_only_its_entry',mapping=['test_astra7656.py::test_legacy_fence_marker_fences_everything','followup7694.old_markers'],assessment='Selective availability guarantee intentionally lost, superseded by documented whole-journal legacy fencing; not a lost fail-closed guarantee.'),
 dict(deleted='test_one_char_edit_of_abort_op_id_does_not_revive_entry',mapping=['test_astra7656.py::test_edited_journal_entry_not_replayed','followup7694.native_tails_order_edits','followup7694.exact7678_archived_witnesses'],assessment='v3 abort unsupported/migration-fenced; v4 deciding-commit edit/tail covered. Old-format byte regression no longer an authored pytest case.'),
 dict(deleted='test_rehashed_abort_naming_no_rebind_does_not_revive_entry',mapping=['test_astra7678.py::test_rehashed_forged_commit_without_chain_fences','followup7694.duplicate_commit'],assessment='Analogous chain and missing-pending validation covered independently; no v4 abort path.'),
 dict(deleted='test_garbage_line_after_rebind_blocks_it_but_not_later_ones',mapping=['test_astra7678.py::test_garbage_line_fences_everything_including_later_rebinds','followup7694.native_tails_order_edits'],assessment='Whole-journal fencing is stronger safety, deliberately loses earlier selective later-record availability.')
]
save('deleted-test-coverage.json',dict(source='d1239f9:tests/test_astra7669.py',tests=coverage,genuinely_lost='Exact old-protocol pytest cases and selective-marker/later-record availability assertions removed; old paths no longer supported. No current v4 fail-closed invariant found wholly uncovered once independent evidence included. Added independent clearance matrix and crash/fault coverage are evidence, not permanent repository tests.',deletion_rationale='No explicit deletion rationale found beyond v4 commit-record replacement in source/docs and new test module; do not invent author rationale.'))
notes=dict(changed_files=changed,diff_sha256=sha(E/'source/production.diff'),documentation=dict(protocol='Accurate pending-durable then commit; pending-only never replays.',chain='Unkeyed SHA-256, not MAC; file-permission threat model explicit. Broad removed-record claim needs clean suffix/whole-file rollback qualification; empty genesis has no externally anchored identity/tip.',whole_journal='Accurate at startup for unverifiable records; exact archived v3 witnesses migration-fenced and native v4 faults independently covered.',clearance='Archive byte identity, reset audit, re-journaling and success restart agree. Seven pre-rename failures preserve old bytes. Post-rename directory fsync failure leaves live fence but disk may already be new; no unconditional old-bytes promise. fence_clearances is live-process history, not reconstructed at restart; journal_reset durably audits actor/reason/archive.',commit_uncertain='Policy explicitly states replayed if commit survived, held if lost, fenced if torn. APPLIED is honest for memory, not durable success; stronger zero-byte-write witness returns True then holds on restart.',migration='README/policy explicitly v1-v3 whole-journal fence, clear and reissue; authentic v1/v2/v3 tested.',health='Appliance status includes rebind_journal_healthy; True denotes absence of known fence, not continuous verification. Runtime permission refusal can remain healthy. Missing startup file creates empty healthy journal.',runtime_change='OPEN Low F-runtime-integrity-overclaim: size/last-record check misses same-size earlier-record edit, permitting new rebind live; restart detects edit and fences. Policy says exactly what this process last wrote, broader than checked bytes.',snapshot='Explicitly unsupported suffix/snapshot restore; full ordered original stream needed, not a new blocker.',deleted_tests='See deleted-test-coverage.json; eight deleted and eleven added -> 785 versus 782; same count retained in other edited test files.'),findings={'closed':['F-abort-tail','F-journal-refused-compound','F-abort-order-scope'],'open_medium':['F-applied-without-durable-commit','F-journal-rollback-anchor'],'open_low':['F-runtime-integrity-overclaim']},gate='NOT APPROVED',scope='Review/evidence only; no product/test changes')
save('static-review.json',notes)
print(json.dumps(dict(source_files=len(after),source_verified=True,prior_manifests=True,guard=True,wheels=True,coverage_tests=len(coverage),gate=notes['gate']),indent=2))
