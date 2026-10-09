# Astra independent re-review 7694 — cf6a060

**Reviewer:** `openai/gpt-6-astra`, sole independent reviewer, no delegation or fallback. Own-session `sessions_list` confirms `gpt-6-astra`; own assistant `sessions_history` confirms model `gpt-6-astra`, provider `openai`, API `openai-responses`. Checks preceded this continuation and were repeated near completion; see [model verification](../experiments/20261008-astra-7694/model-verification.json). **Date:** 2026-10-08 (America/Vancouver). **Request:** review round 7694. **Reviewed pin:** `cf6a0601ddc03dcd87daab7f982cb97361ac7ee8`, parent `d1239f9`. Complete nine-file diff, interacting reducer paths, authored tests, README/policy and prior evidence inspected. Repository-operations and experiment-ledger procedures applied.

The same sole reviewer continued from session `agent:main:subagent:ce379868-8734-49fc-b8b2-9b17659d49ef` in `agent:main:subagent:58d4840d-3ff6-4ae5-afbe-193491620461`. The earlier session was interrupted by a provider content-refusal on one large embedded script, **not a model fallback or delegation**. Completed results were retained; the full suite was not rerun. This continuation ran the already-written focused witnesses, added clearance probes, completed the static audit and published the report.

**Evidence:** [index](../experiments/20261008-astra-7694/README.md), [primary results](../experiments/20261008-astra-7694/review7694.json), [focused followups](../experiments/20261008-astra-7694/followup7694.json), [sole full-suite output](../experiments/20261008-astra-7694/pytest.stdout). Artifact names below refer to that directory. Execution used clean detached `/tmp/hive-astra-7694-source`; **149 tracked non-experiment files remained byte-identical to both initial hashes and pinned Git blobs**. No production/test-source edits, old-evidence changes, scratch changes, delegation, paid/remote compute or deployment.

## Verdict and gate

**Production ownerless hold/rebind gate: NOT APPROVED.** All three OPEN 7678 findings are CLOSED by the new pending/commit protocol and whole-journal fencing, with exact archived v3 bytes and native v4 counterparts distinguished. Two Medium concerns remain for the current durable-recovery gate: a True/APPLIED return can have no commit bytes at all and revert to held on an ordinary restart; and whole-file rollback to an old valid journal can undo a deliberate clearance without detection or rehashing. A Low documentation/runtime-integrity overclaim is also open. Preserve the previously bounded explicitly-owned-plan gate; no operational gate is broadened.

| Item | Verdict | Result |
|---|---|---|
| F-abort-tail (residual F-abort-content) | **CLOSED — prior Medium** | Exact archived cancelled-tail bytes migration-fence; native v4 lost final newline, truncated/blank commit and refused pending tail fence without trimming or replay. |
| F-journal-refused-compound | **CLOSED — prior Medium** | Old compensating abort/marker path removed; archived compound witnesses fence; 24 native write/rollback modes contain no False-return resurrection. |
| F-abort-order-scope | **CLOSED — prior Medium, reordered-storage qualification** | Exact displaced-cancellation bytes fence; native commit-before-pending, pair reorder/interleave/removal/duplicate/edit cases fence the whole journal. |
| F-applied-without-durable-commit | **OPEN — Medium** | Commit write lands zero bytes, rollback fails: True, owner assigned/incident closed live; two ordinary restarts hold again and report healthy with no commit. |
| F-journal-rollback-anchor | **OPEN — Medium, old-journal restore qualification** | Empty genesis has no external identity/tip anchor; replacing a reset journal with the prior valid bytes revives deliberately discarded authorization without rehashing. |
| F-runtime-integrity-overclaim | **OPEN — Low** | Same-size earlier-record edit bypasses size/last-record check; next rebind succeeds healthy, then restart detects corruption and fences. “Exactly what this process last wrote” is too broad. |
| F-journal-refused-fsync / F-fence-remove-dir-fsync / F-fence-content | **CLOSED — retained Medium invariants, obsolete writer steps removed** | Pending-only never applies; legacy marker presence fences all; new fault matrix covers both pending and commit stages. |
| F-recovery-doc-overclaim | **CLOSED — retained prior Low exact statements** | Removed cancellation/marker wording replaced with explicit replayed/held/fenced commit-uncertain outcomes and archive/reset recovery. New narrower overclaim is separate above. |
| Durable fence clearance / v1-v3 migration | **CLOSED for tested boundaries** | Seven pre-rename failures preserve old bytes/live fence/audit; success archives exactly and carries applied p, not refused pending-only q; genuine v1/v2/v3 journals fence. |
| F-journal-content / F-tail-aside-short-write / F-unapplied-observability | **CLOSED — retained Medium / Low / Low** | Canonical-content/hash controls pass; startup never trims damaged bytes; pending-only dispositions remain observable. |
| Aggregate/default controls; prior foreign evidence/unregister/order/hold/preview | **CLOSED — retained High/Medium/Low** | 10,000-plan admission, configuration/migration, exact retained witnesses and lifecycle/schedule controls pass. |
| Snapshot/suffix recovery | **Unsupported, not approved as recovery capability** | Full ordered original event stream remains required; retained partial restore controls fail closed. |
| Authored suite / retained execution gates | **CLOSED as execution, not safety proof** | **785 passed**, exactly one full suite; primary 16/16, focused 12/12, final static exit 0. Defect assertions count as passing groups. |

## 1. Refused writes and live/restart agreement

### F-journal-refused-compound — CLOSED Medium

V4 durably appends `rebind_pending`, then `rebind_commit`; only the latter authorizes replay. There is no writer-side abort/marker-removal compensation window. `followup7694.json.exact7678_archived_witnesses` reuses the actual 7678 damaged bytes and event streams, not regenerated easier examples; legacy-format fencing excludes all of them. Native v4 controls independently establish closure rather than relying only on migration.

The 24-case `v4_fault_matrix` injects open, pre-write, zero/positive-short write, after-complete-write, before/after fsync, before/after truncate, rollback-fsync, close-after and compound failures for both pending and commit. For every False result, business-state comparison permits changes only in journal fields; no refused authorization replays. Positive short writes complete; post-close errors do not negate an already fsync'd record. Commit uncertainty is distinguished from refusal, not relabeled a clean success.

### (a) APPLIED versus UNCERTAIN — OPEN Medium F-applied-without-durable-commit

`followup7694.json.applied_no_commit` is stronger than a simulated lost page:

```text
pending write/fsync succeed
commit write raises BEFORE writing any bytes
rollback truncate raises
rebind -> True; owner(p)=i, incident i closed, audit applied
live fence.kind=commit_uncertain, applied=True
disk contains exactly ONE pending record and NO commit
ordinary restart twice + identical full stream:
  p held, i open, no owner; healthy=True; unapplied="no commit record..."
```

“APPLIED” is truthful about current memory, and the policy explicitly describes replayed/held/fenced restart outcomes. It is **not a durable-success acknowledgment**. The revised design closes refused-entry resurrection but does not meet caller/live/durable-restart agreement for the current production gate. Require an explicit structured UNCERTAIN result (with whether applied in memory and whether durable), or an enforced recovery contract that prevents treating True as durable authorization. This finding is not an accusation that a refused rebind revives, nor a documentation claim that restart always agrees: the docs accurately warn of the divergence.

### (d) Crash/fault coverage

The eight `crash_boundaries` modes interrupt before/after pending write, after pending fsync, before/after commit write, after commit fsync and before/after apply. Trace and restart state are recorded. These complement the 24-mode syscall fault matrix, not replace it. Repository tests cover pending-only crash reconstruction, pending uncertainty, commit uncertainty with intact/lost/torn outcomes and major corruption paths; they do not themselves instrument every step pair. The independent matrix fills that evidence gap.

These are abrupt `BaseException`/syscall-injection probes with fresh reducers, **not physical power-loss tests**. Bytes written but not fsync'd remain visible to the fresh process on this host; a real power loss may lose them. Neither a returned-result guarantee nor hardware durability is inferred from those intermediate stops.

## 2. Fence validation and durable clearance — CLOSED for tested boundaries

V4 treats **any** leftover legacy marker as a whole-journal fence, without narrowing to a trusted entry. Eight independent marker-content cases include unreadable bytes, malformed/array/empty JSON, edited ID, missing entry, nonlast and legacy-v1 shapes; all block replay/new rebind, and explicit clearance does not resurrect old authorizations. Authentic v1/v2/v3 journal fixtures fence and require inspect/clear/reissue.

`followup7694.json.clearance_fault_matrix` uses a live applied p and genuinely refused pending-only q. Injected archive write, archive file fsync, archive directory fsync, new-journal create, new-journal file fsync, new-journal directory fsync and rename failures all raise, preserve old bytes and live fence, leave `fence_clearances` unchanged, keep p applied and q held on restart. On success, the archive is byte-identical, the new first record is `journal_reset` with actor/reason/archive, and exactly p is re-journaled as pending+commit; restart matches live ownership.

An extra **post-rename directory-fsync** failure raises and leaves the live fence/audit unchanged, but the disk path already contains the new journal. Thus old-byte-preservation cannot be asserted after rename. Both observed old/new journals retain p and exclude q; no safety failure was found in this probe. This distinction accords with the source comment and prevents an invented all-failures-before-mutation claim.

Clearance audit entries are exposed by `journal_status()["fence_clearances"]` in the running process. Restart does not reconstruct that list; durable `journal_reset` retains actor/reason/archive. The policy does not explicitly promise persisted reconstruction. Archive/reset state beyond full-stream replay is not a snapshot API.

## 3. Cancellation integrity and the narrower corruption scope

### F-abort-tail / F-abort-order-scope — CLOSED Medium

There are no cancellation records in v4. Startup does not trim or skip a torn/blank line: it fences the whole journal, preserves bytes, refuses new rebinds and repeats that behavior across restarts. Native tests include commit newline loss, partial/complete malformed tails, whitespace replacement, commit-before-pending, reordered pairs, interleaving, middle removal, duplicated pairs, changed IDs/targets, invalid UTF-8, arrays and unknown operations. Exact original 7678 archived abort/cancellation fixtures separately migration-fence.

### (b) Hash-chain anchor — OPEN Medium F-journal-rollback-anchor

`prev=""` begins each journal; there is no separately anchored expected journal identity or latest tip. `archive_splice` first commits p, damages the tail, restarts fenced with p held, then clears with the explicit decision to discard the old authorization. The new reset-only journal holds p. Appending the archived prefix after the reset breaks the chain; restoring the full damaged archive remains fenced. **Replacing the file with its prior valid journal, or the clean prefix of that archive, is accepted healthy and closes p again without recomputing any hash.**

A separate clean archive produced after a refused next pending write is also accepted as a whole valid journal. That control alone is not an unsafe closure (its p was still applied), but establishes that archive identity is not checked. The discard/reset witness establishes the consequential revival.

This requires old-journal/backup rollback, not ordinary truncation of the current journal, and is not generated by intact append order. The untouched damaged archive is fenced in practice; a previously valid copy/clean archived prefix is **undetectable**. Severity Medium is qualified by this restore/storage precondition, not hostile hash forgery. A random ID inside the rollbackable file alone cannot solve whole-file rollback; an independently anchored expected identity/tip or enforced exclusion of such restores is needed for the broad recovery gate.

### (c) Duplicate/second commit

`duplicate_commit` confirms both fence the whole journal over two restarts. An exact duplicated commit reports **“hash chain broken (a record was reordered, removed or inserted)”**. A second commit for the same pending, correctly linked/rehashed to reach semantic validation, reports **“duplicate commit record”**. Controls additionally report **“commit record names no earlier pending rebind”** and **“commit record does not match its pending rebind”**. This is not merely deduplicating an unsafe journal and continuing.

### (e) Clean record-boundary truncation

`clean_prefixes` checks all five boundaries of the current four-record/two-rebind journal. Zero/one record authorizes neither; two/three authorizes only the first; four authorizes both. Every prefix is healthy, and lost commits only return plans to held. **No wrong closure for a prefix of the CURRENT journal.** This cannot be generalized to replacing a reset journal with an old valid whole journal, which can revive authorization deliberately omitted at reset.

## 4. Documentation, recovery and retained boundaries

The pending/commit protocol, whole-journal corruption fence, legacy migration, default refusal and volatile opt-out are accurately described. The policy explicitly states that commit_uncertain may be replayed, held or fenced on restart; no missing warning is alleged. Startup create/read failures fence; the appliance propagates `rebind_journal_healthy`. A missing startup file creates an empty healthy journal: the process cannot tell first use from journal loss.

### F-runtime-integrity-overclaim — OPEN Low

`startup_external_health` changes an earlier pending record's reason by one same-length character while leaving the final record and total length intact. The next rebind returns True with healthy=True; restart catches the hash mismatch and fences everything. The implementation checks only size and last-record bytes, whereas policy says the file must still be “exactly what this process last wrote.” Narrow that wording or validate the promised scope. No wrong-target closure was demonstrated: this is a live-health/integrity diagnostic overclaim and restart-availability divergence. Runtime PermissionError can also cleanly refuse while healthy remains True; healthy means absence of a known fence, not a continuously verified availability certificate.

The hashes are explicitly **unkeyed SHA-256**, not a MAC; file permissions are the stated malicious-writer boundary. That is an accepted limitation, not a demand for keyed authentication. Whole-file rollback above needs no rehashing and is a separate recovery-boundary concern. Broad “removed record breaks the chain” language should exclude clean suffix truncation/whole-file replacement.

Snapshot/partial replay remains expressly unsupported. Retained suffix-only and synthetic-hydrate controls stay pending/unapplied, not unsafe automatic closure. Full original ordered stream availability is a deployment/recovery limitation, not a new blocker by itself. Default argument/env precedence and real 9,999/10,000/10,001 tracked-plan admission controls pass; the plan cap is not a universal bound on all memory or old-journal size.

## 5. Authored tests and regression review

Eight old tests were deleted and eleven v4 tests added; other changed test files adapt protocol/status expectations without changing their test counts. The suite rises from 782 to **785**. There is no explicit deletion rationale beyond the v4 replacement evident in source/docs; do not attribute an unstated rationale to the author.

### (f) Deleted tests/test_astra7669.py coverage map

Full machine-readable mapping: `deleted-test-coverage.json`; exact deleted source is archived as `source/test_astra7669-deleted.py`.

| Deleted case | Surviving/inherited coverage and qualification |
|---|---|
| Marker unlink then directory-fsync failure | 7656 clean-refusal test; native 24-mode fault matrix and archived compound witnesses. Writer marker unlink no longer exists. |
| Abort plus marker compound failure | 7678 pending/commit-rollback tests; native fault matrix. Old compensating paths removed. |
| Edited outer marker op_id / missing entry | 7656 legacy-marker test; independent `old_markers` specifically retains both malformed forms. |
| Valid marker not naming last entry | Presence-only whole-journal fencing, independent nonlast marker case. Hash-valid-v2-specific assertion removed with its validator. |
| Intact marker fences only its entry | **Selective availability coverage intentionally lost**; the documented new rule fences everything. Safety strengthened, selective contract discontinued. |
| One-character abort op_id edit | 7656 edited-record test; independent native deciding-record edits/tails and exact archived legacy fixtures. No current abort parser. |
| Rehashed abort naming no rebind | 7678 rehashed bad-chain commit test; independent missing-pending/mismatched-pending semantic cases. |
| Garbage after rebind | 7678 garbage-line test plus independent native corruption; whole-journal fencing replaces before-only availability. |

Exact old-protocol pytest cases are genuinely no longer permanent tests. Selective-marker/later-record availability assertions are intentionally not preserved. No current v4 fail-closed invariant was found wholly uncovered once the independent evidence is included; **independent evidence is not a substitute for permanent regression tests**, and authored tests alone do not contain the full crash/clearance/fault matrices.

No regression was found in retained accepted event ordering, owner/foreign isolation, hold lifecycle, actual unregister/reregister APIs, quiet preview, canonical hashing, default configuration or explicitly-owned supersession schedules. No production/test source was changed to obtain these results.

## 6. Execution and regression accounting

**Full suite exactly once: 785 passed in 47.86s**, exit 0, runner wall **48.4249s**. Python 3.10.12, pytest 9.1.1, build 1.5.0; offline wheel hashes verified. Primary **16/16**, focused **12/12** (including the added clearance group), final static exit 0. Followup wall 0.8686s; added clearance 0.3156s; final static 0.6694s.

The initial static run failed solely because changed test-source archive files were missing. `archive_sources7694.py` copied the unchanged pinned source files; the final static rerun succeeded. Both logs are retained. No suite or completed semantic harness was rerun, and no product fix was made.

| Retained/independent coverage | Result |
|---|---:|
| Owned supersession schedules | 1,440; 15,840 states |
| Hold/rebind schedules | 144; 1,152 event-prefix checks |
| N1–N4/mixed receipt controls | 398/398 |
| Current/prior-ordered semantic sweeps | 3,072/3,072 each |
| Legacy fail-closed / original witnesses | 384/384; 2/2 |
| H2/N9/N10 7173 / N9/N10 7195 | 10/10; 7/7 groups |
| Exact retained foreign/unregister/journal-order/canonical/hold controls | All asserted primary groups pass |
| Authentic legacy quarantine | 300 → 151 → 0, retained recovery-text adaptation |
| Real aggregate plan admission | 9,999/10,000/10,001 attempts; at most 10,000 tracked |
| New v4 write/rollback modes / abrupt step boundaries | 24 / 8 |
| New native tail/order/edit cases | 15 plus refused-pending tail |
| Duplicate/second/missing/mismatched commit | 4 |
| Clean current-journal prefixes | 5 |
| Legacy marker shapes / authentic v1-v3 migration | 8 / 3 |
| Clearance durability modes | 7 pre-rename faults + post-rename fsync fault + success |

Retained helper adaptations and provenance remain in `witness-adaptation.diff`, `retained-extraction.json`, `copy-provenance.json` and primary output. Successful groups include asserted defects, not 28 safety approvals.

Unchanged `semantic_7133.py` exits **1** for the same three obsolete legacy automatic-closure expectations; actual outcomes remain fail-closed. Raw failures are retained, not relabeled passes or counted as authored-suite failures. Current/prior/legacy fail-closed sweeps and separate rebind controls pass. Runner records command, cwd, stdout/stderr, exit and wall time for every execution.

## Publication integrity

Only this report and `experiments/20261008-astra-7694/` are published. All **149 tracked non-experiment files** match initial hashes and pinned Git bytes; detached source is clean. Prior evidence verification passed **315 (7669)** and **351 (7678)** artifact/report hashes. Inputs include the complete `d1239f9..cf6a060` nine-file diff, all changed source files, deleted test, retained helpers and provenance.

The Python socket guard rejects external connects and pip is offline; this is not an OS-wide network sandbox. No paid/remote compute or deployment occurred. Disposable test/build files, bytecode, third-party wheels and large padding fixtures are excluded with hashes/recipes retained. Raw archived patch/log whitespace is preserved separately from authored whitespace checks. The SHA-256 manifest includes this report, with complete read-only verification. Exact staged index bytes are scope-checked and credential-pattern scanned before commit. Publication is fast-forward-only to origin/main; fetched remote/local equality is recorded outside the published manifest after commit to avoid self-reference. Scratch and old evidence are untouched.
