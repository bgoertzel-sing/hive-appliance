# Astra independent re-review 7669 — d0fc184

**Reviewer:** `openai/gpt-6-astra`, sole independent reviewer, no delegation or fallback. Own-session `sessions_list` confirms `gpt-6-astra`; own assistant `sessions_history` confirms model `gpt-6-astra`, provider `openai`, API `openai-responses`. These checks preceded the review and were repeated; see [model verification](../experiments/20261008-astra-7669/model-verification.json). **Date:** 2026-10-08. **Request:** review round 7669. **Reviewed pin:** `d0fc184d6cbbd6381243d55901219b6b1ba41721`, verified equal to main and origin/main after fetch; parent `7a372c3`. Reviewed the complete five-file diff, changed implementation/tests/docs and interacting reducer paths, review 7656 and its execution/evidence procedure. Repository-operations and experiment-ledger skills applied.

**Evidence:** [index](../experiments/20261008-astra-7669/README.md), [primary results](../experiments/20261008-astra-7669/review7669.json), [focused followups](../experiments/20261008-astra-7669/followup7669.json), [sole full-suite output](../experiments/20261008-astra-7669/pytest.stdout). Artifact names below refer to that new evidence directory. All execution used a clean detached `/tmp/hive-astra-7669-source`; **146 tracked non-experiment files remained byte-identical both to their initial hashes and the pinned Git blobs**. No production/test-source changes, old-evidence changes, scratch changes, paid/remote compute or deployment.

## Verdict and gate

**Production ownerless hold/rebind gate: NOT APPROVED.** The exact 7656 failed-append/failed-truncation witness is repaired, but **F-journal-refused-fsync remains OPEN Medium at fence removal**: successful unlink followed by failed directory fsync returns False, yet a fresh reducer applies the refused operation. Two additional Medium corruption-handling witnesses allow an uncertain or explicitly cancelled entry to replay. These are concrete fresh-reducer reproductions, not claims about hypothetical physical power loss. Preserve the previously bounded explicitly-owned-plan gate; no operational gate is broadened here.

| Item | Verdict | Result |
|---|---|---|
| F-journal-refused-fsync | **OPEN — Medium, narrower residual** | Original append-fsync + failed-truncate witness CLOSED; close-after-durable-write CLOSED. New removal-directory-fsync witness returns False but restart closes i. Alias: F-fence-remove-dir-fsync. |
| F-journal-content | **CLOSED — prior Medium, exact witness** | Same IDs with final receipt `verified=False→True` now change the digest; journal is unapplied and p remains held. Edited owner-rebind entry also fails its self-hash. |
| F-fence-content | **OPEN — Medium, new** | Parseable marker with an altered `op_id` is trusted without validating its embedded entry; the actual uncertain entry replays despite an indeterminate status. |
| F-abort-content | **OPEN — Medium, new** | One-character corruption of abort `op_id`, without recomputing its hash, is warned about but honored under the wrong ID; the original cancelled operation replays and closes i. |
| F-tail-aside-short-write | **CLOSED — prior Low** | Positive short writes are completed; zero-progress, errors, fsync/readback/pre-truncation faults preserve the original and refuse. Startup and runtime exercised. |
| F-unapplied-observability | **CLOSED — prior Low** | Exact 201 v2 records and 201 current-format mismatches: total 201, status 200, omitted 1, complete independent-copy enumeration 201. |
| Aggregate resource/admission policy | **CLOSED — prior Low, tracked-plan scope** | Real unpatched 9,999/10,000/10,001 attempts produce 9,999/10,000/10,000 tracked plans; new plan refused, incident open, existing holds/state retained. Not a universal memory bound. |
| Recovery/migration documentation | **CLOSED — prior Low omission** | README/policy now cover default journal requirement, env/argument precedence, v1/v2 reissue, full-stream replay and fence clearance. |
| F-recovery-doc-overclaim | **OPEN — Low, new accuracy issue** | “Marker STAYS” is false at the reproduced unlink/fsync boundary; “any” tail step failure leaves original untouched is false after truncate succeeds and journal fsync fails. |
| Durable fence clearance | **CLOSED for intact records; corruption qualification above** | Abort record fsync precedes unlink and directory fsync; actor/reason durable; cancelled entry absent through two restarts; explicit reissue works. |
| Prior unregister/order/tail/default controls | **CLOSED — retained High/Medium** | Exact unregister through appliance path, all three ordered streams, normal ASCII/UTF-8 tail recovery and journal-default controls pass. |
| Prior foreign evidence/hold expiry/preview/recovery text | **CLOSED — retained High/Medium/Low** | Retained witnesses, restores/replays, silent preview and nonvacuous recovery-text mutant check pass. |
| Authored suite and retained gates | **CLOSED as execution, not full safety proof** | **774 passed**, exactly one full-suite run. Independent primary 27/27 plus focused 4/4 assertion groups, including explicit defect reproductions. |

## 1. F-journal-refused-fsync — original witness repaired, residual OPEN Medium

### Original 7656 refusal and close witnesses — CLOSED

The original sequence is held p linked to i, successful i evidence, candidate i, then rebind. Injecting journal append fsync failure **and** ftruncate failure leaves the complete entry plus `<journal>.fence`. Live rebind returns False; fresh serialized replay leaves i open, p held, owner/audit absent and startup indeterminate visible. Another rebind refuses. The persistent marker fixes the original live-only fence.

Clean rollback truncates and fsyncs, removes the marker and returns False without replay. A failed second append preserves a prior committed entry byte-for-byte and replays only that first operation. The old all-fsync-fail injection now fails earlier, while fsyncing the temporary fence, before any journal append; fresh replay remains held. A raw close error **after the actual journal close and successful commit fsync** now returns True, applies live and replays consistently. The injected descriptor is genuinely closed, not leaked.

The normal syscall trace independently observes:

```text
write complete fence.tmp → fsync(fence.tmp)
rename into fence → fsync(parent directory)
append entry → fsync(journal)
unlink(fence) → fsync(parent directory)
only then mutate live owner/audit
```

Both directory fsync calls exist. Their presence alone does not establish correct error handling.

### F-fence-remove-dir-fsync — OPEN Medium

At `hive/reducer.py:619`, `os.unlink()` can succeed before `_fsync_dir()` raises. The handler at line 621 raises `_JournalIndeterminate`, but cannot truthfully claim the marker remains on disk.

Exact independent witness (`fence_fault_matrix`, mode `remove_directory_fsync`):

```text
hold p for i; collect successful i receipt; record candidate i
fence creation + parent fsync succeed
journal append + fsync succeed
unlink(<journal>.fence) succeeds
inject error on following parent-directory fsync
rebind(...) -> False; live p held, i open; indeterminate.persisted == False
fresh reducer(same journal); identical full serialized replay
# no marker; indeterminate is None; owner(p)=i; i closes; audit says replayed
```

This reproduces the requested refused-operation restart failure without modifying event/journal content. **Required closure:** define and enforce a recoverable commit/refusal boundary. If reporting indeterminate/refused, ensure a durable disposition blocks later automatic authorization, including when unlink has already succeeded. Merely attempting directory fsync or reporting an in-memory fence is insufficient.

Twenty syscall-fault modes cover fence open/write/fsync/rename/directory fsync, journal open/write/short write/error-after-complete-write, append fsync before/after the real call, truncate before/after, rollback fsync, close, and unlink/directory-fsync on success and rollback. Six abrupt-control-flow probes cover before fence, temporary marker before rename, after fence/before append, after append/before removal, during rollback and after unlink/before directory fsync. These use `BaseException` escape followed by fresh reducers, not real power cuts. A crash after unlink has commit ambiguity because the call never returned; the explicit error-return witness above is the concrete defect. There is no Python flush boundary in this raw-descriptor implementation.

## 2. Content integrity, fence corruption and abort corruption

### F-journal-content — CLOSED prior Medium

Exact 7656 stream: linked i/j, ownerless p, successful i receipt, failing i receipt, PLAN(p,i), then audited rebind. Original execution leaves i/j open. Replay with the same IDs/order and only the last receipt's `verified` changed False→True now reports a stream mismatch and leaves p held and both incidents open. An owner-rebind entry edited from target i to j without updating its hash is separately unapplied.

Canonicalization controls reverse nested object key order, change JSON whitespace and represent the same Unicode characters as escapes versus literal UTF-8. Digests and replay remain identical. Timestamp, source, subject, severity and schema-version changes separately fail replay. The scope is JSON-compatible string-key payloads; fallback `repr` for non-JSON mixed-key objects is not a portable canonical serialization. Unicode normalization forms with different code-point sequences are different content, not asserted equivalent.

The policy appropriately describes unkeyed SHA-256 as accidental/naive edit detection, **not** tamper resistance against a writer recomputing hashes. No keyed-authentication requirement is invented here. The following defects matter even within that narrower corruption-detection scope.

### F-fence-content — OPEN Medium

`_load_fence` at `hive/reducer.py:418` accepts any nonempty string `op_id`, without requiring a valid matching embedded entry. `_parse_journal` then fences only that ID.

Witness: first create the genuine append-fsync + rollback-failure state, with complete uncertain journal entry and matching fence. Change only the marker's outer `op_id` to another string, leaving its embedded original entry untouched. Fresh full replay **sets owner i and closes i**, although `journal_status()['indeterminate']` is present. A marker containing only an unrelated `op_id`, without any embedded entry, has the same effect. Subsequent new rebinds refuse, but the unsafe replay has already occurred.

Malformed JSON, invalid UTF-8, arrays, empty objects and injected permission-denied reads correctly fence everything. A **complete matching entry plus intact marker** also correctly stays fenced: completeness is not treated as proof of successful commit. The gap is parseable corruption, not unreadable garbage. **Required closure:** validate marker structure/content and operation binding; any untrustworthy or inconsistent marker must conservatively fence replay, not selectively exclude an unrelated ID. The witness does not recompute any hash.

### F-abort-content — OPEN Medium

`_parse_journal` at `hive/reducer.py:509` warns on an abort hash mismatch but honors its `op_id` anyway, on the rationale that abort is the safe direction. That is not safe when the corrupted field identifies **which** operation must never replay.

Focused witness (`followup7669.json.abort_content_corruption`):

```text
produce complete uncertain rebind X and durable fence
clear_journal_fence(actor='reviewer', reason='cancel this uncertain rebind')
# abort(X) fsync'd; fence removed; intact restart correctly stays held
change ONE hex character in abort record's op_id; leave entry_hash unchanged
fresh full replay, then another fresh full replay
# hash mismatch logged, but abort(wrong-id) honored
# original X replays; owner(p)=i; i closes; unapplied is empty
```

The cancellation was successful and durable before the corruption. **Required closure:** a corrupt cancellation must not release the possibly cancelled original authorization. Conservatively fence affected/unknown operations or the journal and require inspection; simply trusting, or discarding, an untrustworthy abort ID can both reauthorize the original record. Severity Medium reflects the changed/corrupted-storage assumption, consistent with 7656's content finding; this is not a claim about hostile authenticated-store compromise.

## 3. Fence clearance, tail recovery and observability

### Intact fence clearance and fault behavior

Nonempty actor/reason are validated. The abort JSONL includes them plus operation ID, timestamp, fence error and self-hash. Independent tracing sees the **complete abort record and existing marker at journal fsync**, then unlink, then directory fsync. The operation stays unapplied through two fresh restarts; explicit reissue creates a new replayable operation. `journal_status()['fence_clearances']` is live-only, not reconstructed at startup, but the durable actor/reason audit is retained in JSONL.

Eight clearance fault/crash modes cover zero write, append fsync, simultaneous rollback failure, unlink, directory fsync, crash before abort, after durable abort/before unlink, and after unlink. All leave the cancelled/uncertain operation unreplayed through two fresh reducers: either the marker persists or the durable abort excludes it. A complete matching entry with a deliberately reinstated marker also requires explicit clearance and stays cancelled over two restarts. The corrupt-abort qualification in §2 is separate.

### F-tail-aside-short-write — CLOSED Low; documentation accuracy OPEN Low

The exact earlier short-copy witness now loops to write the **whole** fragment in 3-byte pieces, fsyncs it, verifies size/readback, fsyncs its parent directory and only then truncates. Successful startup/runtime recovery preserves all fragment bytes and subsequent entries replay. Eighteen startup/runtime cases cover positive short writes, zero progress, error after short write, aside fsync, readback mismatch, short original read, aside-directory fsync, truncation and journal fsync.

Failures before truncation leave the original bytes untouched and refuse/startup-raise. However, when `ftruncate` succeeds and the following journal fsync raises, the original is already truncated; the **complete, verified durable aside** still contains the fragment. This is not the old forensic-data-loss bug. It disproves the policy's blanket “If any step fails, the journal is left untouched.” Together with the false “marker STAYS” assertion at the removal failure above, this is **F-recovery-doc-overclaim, OPEN Low**. Document pre-truncation versus post-truncation failure states and actual uncertain-marker handling accurately.

Normal ASCII/invalid-UTF-8 torn-tail witnesses and complete-invalid-line isolation remain passing. A corrupt line later invalidating cancellation is not safely covered by that older skip-invalid-line rule; §2 identifies the concrete valid-JSON abort counterexample.

### F-unapplied-observability — CLOSED Low

The exact 201 v2 mismatch records become legacy-unapplied; additionally 201 valid-self-hash v3 records with mismatching streams exercise the current path. Each gives pending 0, status history 200, total 201, omitted 1 and all 201 through `journal_unapplied()`, including original first and last IDs. Mutating the returned list does not mutate reducer diagnostics. The documented retention cap is 10,000; this is not unlimited historical enumeration.

## 4. Real caps, defaults, migration and recovery limitations

### Aggregate tracked-plan admission — CLOSED Low, scoped

No limit constant was patched. Full event reduction registers one held plan and 9,999 additional plans, then attempts a new owned plan for an open incident:

| Attempted plans | Tracked plans | Refused count | Original hold |
|---:|---:|---:|---|
| 9,999 | 9,999 | 0 | retained |
| 10,000 | 10,000 | 0 | retained |
| 10,001 | 10,000 | 1 | retained |

The refused plan is absent from tracking; its incident stays open even after a matching successful receipt. Existing plan rebind/fresh evidence still work at capacity without dropping any tracked plan. Separately, retained 600-hold controls preserve **all** holds through candidate overflow and local restore; after 270 rebinds, audits are bounded 256 local/200 hive, cumulative count 270, holds 330. Real 255/256/257 candidate boundaries and five actual-size 64 MiB journal boundaries still pass.

This closes the missing **tracked-plan admission policy**, not every possible resource bound. Open incidents, buffered receipts and oversized pre-existing journal loading are not universally bounded by `MAX_HIVE_PLANS`. No OOM measurement or comprehensive compaction workflow is claimed.

### Defaults, v1/v2 migration and plain-hash scope

README and policy now say `HiveAppliance` refuses rebinds without a journal unless explicitly volatile, explain argument/environment precedence, and distinguish bare `HiveReducer`'s volatile default. The default/opt-out/env/explicit controls pass.

The docs explicitly reject both v1 and **v2, the 647fac6 format**. The harness copies an authentic v2 entry from 7656 evidence and replays its actual original serialized stream: legacy-unapplied, owner absent, hold retained. Explicit operator reissue creates v3 and later replay works while preserving the v2 diagnostic. Recovery/migration omission is therefore **CLOSED Low**, apart from the new accuracy issue above.

### Snapshot/partial replay: documented unsupported path, not a new unsafe-closure finding

There is still no native hive `snapshot()`/`restore_snapshot()` API. The retained suffix-only replay and explicitly synthetic state hydration stay pending or become unapplied with p held; they do not silently authorize. Policy now explicitly requires the full original ordered stream and says snapshot/suffix restore is unsupported. The bounded in-memory event bus is not a durable globally ordered archive, and local checkpoints do not restore hive sequence/digest.

This remains an availability/recovery integration limitation, not a demonstrated new unsafe closure or evidence that snapshot recovery works. Deployments must actually possess the full ordered stream; configuring this journal alone is not a complete autonomous-recovery solution. No new Medium/High gate defect is inferred solely from absence of an unsupported API.

## 5. Authored tests and regression review

The two edited `tests/test_astra7638.py` tests now fail **the journal descriptor's** fsync, not the first global fsync. With the new protocol, failing the first global fsync would stop in fence creation and never exercise append rollback. This retargeting preserves the original proof rather than weakening it: existing rollback/live-fence assertions remain, and the clean-refusal case additionally asserts marker absence. The new test suite adds restart/cancel/reissue checks for the intact marker.

The authored tests inspected do **not** separately inject fence-file fsync or fence-directory-fsync failure; independent `all_fsync_fail`, `fence_fsync`, fence-create directory fault and startup fsync controls now exercise those paths. Authored tests also do not cover the three reproduced Medium defects. Their “short copy” test injects zero progress; independent controls add real positive short copies and readback verification. Their cap test patches the constant to 2; the independent boundary above uses 10,000 unchanged. These distinctions explain why 774 passing tests do not satisfy the production gate.

Rejected conflicting PLANs retain the permitted diagnostic-only counter increment and do not change accepted-event position/hash. Exact three original journal orderings replay identically; identity/content/order mismatches stay held. Prior foreign progress isolation, held-plan lifecycle/unregister through real appliance tick/register APIs, trusted plan-only-evidence qualification, quiet preview and recovery-text mutation controls are retained. Unkeyed integrity remains appropriately scoped as described in §2.

## 6. Execution and regression accounting

**Full suite exactly once: 774 passed in 47.23s**, no failures/skips; runner wall 47.79s. Python 3.10.12, pytest 9.1.1, installed build 1.5.0 (not requirements-dev's 1.6.1); offline packaging-wheel hashes verified. `run_primary.py` runs the suite once and retained historical probes. Primary review **27/27**, focused followup **4/4**, static verification exit 0. These groups include asserted defect reproductions, not 31 safety approvals. No initial fixture failures or suite reruns.

| Retained/independent coverage | Result |
|---|---:|
| Exact foreign 7582 witnesses | 4/4 both reducers; 10 ordering variants plus mixed/unknown-source controls |
| Hold/rebind schedules | 144 / 1,152 event-prefix checks |
| P3-ownerless schedules | 180 / 1,224 states |
| Owned supersession schedules | 1,440 / 15,840 states |
| Owned positives / foreign-owned controls | 6/6; 4/4 |
| N1–N4/mixed receipt controls | 398/398 |
| Current / prior-ordered semantic sweeps | 3,072/3,072 each |
| Legacy fail-closed / original witnesses | 384/384; 2/2 |
| Ownership lifecycle / authentic ownership / namespace | 48/48; 6/6; 1/1 |
| N8 boundary/disk | 14/14 |
| Explicit stale disk / rebind / pending liveness | 6/6; 8/8; 6/6 |
| H2/N9/N10 7173 groups | 10/10, including 51 H2 schedules |
| N9/N10 7195 groups | 7/7, including 64 receipt schedules |
| Authentic legacy quarantine | 300 → 151 → 0; 20 JSON roundtrips per stage; history 256 |
| H-oracle / F7 | Five poisoned-health controls detected; completeness mutant caught by both negatives |
| Fence/append/rollback/close syscall faults / abrupt crash boundaries | 20 / 6 |
| Clearance faults/crashes / malformed or corrupted marker cases | 8 / 7 |
| Torn-tail startup/runtime cases / startup creation fsync faults | 18 / 2 |
| Actual limits | 5 journal sizes; 255/256/257 candidate keys; 600 retained holds; 9,999/10,000/10,001 plan attempts |

The 300-plan helper retains the prior sole recovery-text adaptation; the 600-hold helper retains the same three documented candidate-cap substitutions. Their extracted/adapted hashes are recorded. The F7 failure-guard-only mutant still survives because intact completeness already excludes failed indices; this is not hidden as a detection.

Unchanged `semantic_7133.py` exits **1** for the same three known obsolete legacy automatic-closure expectations, with actual fail-closed outcomes. Raw failures are retained, neither relabeled passes nor counted as authored-suite failures. Current/prior/legacy fail-closed sweeps and separate explicit-rebind controls pass.

## Publication integrity

Only this report and `experiments/20261008-astra-7669/` are committed. The isolated worktree remained clean and all 146 tracked non-experiment files matched pinned Git bytes. Prior 7656 evidence verification passed **243 artifact/report hashes**. Archived inputs include the complete five-file diff, changed sources, policy/setup inputs, copied helper provenance and actual fault journals. Outputs, stderr, exit statuses, wall times, high-confidence credential scan results and complete SHA-256 manifest accompany the report.

Python socket guard blocks external connects and pip uses offline wheels; this is not represented as an OS-wide network sandbox. No paid/remote compute or live deployment occurred. Disposable test/build files, bytecode, third-party wheels and large 64 MiB padding fixtures are excluded; wheel/fixture hashes and recipes remain. Raw patches/log whitespace is preserved; new-authored whitespace checks are separate. `verify_evidence.py` is read-only and checks complete coverage. Staged content is credential-scanned before commit. Publication is fast-forward-only to origin/main; fetched remote/local equality is checked after commit and recorded outside the manifest to avoid self-reference. No scratch or old evidence is staged.
