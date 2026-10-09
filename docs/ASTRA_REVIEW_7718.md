# Astra review 7718 — rebind-journal reset durability and recovery

## Verdict: NOT APPROVED

Reviewed **`0ec1a2dc9b56b8011903180f07f94cd1f3f3d39f`** (Protomega2's 7708 fixes). Origin was fetched at start and again before publication; `origin/main` remained this pin. No extra code beyond the requested target needed review. Sole independent reviewer: **`openai/gpt-6-astra`**, verified through this session's metadata and history at start and near completion; no delegation, substitute model, paid compute or remote execution.

The successful restore procedure now works, and the clean-record-boundary truncation documentation is corrected. However, the new reset command is **not fail closed across all interruption boundaries**. A crash before installation of the new anchor can leave a restored old pair healthy and replayable, even after both archives are durable. A caught write failure can leave old pending authorizations live, including after a clean new journal is already durable. Two new **Medium** findings block the requested storage/recovery production gate. This is not a rejection of the explicitly accepted hash/rollback architecture.

Evidence: [index](../experiments/20261008-astra-7718/README.md), [execution ledger](../experiments/20261008-astra-7718/RUN.md), [reset matrix](../experiments/20261008-astra-7718/reset7718.json), [exact restore](../experiments/20261008-astra-7718/exact-restore-final7718.json). Source ran in clean detached `/tmp/hive-astra-7718-source`. No production/test files or older evidence were edited; `scratch/` was left alone.

## Findings

| Finding | Status / severity | Evidence and scope |
|---|---|---|
| F-joint-rollback-doc-scope (7708) | **CLOSED — Low, successful reset scope** | Healthy restored pair: clearance remains a no-op, but successful pre-replay reset archives both files, discards p, stays held through two restarts; explicitly reissued p survives two further restarts. Interrupted reset is a separate OPEN finding below. |
| F-clean-suffix-doc-overclaim (7708) | **CLOSED — Low** | Policy distinguishes middle/torn changes from clean suffix removal. Retained complete-prefix controls accept exactly surviving commits with matching identity; no authorization is invented. |
| F-reset-interruption-replays-restored-pair | **OPEN — Medium** | 50/80 healthy-pair reset injections restart healthy with discarded p restored. Both archives can already be durable while current identity remains unchanged. Broad crash guarantee in policy/docstring is false. |
| F-reset-error-live-pending | **OPEN — Medium** | 40/40 healthy-pair OSError injections leave p pending in a healthy live reducer; replay applies it. After new journal installation, `verify_journal(); clear_journal_fence()` can re-journal the stale pending p and preserve it across restarts. |
| Reset guard / successful archives / identity order / audit | **CLOSED — tested requirements** | Seven invalid/late calls leave all matching disk files and reducer state unchanged. Six successful input states; exact byte archives; anchor-first order; actor/reason durable reset record, status audit and WARNING log. Failure visibility remains OPEN above. |
| F-startup-identity-adoption / F-legacy-marker-startup-bypass | **CLOSED — retained Medium** | Missing/mismatched pair and both active legacy markers remain fail closed; 48 creation and 80 clearance injections rerun. |
| F-rebind-result-ambiguity / F-journal-rollback-anchor | **CLOSED — retained Medium scopes** | Uncertain is not a durable acknowledgment; single-file rollback fences. Joint rollback remains an accepted limitation, not a supported restore method. |
| F-runtime-integrity-overclaim | **CLOSED — retained Low, live verification scope** | Whole-file runtime edits detected; restart clean-prefix limitation explicitly documented. |
| F-abort-tail / F-journal-refused-compound / F-abort-order-scope | **CLOSED — retained Medium scopes** | Historical bytes, native malformed/order cases, pending/commit faults and abrupt boundaries retain fail-closed behavior. |
| Aggregate/default, unregister, foreign isolation, stream/content, hold/preview | **CLOSED — retained High/Medium/Low scopes** | 16/16 primary groups; 1,440 supersession and 144 hold/rebind schedules rerun. |
| Snapshot/partial replay | **Unsupported; not approved as recovery capability** | Full ordered original event stream remains required. |
| Full suite / author provenance | **Independent pass; author exact-pin provenance unverified** | **813 passed**, full suite exactly once on the pin. No tracked author execution artifact tying that claim to this SHA was found. |

## 1. Successful reset and end-to-end restore

The exact 7708 history is reconstructed independently: commit p; save journal and anchor; corrupt tail; restart fenced; clear to discard p; verify p remains held; restore both original files. A fresh reducer sees a healthy pair, and `clear_journal_fence()` correctly returns False without sanitizing it.

`reset_journal(actor, reason)` before event replay succeeds: both old current files are preserved byte-for-byte under their `.reset-<ns>` names, a different random identity is installed before the new journal, and only header + `journal_reset` remain. Full original Event objects are replayed, p remains held on that process and two subsequent restarts, and a deliberately reissued p survives two more restarts. The supplemental exact timeline freezes observations before the reissue so later mutation cannot mislabel an earlier state.

Additional successful fixtures cover a matching healthy restored pair, both legacy marker files, corrupt journal, v3 legacy journal without anchor, missing anchor, and missing journal with anchor. Reset clears applicable legacy markers only after the new pair is installed. Archives contain exactly the previous existing current files. Calls after one event and after full replay, blank/non-string actor/reason, and no configured journal are refused before file changes; all matching files, not merely the two current files, are compared.

Successful reset is operator-visible: returned audit is a deep copy, `journal_status()["journal_resets"]` records the live reset, WARNING logs identify actor/reason, and the durable `journal_reset` contains actor/reason, archive reference and `forced_fresh=True`. In-memory reset lists are not reconstructed on restart; the durable record remains available in the journal. No persistent status-list guarantee is inferred.

The policy's normal sequence—stop service, restore both files, construct reducer, reset **before** replay, replay the full original stream, reissue only reviewed decisions—is now correct **when reset completes successfully**. It does not implement a service-level restore latch, and the failure/crash sentence contradicts the actual transition states below.

## 2. F-reset-interruption-replays-restored-pair — OPEN Medium

Locations: `hive/reducer.py:950`, `:967`, `:989`; policy rollback paragraph, particularly its final crash assertion.

Reset first writes two archive files and only then replaces the current anchor. No persistent reset-in-progress record or startup check distinguishes the original restored pair from the same pair left behind during a failed reset.

Concrete witness: `reset7718.json → interruptions.cases[name="healthy-7-after-Crash"]`.

1. The original authorization was already discarded by an earlier fence clearance, then both old backup files were restored.
2. A new reducer starts before event replay and calls reset.
3. Both archive files have been written and fsync'd, with their directory fsyncs completed.
4. Inject abrupt BaseException **after operation 7**, the second archive's directory fsync.
5. On each of two ordinary restarts, the current old pair is still self-consistent, `healthy=True`, and full original replay restores p.

The same outcome occurs through the temporary-new-anchor creation/write/fsync interval until the anchor rename. This is not merely an exception before the first mutation: the cited witness has completed durable archival work. The policy's “crash part-way ... leaves the old journal under a new anchor” describes only one middle interval, not every partial reset.

Healthy-pair trace: **20 mutating/durability operations × before/after × Crash/OSError = 80 injections**. Results: 50 healthy-old-replay, 24 identity-fenced, 6 healthy-new-held. With both active legacy markers: **24 operations / 96 injections**, 90 fenced and 6 healthy-new-held; no old replay, because markers independently fence startup until removed. Total: **176 injections**, 50 old replay, 114 fenced, 12 healthy held. No tested mismatched/unverified pair was silently accepted; the defect is acceptance of the old verified pair despite interrupted discard intent.

**Required correction:** establish a durable, startup-enforced reset/restore intent before the archival/replacement transition, or an equivalent fail-closed restore transaction. Keep it enforced until the new pair is durably complete. Document the pre-intent/no-mutation boundary honestly: no implementation can infer an invocation that left no durable evidence. If intent establishment fails, the service must remain stopped and the recovery procedure must require retry/explicit successful reset before any replay. Do not assert arbitrary partial resets always create an identity mismatch.

## 3. F-reset-error-live-pending — OPEN Medium

Locations: `hive/reducer.py:989–999`, `:1025` (`_replay_journal`), `:905` (clearance carries pending entries).

Reset does not fence or invalidate cached pending authorizations on failure. Clearing `_journal_pending` and updating verified state occur only after all storage and marker operations. In the healthy-pair matrix **all 40 OSError cases** leave the live reducer reporting healthy with one pending p; feeding the original stream applies it. No successful reset audit appears.

The sharper independent witness is `reset7718.json → live_failure`: let `_replace_durably(path, new_data)` finish, including directory fsync, then raise OSError before reset's in-memory commit. Fresh disk restart is healthy and held; the still-live reducer reports healthy and retains p. Two supported follow-ups demonstrate the consequences:

- Feed original events: old p applies only in memory, while independent restarts remain held. Live and durable recovery disagree.
- Call `verify_journal()`: it notices changed bytes and fences. Then call `clear_journal_fence()` on this same pre-event reducer: clearance deliberately preserves cached pending p, writes a new committed pair for it, and p now survives **two restarts**.

Thus the ordinary “verify then clear” repair path can undo a partially successful reset and make discarded authorization durable again. Unlike the early crash case, this is not an old pair surviving unchanged: the fresh journal already exists and held state is recoverable from disk.

**Required correction:** a failed reset must leave an explicit unusable/fenced live state that cannot replay or re-journal pre-reset pending decisions. Simply setting a fence is insufficient: `_replay_journal` does not gate on the fence and clearance preserves pending entries. Safely invalidate/quarantine the reset's pending authorization set, forbid subsequent replay/clearance until correct recovery, or require disposal of the failed reducer through an enforced API state. Retrying reset on a still-pre-event reducer or reconstructing under a durable restore gate can be recovery paths, but merely documenting “catch and clear” would be unsafe. Expose the failed/in-progress state to operators.

These two findings concern reset recovery, not normal committed-rebind writes or successful reset. Their severities are Medium because storage/process failure during the prescribed restore can revive deliberately discarded authorization and close an incident.

## 4. Retained integrity checks and accepted limitations

All eight focused journal groups now pass with the precise MIGRATION diagnostic adaptation made **before** execution; its diff is retained. The 16 primary groups retain original content/order witnesses, default journal refusal, foreign isolation, real 10,000-plan admission, hold/rebind and snapshot/partial-replay controls. The 48 corrected first-use injections use the same Event objects across restart comparisons; all 24 fenced states are explicitly recoverable. Clearance retains its 80-boundary matrix including both legacy markers. Unreadable journal/anchor controls include actual mode-000 files under the non-root uid and EACCES/EIO; temporary/cleared-artifact and v1–v4/op controls pass.

The unchanged `recovery7708.restore_guidance` witness intentionally reproduces the **old** clearance-only procedure. Its historical “OPEN” string is not a finding against the revised success path; the new reset timeline is authoritative for that question.

Accepted architectural limits remain:

- SHA-256 is unkeyed, not a MAC; hostile writers can recompute a chain.
- Joint rollback of journal and `.id` without a successful reset is undetectable and may revive discarded decisions.
- Clean suffix truncation at a complete record boundary within one identity is accepted on restart and can only remove surviving authorization. The live remembered whole-file check can detect the changed bytes.
- Both files absent is indistinguishable from first use; external storage lifecycle discipline is required.
- Snapshot/partial/synthetic replay does not reconstruct journal authorization; only the full original ordered stream is supported.
- Whole-file verification remains synchronous and linear in journal bytes. No performance remeasurement or broader deployment audit was attempted.

The failure matrices inject syscall-visible exceptions before/after mutations and fsync, not hardware power loss. They do not prove firmware persistence, enumerate every filesystem reordering, or test concurrent writers.

## 5. Suite, provenance and execution accounting

Target adds five authored reset tests; suite grows 808 → **813**. Full suite executed **exactly once**, result **813 passed in 52.16 s**, runner wall **52.6947 s**, exit 0. The author claims the same count, but tracked docs/experiments at the pin contain no full-suite execution artifact tied to this SHA. Author provenance is **UNVERIFIED**, not disproved; the independently pinned run is direct evidence.

| Coverage | Result |
|---|---:|
| Supersession schedules / event-prefix checks | 1,440 / 15,840 |
| Hold/rebind schedules / event-prefix checks | 144 / 1,152 |
| Primary / focused retained journal groups | 16/16 / 8/8 |
| Identity/runtime/rollback/prefix/legacy groups | 5/5 |
| Rebind pending/commit fault modes / abrupt boundaries | 24 / 8 |
| First-use / clearance / reset injections | 48 / 80 / 176 |
| First-use fenced-state explicit recovery | 24/24 |
| Active-marker startup variants | 8 |
| Stray artifacts / legacy-version-op / unreadable cases | 12 / 12 / 6 |
| Successful reset input states / refusal guards | 6 / 7 |
| Exact restored discarded p / reissued p | Held for two restarts / durable for two restarts |

**Nonzero runs are preserved, not hidden.** Historical `semantic-7133` exits 1 for the same three obsolete automatic-closure expectations; its current/prior 3,072-case sweeps, 384 legacy sweep and lifecycle controls pass. Initial supplemental `exact-restore7718` exits 1 at log capture because imported historical harnesses set the root threshold to CRITICAL; storage/restart assertions before it passed. A targeted retry explicitly enables WARNING on the reducer logger and uses a distinct fixture; diff and both executions are retained. This is not a second suite run.

Raw `reset7718.successful_restore` serializes its second held reducer after subsequently reissuing p on that object; assertions check held beforehand, but the output list alone can be misleading. The supplemental final timeline freezes the two pre-reissue observations. No raw result was overwritten or retroactively labeled a pass.

## Publication integrity

All **155 tracked non-experiment files** in the detached source match initial hashes and pinned Git blobs; source is clean. Prior manifests for 7669/7678/7694/7701/7708 verify **315/351/355/829/1,189** files respectively. Exact target diff and changed source snapshots are retained. Only this report and `experiments/20261008-astra-7718/` are staged and committed; no production/test/old-evidence/scratch edits.

Started/exit JSON and stdout/stderr accompany each substantive execution. Python sockets are guarded and package installation uses local hashed wheels with PIP_NO_INDEX; this is not an OS network sandbox. Disposable pytest/tmp/cache directories and wheel binaries are excluded. SHA256SUMS covers report and every delivered evidence file except itself; staged index bytes are scope-checked and scanned for high-confidence credential patterns. Publication is authorized fast-forward-only to origin/main, with post-push local/remote equality verified separately at `/tmp/hive-astra-7718/postpush-verification.json` to avoid self-reference.
