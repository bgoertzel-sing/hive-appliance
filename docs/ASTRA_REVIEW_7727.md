# Astra review 7727 — rebind-journal reset durability and recovery

## Verdict: NOT APPROVED

Reviewed **`7ce5cd5c2c3289ee1ce9f50c2683854e038df0d0`**, specifically **`git diff 30e3d39..7ce5cd5`** (Protomega2's 7718 fixes). Sole independent reviewer: **`openai/gpt-6-astra`**, verified using this session's runtime metadata and assistant-history provider/model fields. No delegation, substitute model, paid compute, commit or push.

The two 7718 defects are **closed in their corrected scopes**: reset drops and fences pending decisions before storage work; an established reset-intent blocks startup throughout the replacement transaction. All retained storage boundaries and the expanded matrices preserve that result. However, the new recovery diagnostic **equates marker existence with durability**. It can positively promise that every restart will fence before either required fsync has occurred, or after intent fsync and cleanup both fail. This is a new **Medium** recovery-assurance finding: the documented `intent_durable: false` / keep-service-stopped boundary is not reliably reported. It blocks this storage-durability production gate, not the accepted unkeyed-hash architecture.

Evidence: [index](../experiments/20261008-astra-7727/README.md), [ledger](../experiments/20261008-astra-7727/RUN.md), [reset matrix](../experiments/20261008-astra-7727/reset7727.json), [intent controls and durability witnesses](../experiments/20261008-astra-7727/intent-final7727.json). Exactly pinned source was exported to `/tmp/hive-astra-7727-source`; historical evidence was read through its `experiments` link. **817 tests passed**, full suite exactly once. Production and test files and `scratch/` were not modified.

## Findings

| Finding | Status / severity | Evidence and scope |
|---|---|---|
| F-reset-interruption-replays-restored-pair (7718) | **CLOSED — Medium, established-intent scope** | 24 healthy-pair / 28 legacy-marker storage operations, 208 before/after Crash/OSError injections. No discarded replay once the intent helper has completed; all eight old-pair restarts are within failed/uncompleted intent establishment, with the original pair unchanged. The new durability-reporting issue below qualifies the pre-intent boundary. |
| F-reset-error-live-pending (7718) | **CLOSED — Medium** | 104 error cases leave the process fenced and pending empty; verify then clear writes zero rebinds and remains held through two restarts. Another 48 live-feed cases stay blocked without clearance; 48 reset retries complete held. The exact formerly dangerous late replacement failure no longer resurrects p. |
| F-reset-intent-durability-status | **OPEN — Medium** | `hive/reducer.py:1077` derives `intent_durable` from `os.path.lexists(ip)`. Empty, never-fsync'd intent and failed-fsync/failed-cleanup witnesses report True and promise every start fences. A modeled loss of the unsynced marker leaves the unchanged old pair replayable. |
| Intent startup / damaged markers / recovery | **CLOSED — Medium, tested requirements** | 42 marker/pair combinations fence before create/adopt/replay; malformed, partial, empty and mode-000 files need no parsing. Directory-in-place stays safely blocked; clearance raises rather than deleting a directory. Missing/mismatched anchors and active legacy markers cannot bypass intent. |
| Clearance after interrupted reset | **CLOSED — Medium** | 72 additional intent-bearing clearance interruptions, 18 storage operations; new rebind-free pair precedes marker deletion; interrupted/failed clearance never revives p. |
| F-joint-rollback-doc-scope / F-clean-suffix-doc-overclaim (7708) | **CLOSED — Low, retained scopes** | Exact restore timeline: successful reset archives both files byte-for-byte; p held through two restarts; explicit reissue durable through two more. Policy correctly distinguishes clean suffix truncation from torn/middle modification. |
| Identity, legacy startup, rebind-result ambiguity, single-file rollback, runtime integrity | **CLOSED — retained Medium/Low scopes** | Retained 7701/7708 focused groups, 48 first-use and 80 clearance injections, 24 explicit startup recoveries, eight active-marker variants pass. |
| Abort-tail / refused compound / order / stream-content / default journal / foreign isolation / unregister / hold-preview | **CLOSED — retained High/Medium/Low scopes** | 16 primary and eight focused journal groups; 1,440 supersession and 144 hold/rebind schedules rerun. |
| Snapshot / partial replay | **CLOSED — Low documentation scope; unsupported recovery capability** | Policy requires the full original ordered event stream; no snapshot/partial-replay recovery approval inferred. |
| Full suite | **CLOSED — independent verification** | **817 passed in 51.57 s**; runner wall 52.1323 s, exit 0. Author's claimed count independently reproduced; author's execution provenance not independently verified. |

## 1. Reset order and the two prior findings

The new order is at least as safe as an archive-first proposal **after intent establishment**: discard pending decisions and fence in memory; create/fsync intent and its directory; rename old journal aside and sync; copy old anchor; write new anchor; write new journal; move legacy markers aside; unlink intent and sync. The marker protects the whole archive/replacement interval, not just the mismatched-identity interval. Moving it before the journal rename is a sound design choice.

The retained reset harness was adapted, not silently replaced: [adaptation diff](../experiments/20261008-astra-7727/adaptation-7727.diff). Its former **80 healthy-pair injections / 40 error cases** expand to **96 / 48** because the healthy trace grows from 20 to 24 storage operations. Legacy markers expand the trace from 24 to 28 operations (**112 / 56**). Combined: **208 injections**, **188 fenced restarts**, **12 healthy new-pair/held restarts**, **eight unchanged-old-pair restarts during intent establishment**, **zero live authorization replay after error recovery**. Every original type of storage boundary remains covered, including both marker moves and the new intent deletion.

All 104 caught OSError cases have pending=0 and unhealthy status before recovery. `verify_journal()` returns False; `clear_journal_fence()` carries zero decisions and writes only header + reset. Live replay and two subsequent restarts remain held. A separate matrix resumes **48** failed live reducers without clearing and another **48** via successful `reset_journal()` retry. The old late-new-journal-durable witness passes for both direct replay and verify/clear.

Additional I/O coverage extends the healthy trace to **48 calls**, injecting **48** before/after errors at the added directory-open, fstat and close calls, plus **four** anchor open/read failures. These are supplemental errors, not included in the 208 storage mutation/durability injections. They leave no pending decision and recover without re-journaling p. [Extra I/O evidence](../experiments/20261008-astra-7727/extra-io7727.json).

The unavoidable boundary where intent cannot be established is acceptable **only with an accurate conservative diagnostic and a stop/retry requirement**. Before any change to the journal/anchor pair, a fresh process cannot infer an invocation that left no durable marker. Eight ordinary-restart outcomes exhibit that boundary; cleanup can also remove a marker after a failing/uncertain durability call, while leaving the old pair unchanged. A returned failure is not permission to serve/replay a restored pair. The policy correctly calls for the service to remain stopped, but the new status field and positive durability message violate that distinction below.

## 2. F-reset-intent-durability-status — OPEN Medium

Locations: `hive/reducer.py:1077` (existence used as durability), `:1082` (positive every-start guarantee), `:1096` (audit field); policy reset-failure paragraph at `docs/POLICY_MULTI_PLAN_SUPERSESSION.md:150` onward.

`durable = os.path.lexists(ip)` measures namespace visibility in the running OS, **not completion of file and directory fsync**. The code then records `intent_durable: true` and says “The reset-intent marker is durable: every start fences …”. This is stronger than the evidence it has.

Two independent witnesses are retained in `intent-final7727.json → intent_durability_reporting`:

1. Interpose immediately after the successful O_CREAT of the intent, before the helper's protected body: raise OSError at this return boundary. The resulting intent is empty; **zero fsync calls** occurred; old journal and `.id` are byte-identical. The failure nevertheless records `intent_durable: true` and the positive every-start-fences message. This is the same before/after-call fault model used in the retained matrices, not a claim that ordinary `open()` both succeeds and returns an errno.
2. A syscall-like compound failure: intent file `fsync` raises EIO, and attempted cleanup `unlink` raises EACCES. The visible marker remains, neither file nor directory durability was acknowledged, and the same True/durable/every-start guarantee is emitted. This second witness does not depend on the synthetic successful-open return-boundary exception.

For the first witness only, a separate **modeled power-loss outcome** removes the unfsync'd marker entry and restarts against the unchanged old pair: p returns. This models a permitted persistence outcome, **not a hardware power-loss test**. Ordinary process restarts while the marker remains visible correctly fence. Neither witness revives pending p inside the failed live reducer.

**Required correction:** separate marker presence from confirmed durability. Track successful intent establishment explicitly, and handle pre-existing/unknown-durability markers conservatively (or explicitly synchronize them before asserting durability). A failure before that confirmation must not assert every restart will fence; it must expose unknown/not-confirmed durability and retain the keep-service-stopped, retry-before-replay instruction. Preserve the safe in-memory discard and established-intent transaction behavior. Documentation must also distinguish “old pair unchanged” from “nothing changed on disk”: a partial/empty intent can already exist.

Severity is **Medium** because the new operator-facing recovery assurance can authorize reliance on a startup fence that has not been durably established during the prescribed joint-restore procedure. This is narrower than the old late-reset pending-rebind resurrection defect, which is fixed. The verdict would change after a concrete correction and a rerun of these witnesses plus the affected reset boundaries; no broader architectural redesign is requested.

## 3. Leftover intent, legacy artifacts, anchor checks and completion

The 42 controls cross six intent forms (empty, partial JSON, non-UTF8/damaged, genuinely unreadable mode-000 under the non-root uid, directory, dangling symlink) with seven pair/artifact states (healthy, both active legacy markers, missing anchor, missing journal, mismatched anchor, both absent, old `.reset-<ns>` artifacts). Startup always reports `reset_incomplete`, loads no pending entry and leaves disk unchanged. No marker content is trusted or required; namespace presence is deliberately sufficient to **block**, though not sufficient to assert **durability**.

Clearance carries zero decisions across all forms it can remove. A directory at the intent path makes `unlink` raise `IsADirectoryError`; the current process and subsequent startup remain fenced. Recovery from such a filesystem obstruction needs operator correction of the path; generic retry/clearance is not guaranteed to repair a directory. A dangling symlink blocks via `lexists` and is removed as a link, without reading a target.

The 72 intent-bearing clearance injections preserve p's discard. Clearance makes its new journal and matching anchor durable before removing the intent; failure after the final unlink can leave a healthy new pair on restart, or a surviving marker can block startup. Both are authorization-safe. A failed final delete does not bring old decisions back. Retried reset correctly handles whatever new/current pair remains after earlier failure; archive files remain evidence, not startup authority.

The six successful reset input states and seven argument/late-call refusal guards pass. [Exact restore timeline](../experiments/20261008-astra-7727/exact-restore-final7718.json) freezes held observations before reissue; archive bytes, durable actor/reason reset record and operator WARNING are verified. No reconstruction of the live `journal_resets` list after restart is promised.

## 4. Retained integrity checks and accepted limitations

All 16 primary / eight focused journal groups pass. The retained sweeps cover **1,440 supersession schedules / 15,840 event-prefix checks** and **144 hold/rebind schedules / 1,152 checks**. Prior 7638–7718 content/order, refusal, pending/commit failures, abrupt rebind boundaries, startup identity adoption, legacy marker startup, unreadable files, stray artifacts and valid-prefix cases still apply and pass. Historical `recovery7708.restore_guidance` intentionally preserves the obsolete clearance-only restore witness; its old OPEN label is not a finding against the new successful reset sequence.

The policy accurately documents these accepted limits, none of which causes this verdict:

- SHA-256 chains are unkeyed, not a MAC; a hostile writer can recompute them.
- Joint journal/`.id` rollback without successful pre-replay reset is undetectable and can revive discarded decisions.
- Clean suffix removal at a complete-record boundary with matching identity is accepted on restart; it only removes surviving authorizations. Live whole-file checks can detect the changed bytes.
- Both files absent cannot be distinguished from first use; storage lifecycle discipline is external.
- Snapshot/partial/synthetic replay is unsupported; use the full original ordered stream.
- Verification is synchronous and linear in journal bytes; performance and concurrent-writer semantics were not requalified.

Injected before/after-call exceptions and a narrowly specified persistence model do not prove firmware behavior or enumerate every filesystem reordering. No hardware power-cut campaign or service-level restore latch was tested.

## 5. Suite, execution accounting and publication integrity

Full suite executed **exactly once** on the pinned source: **817 passed in 51.57 s**, exit 0. Source verification checks all **157 tracked non-experiment files** against both initial export hashes and Git blobs and confirms the repository's existing source is unchanged. Prior manifest verification retains **315 / 351 / 355 / 829 / 1,189 / 2,221** artifacts for rounds 7669/7678/7694/7701/7708/7718.

Nonzero runs are preserved. `semantic-7133` repeats the same three obsolete automatic-closure expectations; both 3,072-case current/prior sweeps, 384 legacy cases and lifecycle controls pass. Initial supplemental `intent7727` had two harness defects: its disk-inspection helper attempted to read the deliberately mode-000 marker, and the syscall-wrapper factory omitted `return call`. No production failure is inferred from those harness errors. Original source, JSON and logs remain; `intent_final7727.py` fixes only those helpers, uses distinct fixtures, and all four supplemental groups pass. Its correction diff is retained. The failed unreadable fixture was made readable afterwards solely for evidence hashing; final mode-000 behavior was independently rerun successfully. No suite rerun or raw-log overwrite.

Every substantive run has exclusive started/exit JSON and stdout/stderr. Exact commands, environment allowlist, offline wheel hashes, copied-script provenance, adaptation diffs, target patch and changed-file snapshots are included. Python sockets are guarded and package installation uses existing local wheels; this is not an OS network sandbox. No secret/token/environment dump is retained.

Only this report and `experiments/20261008-astra-7727/` were written in the repository. `SHA256SUMS` covers every delivered regular evidence file and this report except itself; the read-only `verify_evidence.py` passes. Nothing is staged, committed or pushed by this reviewer; parent verification, secret scan and publication remain separate.
