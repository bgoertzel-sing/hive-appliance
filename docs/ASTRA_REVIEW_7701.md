# Astra independent re-review 7701 — 865fd63

**Reviewer:** `openai/gpt-6-astra`, sole independent reviewer; no delegation or fallback. Own-session `sessions_list` and assistant `sessions_history` identify model `gpt-6-astra`, provider `openai`, API `openai-responses`. Session: `agent:main:subagent:f4330ac2-ada4-43a1-983e-1682d71d5cd1`. Start and near-completion checks: [model verification](../experiments/20261008-astra-7701/model-verification.json). **Date:** 2026-10-08 (America/Vancouver). **Reviewed pin:** `865fd633bc53561aea140dc3f43fee72b8fd61ee`, parent `5535545368e1577a5eaed0b681b9cb6334915fff`. Re-fetches found origin/main unchanged. Complete eight-file diff, implementation, changed tests, policy and interacting production paths inspected. Repository-operations and experiment-ledger procedures applied.

**Evidence:** [index](../experiments/20261008-astra-7701/README.md), [exact/adapted journal witnesses](../experiments/20261008-astra-7701/followup7694.json), [new focused witnesses](../experiments/20261008-astra-7701/focused7701.json), [sole full suite](../experiments/20261008-astra-7701/pytest.stdout). Artifact names below refer to that directory. Clean detached `/tmp/hive-astra-7701-source`; **151 tracked non-experiment files** remained byte-identical to initial hashes and pinned Git blobs. No production/test changes, old-evidence changes, scratch changes, paid/remote compute or deployment. No reviewer continuation/interruption occurred. Harness adaptation retries are accounted for below.

## Verdict and gate

**Production ownerless hold/rebind gate: NOT APPROVED.** The three OPEN 7694 findings are CLOSED for their exact scopes. Two new Medium startup defects block this gate: header-only missing-anchor adoption explicitly violates the requested crash-fencing contract, and creation/adoption skips an existing legacy fence, allowing a durable APPLIED result whose authorization is blocked on two ordinary restarts. A Low documentation gap remains around joint journal/anchor rollback. The explicitly-owned-plan gate is not broadened.

| Item | Verdict | Result |
|---|---|---|
| F-applied-without-durable-commit | **CLOSED — prior Medium** | Exact zero-byte commit-write plus failed truncate returns falsy `uncertain`, applied=True, durable=None; live applied, two restarts held. |
| F-journal-rollback-anchor | **CLOSED — prior Medium, single-file restore scope** | Current anchor rejects prior valid journal and clean archived prefix after clearance; full damaged archive and splices also fence. |
| F-runtime-integrity-overclaim | **CLOSED — prior Low** | Same-size one-character earlier-record edit is caught before next rebind; on-demand verification also catches it without writes. |
| F-startup-identity-adoption | **OPEN — Medium, requested crash-fencing contract** | Crash after journal creation but before anchor write is silently adopted healthy at restart; new durable rebind allowed without clearance. No stale authorization is demonstrated in this header-only case. |
| F-legacy-marker-startup-bypass | **OPEN — Medium** | New/empty-journal creation and header-only adoption return before legacy-marker check; existing `.fence` is ignored live, then fences both restarts. |
| F-joint-rollback-doc-scope | **OPEN — Low** | Restoring both old journal and old anchor revives discarded authorization. Policy recommends paired restore without explicitly warning that freshness/clearance rollback is undetectable. |
| F-abort-tail / F-journal-refused-compound / F-abort-order-scope | **CLOSED — retained Medium scopes** | Exact archived witnesses migration-fence; native v5 tails/order/edit cases and 24 pending/commit fault modes retain fail-closed invariants. |
| Clearance durability / legacy v1-v4 migration | **CLOSED for tested boundaries** | 64 clearance fault/crash injections plus success; fresh-ID mismatch fences in transition; only applied p survives healthy restart, refused q never does. |
| Aggregate/default, foreign isolation, unregister, journal-order/content, hold/preview | **CLOSED — retained High/Medium/Low findings** | Applicable retained controls pass after explicit structured-result harness adaptations. |
| Near-cap whole-file verification | **Measured cost, not a demonstrated new safety blocker** | At about 63 MiB: median verify 81 ms; two-record rebind 165–179 ms on this warm-cache host. Linear per write, no latency SLA established. |
| Snapshot/partial-replay recovery | **Unsupported; not approved as recovery capability** | Full original ordered event stream remains required; suffix/synthetic-hydrate controls fail closed. |
| Authored suite / execution gates | **CLOSED as execution, not safety proof** | **795 passed**, full suite exactly once; all applicable retained groups completed. Defect-asserting probes are not approvals. |

## 1. RebindResult, live/restart agreement and callers

### F-applied-without-durable-commit — CLOSED Medium

The adapted exact `followup7694.commit_absent` witness keeps the original event stream, successful pending write/fsync, commit write that raises **before any byte**, failed rollback truncate and two ordinary restarts. The only protocol adaptation is the v5 header and structured result assertions; complete adaptation is in `adaptation-7701.diff`.

Observed result:

```text
status="uncertain", bool=False, applied=True, durable=None, op_id present
live: p owned by i, incident i closed; commit_uncertain fence
disk: journal_header + rebind_pending, NO commit
restart 1 and 2: p held, i open, healthy; no commit disposition visible
```

That is the explicit uncertainty contract requested by 7694, not a durable-success acknowledgment. The 24 native fault modes retain separate `refused` versus `uncertain` assertions. A falsy result is **not necessarily refusal**: callers needing that distinction must inspect status. Durable normal success, clean refusal, uncertain memory application and volatile truthy success with durable=False are separately checked. Equality to the literal boolean True is no longer the old API; retained harnesses had to use bool(result).

**All callers:** tracked grep including tests/docs is archived in `production-wiring-search.json`. No production consumer was found that calls the hive rebind and treats a non-exception or truthy uncertain result as durable success. `HiveAppliance` exposes its reducer and journal-health summary, not a rebind wrapper. `controller/reducer.py` has a separate local boolean-returning rebind implementation; it does not call the hive method or consume RebindResult. Its local snapshot behavior is independently covered by retained schedules; do not infer synchronous hive-journal durability from that local API.

**Observability:** `observability7701.json` shows explicit uncertainty in the returned result, `last_rebind_result`, and journal fence (commit_uncertain, applied=True, durable=None). Appliance status reports only unhealthy, not the detailed result. The owner_rebinds audit records memory effects/closures but has no status/durable/op_id fields; it is not a durable-success audit. A later refusal overwrites last_rebind_result, while the fence retains uncertainty. These are integration limitations, not evidence that an in-repository caller incorrectly acknowledges durable success.

## 2. Identity, startup and clearance

### F-journal-rollback-anchor — CLOSED Medium for the original witness

`focused7701.archive_restore` first commits p, corrupts the tail, restarts fenced/held, then clears with the explicit decision to discard the authorization. It retains the **current .id anchor** while restoring each original witness: complete damaged archive, clean prefix of that archive, prior valid complete journal, and an internal append splice. Each fences over two restarts, and no discarded authorization revives; no hashes are recomputed. The valid old copies fail identity matching, not merely an easier syntax check.

### F-startup-identity-adoption — OPEN Medium

`focused7701.startup_identity` interrupts `_write_anchor` immediately after durable journal creation. The disk contains a genuine hashed header-only journal and no .id. Restart writes the missing anchor, reports healthy, and allows a durable applied rebind without inspection/clearance. `startup7701.json` records all **12 initial creation operations and 48 before/after Crash/OSError injections**.

The policy openly documents this adoption exception and an authored test explicitly requires it. It is therefore **not a hidden documentation discrepancy**; it conflicts with this round's explicit requirement that this crash point fence rather than silently start fresh. No old rebind exists in the header-only witness, so do not exaggerate it into demonstrated stale-authorization replay. To close this gate, fence missing identity even for header-only journals (or obtain an explicit change to the requested recovery contract).

Missing journal with present anchor, empty journal with present anchor, and missing anchor with committed journal all fence. Both files absent are indistinguishable from first use; this is a separate paired-loss/restore limitation.

### F-legacy-marker-startup-bypass — OPEN Medium

`marker7701.json` establishes a stronger concrete regression:

```text
preexisting <journal>.fence; journal/anchor absent, empty, or header-only/no anchor
startup -> healthy, existing marker still present
rebind -> status="applied", durable=True; live incident closes
ordinary restart twice, no intervening disk edit -> legacy_marker fence, held
```

Three variants reproduce this, with a matching header+anchor control correctly fenced. `_open_journal` returns immediately after new creation or missing-anchor header adoption, before the legacy-marker presence check. This contradicts the documented rule that any leftover legacy fence blocks replay/new rebinds until clearance, and produces live/restart disagreement even after a durable-success return. Check legacy fences before **every** successful startup return. The fix must cover both creation and adoption; only changing the missing-anchor rule leaves the fresh-creation bypass.

### Fresh-ID clearance and fsync ordering

`clearance7701.json` uses applied p plus genuinely refused pending-only q. Its successful trace records **16 operations**: archive create/write/file-fsync/directory-fsync; new journal temp create/write/file-fsync/directory-fsync/rename/directory-fsync; anchor temp create/write/file-fsync/directory-fsync/rename/directory-fsync. The two independent replacements are not atomic together. Every before/after operation is interrupted both with abrupt BaseException and OSError: **64 injections**, plus success.

Every failed attempt leaves the running process fenced and no successful clearance audit. Before journal replacement, old bytes remain. Between journal replacement and matching anchor replacement, restart identity-fences everything. After matching anchor installation, healthy restart retains p and excludes q; post-rename failure may already have changed disk bytes, so old-byte preservation is not claimed. Success archives exact old bytes, emits new header then reset audit, changes ID, and re-journals only p. Crash probes use actual syscalls and fresh reducers but **are not physical power-loss tests**; cache-visible after-write bytes do not prove hardware persistence. Creation uses the same file/fsync/rename/directory-fsync discipline for journal and anchor.

## 3. Record integrity, verification and performance

### F-runtime-integrity-overclaim — CLOSED Low

The exact same-length one-character change of an earlier pending reason leaves total size and final record unchanged. Next rebind returns refused and fences, with damaged bytes unchanged. On-demand `verify_journal()` independently catches it. Missing/unreadable/malformed/changed anchor, removed journal and appended suffix controls also fail verification; unchanged files verify successfully. No continuous monitoring is promised: changes are detected at next write, verify call or restart.

Native v5 tail/order/edit cases preserve the header while applying original record-order attacks. Duplicate commit, correctly rehashed second commit, nonexistent pending and mismatched pending retain their specific chain/semantic errors. Every complete prefix of a current two-rebind journal is tested: anchor plus missing/empty journal fences; header-only and other intact prefixes authorize only surviving complete pairs. This is not rollback detection for an earlier copy with the same identity.

**Cost:** each rebind scans the entire file twice (pending and commit), using 1 MiB pread chunks. The valid fixture uses a hash-covered padding field in the header; it does not monkeypatch verification or the cap. Five warm-cache verifies and two real rebinds per size:

| File size (approximately) | Median verify | First / second rebind |
|---|---:|---:|
| Header only | 0.022 ms | 7.5 / 8.0 ms |
| 1 MiB | 1.42 ms | 20.3 / 11.7 ms |
| 16 MiB | 21.0 ms | 51.7 / 44.1 ms |
| 63 MiB | 81.1 ms | 179.4 / 164.6 ms |

Raw per-record timings, exact bytes/hashes, startup costs and construction recipe: `performance7701.json/.py`. At 63 MiB startup took 0.858 s. This is material synchronous latency and O(n) work per record (quadratic cumulative scanning as a journal grows), but no deployment frequency/SLA was supplied, so it is not honestly a demonstrated unacceptable-performance defect. Plan for low-rate trusted-operator use, bounded/rotated journals, and measure deployment storage. Padding benchmarks hashing/I/O, not many-small-record parser overhead or cold-cache latency. Large padding fixtures are excluded; recipes and hashes retained.

## 4. Documentation and recovery limitations

### F-joint-rollback-doc-scope — OPEN Low

Restoring **both** the old valid journal and its old .id after deliberate clearance restores the old authorization healthy without rehashing; `focused7701.archive_restore.joint_rollback` records it. The anchor identifies a journal generation; it is not an external freshness/tip checkpoint. Rolling both files back (or clean suffix truncation within a generation) is not detected.

This is an acceptable architectural limitation **if clearly scoped**, not a demand for another anti-rollback service. Current policy says “back up / restore the two together” and says an older/archived journal mismatch fences, but never explicitly warns that restoring both can undo clearance or revive discarded authorization. Add that warning and distinguish generation matching from freshness. The docs' broad removed-record claim also needs the intact-suffix qualification. Unkeyed SHA-256/not-a-MAC and filesystem-permission threat boundary **are explicitly documented and accepted**.

Authentic v1/v2/v3 and archived v4 bytes all migration-fence, remain unmodified until clearance, archive exactly, and require reissue. README/policy correctly extend legacy fencing through v4. Snapshot-only/partial-event replay still is **not** a supported recovery capability: retained suffix/synthetic-hydrate controls cannot reconstruct stream identity and fail closed. Full ordered original stream availability remains a deployment condition, not a capability supplied by this patch.

## 5. Authored tests and provenance

Ten tests were added in `tests/test_astra7694.py`; existing tests adapt header offsets/counts and structured uncertainty assertions. No test was deleted in this commit. The suite rises from 785 to **795**. Authored coverage tests literal adoption as healthy, missing/changed identity, normal durable success and whole-file edits. It does not catch creation/adoption bypass of an already-present legacy marker. Independent matrices are evidence, not permanent regression tests.

The author reportedly ran 795 tests before a docs-only edit. Available Git history contains one published implementation commit, not an identified pre-doc tested tree. **An empty non-doc diff against that author's tested tree cannot be independently confirmed** without its hash/artifact; `author-test-provenance.json` records this limit. The final committed tree was independently tested here exactly once, so the current reviewed bytes have direct suite evidence without relying on that unverified chronology.

## 6. Execution and regression accounting

**Full suite exactly once: 795 passed in 48.55 s**, exit 0; runner wall **49.0329 s**. Python 3.10.12, pytest 9.1.1; environment and build package versions in `environment.json`. Offline wheel hashes verified; pip used PIP_NO_INDEX. Commands, cwd, stdout/stderr, started JSON, exit JSON and wall times are retained.

| Coverage | Result |
|---|---:|
| Owned supersession schedules | 1,440; 15,840 states |
| Hold/rebind schedules | 144; 1,152 event-prefix checks |
| Current / prior-ordered semantic sweeps | 3,072 / 3,072 each |
| Legacy fail-closed / original witnesses | 384 / 384; 2 / 2 |
| N1–N4/mixed receipt controls | 398 / 398 |
| H2/N9/N10 7173 / N9/N10 7195 | 10 / 10; 7 / 7 groups |
| Primary retained review groups | All 16 completed, with six structured-result adaptation retries |
| Retained focused journal groups | All 8 completed; legacy/default serialization adaptation required |
| New focused groups | 5 / 5, including asserted startup/rollback limitations |
| Pending/commit syscall fault modes / abrupt rebind boundaries | 24 / 8 |
| Native tails/order/edit cases / duplicate semantic cases | 15 plus pending tail / 4 |
| Initial identity creation / clearance injections | 48 / 64, plus successful traces |
| Legacy marker bypass | 3 reproductions + 1 correctly fenced control |
| Genuine 10,000-plan cap and default/foreign/unregister/partial controls | Pass |

**Nonzero executions are preserved, not hidden.** Initial primary harness: 10/16, six failures from obsolete literal-bool equality and whole-object/no-diagnostic-mutation assumptions. Initial focused harness: 7/8, legacy/default literal-bool equality. First retry had a definition-loader KeyError before running groups. Corrected retry completed all six affected primary groups; legacy serialization then hit a duplicate as_dict adaptation error. The final legacy-only run passed. No successfully completed suite or primary group was rerun for these repairs. Final adaptation diff and distinct raw outputs remain available.

The unchanged `semantic_7133.py` exits 1 for its same three obsolete automatic-closure expectations; actual outcomes remain fail-closed. Separate current/prior/legacy sweeps pass. This is not a pytest failure and is not relabeled as a successful execution. Some retained raw journal verdict strings still say “v4” or “returns True” from 7694; **structured returned.status observations and this report supersede those inherited labels** (see interpretation-notes.json). Falsy uncertain is not clean refusal. Defect assertions are passing witness executions, not safety approvals.

## Publication integrity

Only this report and `experiments/20261008-astra-7701/` are published. All **151 tracked non-experiment source files** matched before/after and pinned Git bytes; detached source was clean. Prior complete manifests verified **315 (7669), 351 (7678), 355 (7694)** artifact/report hashes. Complete target diff and all changed files are archived under source/. No source/test/old-evidence/scratch edits are included.

The Python socket guard rejects external connections; this is not an OS-wide network sandbox. No paid/remote compute or deployment occurred. Disposable test/cache directories, third-party wheel binaries and large padding files are excluded, with recipes/hashes retained. Exact staged index bytes are scope-checked and credential-pattern scanned. The complete SHA-256 manifest includes this report; verification is read-only. Raw fixture/patch whitespace is preserved separately from authored whitespace checks. Authorized publication is fast-forward-only to origin/main; fetched remote/local equality is recorded outside the manifest after commit at `/tmp/hive-astra-7701/postpush-verification.json`, avoiding self-reference.
