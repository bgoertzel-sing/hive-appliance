# Astra independent re-review 7708 — 8945bdc

**Reviewer:** `openai/gpt-6-astra`, sole independent reviewer; no delegation or fallback. Own-session `sessions_list` and assistant `sessions_history` identify model `gpt-6-astra`, provider `openai`, API `openai-responses`. Session: `agent:main:subagent:a24f66ce-f5bc-41a4-ae99-568384ca947f`. Start and near-completion checks: [model verification](../experiments/20261008-astra-7708/model-verification.json). **Date:** 2026-10-08 (America/Vancouver). **Reviewed pin:** `8945bdcb06415a11a5647fbb0e4decc59e021784`, parent `1a87ae9bcdbb8140ff853f32291e17c9582e09d7`; preceding code-change commit `865fd633bc53561aea140dc3f43fee72b8fd61ee`. Re-fetch confirmed origin/main unchanged. Entire six-file target diff, implementation, changed tests, recovery policy and inherited journal witnesses inspected. GitHub workflow applied for authorized publication.

**Evidence:** [index](../experiments/20261008-astra-7708/README.md), [retained journal witnesses](../experiments/20261008-astra-7708/followup7694.json), [new recovery probes](../experiments/20261008-astra-7708/recovery7708.json), [sole full suite](../experiments/20261008-astra-7708/pytest.stdout). Artifact names below refer to that directory. Execution used clean detached `/tmp/hive-astra-7708-source`. No code/test edits, edits to older evidence, scratch changes, delegation, paid/remote compute or deployment. Source verification includes pinned Git-blob comparison. Harness failures and corrections are preserved below; no reviewer/provider interruption occurred.

## Verdict and gate

**Production ownerless hold/rebind recovery gate: NOT APPROVED.** Both prior Medium startup findings are CLOSED. The joint-rollback warning is corrected, but the requested safe restore guidance remains incorrect: calling `clear_journal_fence()` on the healthy restored pair does nothing. A second Low documentation issue still overclaims detection of removed records/edits at restart. No new implementation safety failure was demonstrated in the covered creation, clearance or rebind interruption boundaries. The explicitly-owned-plan gate is not broadened.

| Item | Verdict | Result |
|---|---|---|
| F-startup-identity-adoption | **CLOSED — prior Medium** | Header-only/missing-anchor journals fence without adoption; anchor-only interrupted first use fences and can be explicitly cleared. |
| F-legacy-marker-startup-bypass | **CLOSED — prior Medium** | `.fence` and `.fence.tmp` fence before creation in eight retained variants; bytes unchanged through two restarts. v1–v4 controls also fence before identity creation. |
| F-joint-rollback-doc-scope | **OPEN — Low** | Undetected paired rollback is now stated explicitly, but the recommended `clear_journal_fence()` restore path is a no-op on a healthy pair; discarded authorization returns. |
| F-clean-suffix-doc-overclaim | **OPEN — Low** | Clean complete-prefix rollback within the same identity is accepted at restart; docs still say a removed record breaks the chain and a truncated/edited journal is caught at restart without this qualification. |
| F-applied-without-durable-commit | **CLOSED — retained Medium** | Exact missing-commit/failed-truncate result remains falsy uncertain, applied=True, durable=None, not durable success. |
| F-journal-rollback-anchor | **CLOSED — retained Medium, single-file generation mismatch scope** | Old valid journal/archived prefix with current anchor fences; joint rollback is a separate accepted architectural limitation. |
| F-runtime-integrity-overclaim | **CLOSED — retained Low, live whole-file verification scope** | Same-length earlier edit detected by next rebind and on-demand verification. Restart clean-prefix limitation is separately OPEN above. |
| F-abort-tail / F-journal-refused-compound / F-abort-order-scope | **CLOSED — retained Medium scopes** | Archived and native journal regressions, pending/commit faults and abrupt boundaries preserve fail-closed semantics. |
| Creation / clearance interruptions | **CLOSED for tested boundaries** | Corrected creation matrix 48 injections; clearance 80 injections including both marker renames. No silently accepted mismatched identity or refused q replay. |
| Aggregate/default, foreign isolation, unregister, order/content, hold/preview | **CLOSED — retained High/Medium/Low scopes** | All 16 retained primary groups pass; 1,440 supersession and 144 hold/rebind schedules rerun. |
| Snapshot/partial-replay recovery | **Unsupported; not approved as recovery capability** | Full original ordered event stream remains required; suffix/synthetic-hydrate controls remain fail closed. |
| Authored suite / independent execution | **Author provenance unverified; independent execution complete** | **808 passed**, full suite exactly once on pinned source. No author full-suite artifact tied to exactly this SHA found. |

## 1. RebindResult, live/restart agreement and callers

The target does not alter RebindResult or its callers. `followup7694.applied_no_commit` retains the exact successful pending write/fsync, zero-byte commit write failure and failed truncate witness. It reports uncertain, applied=True, durable=None and falsy. Rebind fault coverage retains 24 pending/commit fault modes and eight abrupt boundaries; clean refusal does not turn into authorization on restart. The `review7694` primary groups retain content/stream identity, canonical encoding, genuine 10,000-plan cap, default/foreign isolation, hold and replay controls. The full suite includes the unchanged caller integration checks.

An uncertain memory application is not a durable acknowledgment and is not the same as refused. Raw inherited descriptive strings saying v4/True are historical labels, not the current protocol: structured status/durable results and this report are authoritative. No broader production caller audit or performance remeasurement is claimed in this storage-focused round; the unchanged 7701 caveats remain applicable.

## 2. Identity, startup and clearance

### F-startup-identity-adoption — CLOSED Medium

`focused7701.startup_identity` (explicit 7708 adaptation) checks missing journal with anchor, missing anchor with committed or header-only journal, empty journal with anchor, both absent and header/no-anchor with legacy marker. All but genuinely absent pair fence, refuse rebind and remain fenced across two restarts; explicit clearance produces a healthy held journal. The original 865fd63 header-only crash disk state is therefore no longer adopted. The authored tests also construct that exact old-order state.

`startup7708.json` records 12 real mutating/durability operations, with abrupt BaseException and OSError injected before and after each: **48 injections**. Identity temp create/write/file-fsync/directory-fsync/rename/directory-fsync precedes equivalent header operations. There is no userspace buffered flush call: implementation uses `os.write` and fsync. Directory-open calls are not mutations; their fsync calls are instrumented.

24 cases restart healthy: either neither final file existed so a genuinely fresh pair is created, or a complete matching pair already exists. 24 restart identity-fenced (anchor installed, journal absent). Corrected harness uses the **same original Event objects on both restarts**, and verifies durable rebind replay for healthy cases. `startup-recovery7708.json` additionally clears, reissues and restarts every one of the 24 fenced cases. This is operator-required recovery, **not a permanent brick and not silent adoption**. Uncommitted `.new-*` residues do not authorize anything.

### F-legacy-marker-startup-bypass — CLOSED Medium

`marker7701.json` adapts the four original disk states (absent pair, empty journal/no anchor, header/no anchor, matching header+anchor) to both `.fence` and `.fence.tmp`: **eight variants**. All report `legacy`, refuse rebind, leave all matching disk bytes/files unchanged, and fence both ordinary restarts. `recovery7708.legacy_versions` adds 12 v1–v4/op combinations over two restarts; no identity is created. Authentic historical bytes remain covered by retained regressions and legacy clearance witnesses. Diagnostic kind changed from `legacy_marker` to `legacy`, with explicit MIGRATION guidance; diffs show the adaptation.

### Fresh-ID clearance and fsync ordering

`clearance7701.json` uses durably applied p and genuinely refused pending-only q, then installs **both legacy marker files** before clearing. Trace: four archive operations; six new-journal operations; six new-anchor operations; each marker rename and directory fsync. **20 operations × before/after × Crash/OSError = 80 injections**, plus success. Archive bytes are preserved; success re-journals only applied p, not q, and moves both markers aside. Each failure leaves the interrupted live reducer fenced and no successful clearance audit. Across two restarts, a healthy result retains p and excludes q; any transition mismatch or residual active marker fences everything. Fenced hold is not silently dropped durable authorization: the operator must inspect the preserved archive, not blindly discard it.

Creation is anchor-first; clearance still installs the new journal before its new anchor. That non-atomic pair replacement safely fences in the gap. Once both replacements and marker transitions are complete, an after-operation exception may leave healthy durable disk state despite the interrupted process being fenced. We do not claim all failures preserve original current-file bytes.

These are syscall/process-interruption simulations, **not hardware power-loss tests**. Cache-visible bytes after a successful syscall do not prove storage firmware persistence. No crash-tree enumeration of every possible filesystem power-loss reorder is claimed.

## 3. Record integrity, verification and performance

Retained whole-file edit/verify controls, native tail/order/duplicate semantics, legacy witnesses and complete-prefix replay controls pass. `recovery7708.unreadable` tests actual mode-000 journal/anchor files under the non-root uid and injected EACCES/EIO on each file across two starts. All refuse replay/rebind. Unreadable journal clearance raises; an unreadable anchor can be replaced by explicit clearance when the journal is readable, discarding unverified replay as intended.

`recovery7708.leftover_artifacts` tests `.tmp`, `.id.tmp`, journal/anchor `.new-*`, `.fence.cleared-*` and `.fence.tmp.cleared-*` in first-use and committed-pair states (12 cases). They remain untouched and are not treated as active authorization/markers. This does not contradict `.fence.tmp` being active legacy evidence. Current matching files, not stray temporaries or old cleared markers, determine replay.

No performance change was made or independently rebenchmarked here. Whole-file verification remains synchronous and linear in journal bytes; 7701's warm-cache measurements remain historical, not measurements of this execution.

## 4. Documentation and recovery limitations

### F-joint-rollback-doc-scope — OPEN Low (warning corrected; safe procedure not corrected)

Policy lines 113–125 explicitly explain joint rollback and revival of discarded authorization. That warning closes the omission portion of the old finding. However the prescribed fallback says restore both and, before serving, call `clear_journal_fence()` (or start a fresh journal), then reissue only wanted rebinds.

`recovery7708.restore_guidance` performs the literal path:

```text
commit p; save journal + .id
corrupt tail; restart fenced; explicitly clear to discard p
restore both original files
construct reducer BEFORE event replay/serving
clear_journal_fence(actor, reason) -> False; no fence, no change
feed original events -> p authorized, i closed; next restart repeats
```

`hive/reducer.py:877` returns False if there is no fence. The restored self-consistent pair is healthy, so the recommended method cannot sanitize it. This is not a new cryptographic failure or a demand for external anti-rollback infrastructure; it is an unsafe recovery instruction despite accurate threat-boundary prose. **Fix:** remove the healthy-pair clearance recommendation. Recommend stopping service, preserving originals for inspection, selecting a genuinely fresh journal location/pair before ingesting the full original stream, and explicitly reissuing only reviewed current decisions. Merely forcing a fence after replay is not a safe substitute: clearance preserves applied/pending decisions. The policy's fresh-journal alternative can be safe; its no-op alternative cannot.

### F-clean-suffix-doc-overclaim — OPEN Low

Policy lines 126–132 say removed records break the chain; lines 171–178 include restart among detection points for edits/truncation. A complete prefix within the same journal identity is self-consistent. `focused7701.clean_prefixes` keeps the matching anchor and tests every complete prefix of two applied rebinds: zero bytes fences; header-only, pending-only, first committed pair, second pending and full journal accept exactly their surviving complete commits. No hashes are recomputed. Thus a clean suffix deletion can remove authorization while startup reports healthy, and a same-generation older pair is not detected. This is an accepted design limitation only when documented precisely. Qualify record-removal/restart claims to distinguish interior deletion/torn lines from complete-suffix rollback, and distinguish live remembered whole-file checks from restart verification.

### Migration and accepted limitations

The identity section explicitly says even header-only/missing-anchor journals fence; legacy-artifact section explicitly names `.fence.tmp`. Together with upgrade text, migration coverage accurately describes the 865fd63 header-only residue and formerly ignored temporary legacy marker. An explicit old-version example in the upgrade paragraph would help, but is not another finding.

Unkeyed SHA-256/not-a-MAC, write-permission threat boundary, joint rollback, both-files-absent indistinguishability and full ordered-original-event replay requirements are accepted architectural limits, not promises of tamper-proof storage or snapshot recovery. Partial/synthetic replay still fails closed. Joint rollback and intact-suffix rollback are not approved as recovery capabilities; safe operational guidance must match these limits.

## 5. Authored tests and provenance

The six-file change adds `tests/test_astra7701.py` (13 collected cases), updates the prior header-adoption and temporary-marker tests to require fencing, and updates two marker-kind assertions. Expected suite grows 795 → **808**. New tests include interruption between anchor/journal, old header-only state, empty journal, six marker startup variants, legacy records and legacy-after-v5 prefix.

`author-test-provenance.json` records commit metadata and a tracked docs/evidence search. No author full-suite execution log tied to exactly `8945bdc` was found; the commit message's “tests” is not execution provenance. **Author execution on the exact pin remains UNVERIFIED**, not disproved. The independent full suite below tests the exact pin directly. No remote CI/paid compute was invoked.

## 6. Execution and regression accounting

**Full suite exactly once: 808 passed in 49.96 s**, exit 0; runner wall **50.5087 s**. Python/package/platform details in `environment.json`; offline socket guard, wheel hashes and PIP_NO_INDEX recorded. Every substantive execution has stdout/stderr and started/exit JSON with command, cwd and elapsed time.

| Coverage | Result |
|---|---:|
| Owned supersession / hold-rebind schedules | 1,440 / 144; 15,840 / 1,152 event-prefix checks |
| Primary retained review groups | 16/16 |
| Focused retained journal groups | Initial 7/8; remaining legacy/default group passes after diagnostic-only retry |
| Focused identity/runtime/rollback/prefix/legacy4 groups | 5/5 |
| Pending/commit fault modes / abrupt rebind boundaries | 24 / 8 |
| Corrected initial creation / clearance injections | 48 / 80, plus successful traces |
| Interrupted first-use explicit recovery | 24/24 fenced states cleared, reissued, restarted |
| Legacy-marker startup / extra version-op cases | 8 / 12, two restarts each |
| Stray temporary/cleared-marker cases / unreadable modes | 12 / 6 |
| New restore-guidance witness | Defect reproduced, not approval |
| Other retained 7173/7195, boundary/disk, mechanism, probes, older, independent, new cases | Exit 0 |

**Nonzero executions preserved:** `followup7694` initially fails only `legacy_default` because it expects old “legacy or unknown” wording; `retry_legacy7708.py` substitutes the precise new `legacy` + MIGRATION diagnostic in memory and reruns only that group. The initial creation harness inherited from 7701 generates new event timestamps separately for each restart; its raw result correctly refuses mismatched-stream replay but cannot establish same-stream durable replay. Supplemental `startup-recovery7708` catches that issue (exit 1). `startup7708.py` preserves one stream per case, uses fresh fixture names and reruns the entire affected creation matrix; the final recovery validator passes. Both initial matrix and failure remain archived with explicit adaptation diff. No suite rerun occurred.

Unchanged `semantic_7133.py` exits 1 for the same three obsolete automatic-closure expectations; separate current/prior/legacy sweeps and current policy schedules pass. This historical execution is not relabeled successful or confused with pytest. Raw legacy labels retained in copied harnesses do not override actual structured observations.

## Publication integrity

Only this report and `experiments/20261008-astra-7708/` are published. All tracked non-experiment files match their initial hashes and pinned Git blobs, and the detached source is clean. Prior complete manifests for 7669, 7678, 7694 and 7701 verified; counts are in `prior-evidence-verification.json`. Target diff and all changed files are archived under source/. No production/test/old-evidence/scratch changes are staged.

The Python socket guard is not an OS-wide network sandbox; authorized git fetch/push are publication operations, not remote execution. Disposable pytest/tmp/cache directories and third-party wheels are excluded; wheel recipes/hashes are retained. Harnesses, distinct execution outputs, failure logs and small forensic journal artifacts are included. SHA256SUMS covers the report and every evidence file except itself; `verify_evidence.py` is read-only. Exact staged bytes are scope-checked and credential-pattern scanned. Raw patches/fixtures preserve their original bytes; authored docs receive whitespace checks. Publication is fast-forward-only to origin/main. Post-push local/remote hash verification is recorded outside the manifest at `/tmp/hive-astra-7708/postpush-verification.json` to avoid self-reference.
