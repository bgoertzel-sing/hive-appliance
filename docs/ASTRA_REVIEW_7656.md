# Astra independent re-review 7656 — 647fac6

**Reviewer:** `openai/gpt-6-astra`, sole independent reviewer, no delegation or fallback. Own-session `sessions_list` and assistant `sessions_history` confirm `gpt-6-astra`, provider `openai`, API `openai-responses`; see [model verification](../experiments/20261008-astra-7656/model-verification.json). **Date:** 2026-10-08. **Request:** review round 7656. **Reviewed pin:** `647fac6fd46f950ab00301aba75dc10900baf1e9`, initially equal to main and origin/main; parent `ff692b9`. The complete four-file diff and all four changed files were read, along with reviews 7638/7582, their procedure/evidence, policy and retained decision input. Repository-operations and experiment-ledger skills applied.

**Evidence:** [index](../experiments/20261008-astra-7656/README.md), [independent results](../experiments/20261008-astra-7656/review7656.json), [focused followups and final severity qualification](../experiments/20261008-astra-7656/followup7656.json), [sole full-suite output](../experiments/20261008-astra-7656/pytest.stdout). Artifact names below refer to this new evidence directory. All execution used a clean detached worktree of the pin; 144 tracked non-experiment files remained byte-identical. No production/test-source changes, prior-evidence changes, scratch changes, paid/remote compute or live deployment.

## Verdict and gate

**Production ownerless hold/rebind gate: NOT APPROVED.** The two original High witnesses are repaired, but **F-journal-refused-fsync remains OPEN Medium**: the indeterminate fence exists only in memory, and a fresh reducer automatically applies the operation that the live API refused. This directly violates the requested restart-fencing gate. There is also a Medium content-integrity qualification and Low recovery/operability gaps below. Preserve the previously bounded explicitly-owned-plan gate; this report does not change any operational gate.

| Item | Verdict | Result |
|---|---|---|
| F-unregister-escape | **CLOSED — prior High, exact witness** | Hold/provenance/dedup survive unregister; re-register and same-plan PLAN cannot credit foreign j evidence to k, through both reducer and real appliance registration/tick paths. |
| F-journal-order | **CLOSED — prior High, exact three orders** | Full identical serialized replay applies at the original accepted-event boundary; original-open i stays open. Identity/order mismatches are reported unapplied and remain held. |
| F-journal-refused-fsync | **OPEN — Medium** | Clean rollback now truncates and fsyncs correctly; failed truncation leaves an entry that restart auto-applies despite live refusal/fence. Close-error boundary also returns False for a durable, replayable entry. |
| F-journal-tail | **CLOSED — prior Medium, original witness** | Normal startup/runtime torn-tail quarantine works, including invalid UTF-8; successful subsequent entries survive restart. Short quarantine writes remain a distinct Low issue. |
| F-journal-content | **OPEN — Medium, new robustness gap** | Hash covers event identities/kinds, not payloads. Same IDs with changed failure content accept the old authorization and close original-open i without an unapplied warning. This assumes changed/corrupted content, not identical immutable events. |
| F-tail-aside-short-write | **OPEN — Low, new** | Short write of the torn fragment is treated as success; original fragment is truncated and most forensic bytes are lost. |
| Default durability | **CLOSED — prior Medium for HiveAppliance** | No journal means rebind refusal; explicit volatile opt-out works; environment path works; argument takes precedence. Constructor and ordinary operations still work without a journal. |
| Candidate/journal admission caps | **CLOSED — prior Low, scoped** | Real 255/256/257 candidate-key and 64 MiB journal boundaries work; refusals never drop active holds. |
| Aggregate resource/admission policy | **OPEN — Low, residual** | Complete active holds/plan state remain uncapped by design; journal cap limits new appends, not pre-existing file loading. No measured OOM is claimed. |
| F-unapplied-observability | **OPEN — Low, new** | 201 mismatches produce only 200 status entries with no cumulative/truncation indication; originals remain on disk and errors are logged. |
| Recovery/migration documentation | **OPEN — Low** | Appliance usage updated, but README/policy lack journal default, legacy-v1 migration, full-stream replay and fence recovery guidance. |
| Recovery-text test gap | **CLOSED — prior Low** | Test actually migrates and unconditionally asserts text/holds; empty-text mutation is detected. |
| Prior foreign evidence/hold-expiry/preview/guidance | **CLOSED — retained High/Medium/Low controls** | Exact earlier controls, restores/replays, quiet preview and authoritative recovery text remain passing. |
| Authored suite and retained gates | **CLOSED as execution, not complete safety proof** | **764 passed**, exactly one full-suite run; retained schedule counts below. |

## 1. F-unregister-escape — CLOSED prior High

Exact 7638 stream:

```text
register(a1)
INCIDENT(j, plan_id=p); PLAN(p, owner="")
RECEIPT(j-evidence, p, incident_id=j, step=0, success)
unregister(a1); register(a1)
INCIDENT(k, plan_id=""); PLAN(p, owner=k)
```

Both `HiveReducer` and `HiveAppliance` keep `a1:p` held, owner absent, k open and audit empty. The appliance case uses `StubAgentAdapter`, public register/unregister and `tick()`, not only its reducer. After unregister, the reason is `ownerless_held`; this is explicitly temporary removal, not a fresh plan incarnation.

Preview discards foreign step 0 and predicts no closure. Audited rebind to k still leaves k open; replay of the old j receipt changes nothing; only fresh k evidence closes it. The author's chosen retained-state lifecycle closes the concrete finding. Incidents/health are still removed on unregister; this is not a claim that all agent state is retained.

## 2. F-journal-order — original High witnesses CLOSED

All three exact 7638 sequences use linked incidents i/j, ownerless p, then:

1. target-i success, target-i failure;
2. plan-only success, plan-only failure;
3. target-i success, foreign-j failure.

Each finishes with PLAN(p,i) and an audited rebind. Original execution leaves i and j open. Full JSON-serialized restart replay now preserves that result, owner, progress/failure sets and audit effects, including candidate and foreign-step discard metadata. Only the deliberate `replayed` flag differs. A changed event ID or swapped receipt order at the same boundary gives one unapplied record and leaves p held; no premature rebind occurs.

Normal write-ahead ordering is independently observed: the complete JSONL entry exists at fsync while live owner/audit are still unchanged. Double event replay does not duplicate the audit or append. Duplicate physical journal lines are now retired rather than remaining pending indefinitely. Open-path failure refuses without live mutation.

### Rejected PLAN and snapshot/partial replay limits

A conflicting PLAN does **not** advance `_event_seq`, change `_stream_digest`, timestamps, journal state or semantic state. The existing `rejected_plan_registrations` counter alone increments, exactly the diagnostic exception in 7146's unchanged test. Inserting that rejected PLAN at a different point in a replay does not invalidate the accepted-event boundary. This is compliant, not a reason to count rejected events.

There is **no native `HiveReducer.snapshot()` or `restore_snapshot()` API**. A partial suffix reconstruction cannot replace complete original replay: its journal remains visibly pending until the recorded position is reached, then an identity mismatch is visibly unapplied and p stays held. A clearly labeled synthetic state hydration without position/digest also leaves the operation pending; it is not presented as a supported snapshot API. Local reducer checkpoint controls still pass, but do not restore the hive's global position/hash.

Thus restart recovery requires the original complete ordered accepted-event stream, not merely an agent/local snapshot. `HiveEventBus` has bounded in-memory history; this change supplies no durable globally ordered event archive or checkpoint migration. Do not interpret “journal configured” as a complete autonomous recovery solution.

### F-journal-content — OPEN Medium

At `hive/reducer.py:306`, `_advance_stream` hashes only previous digest, source agent, event ID and event kind. It does not hash payload, timestamp or other serialized content.

Independent witness: preserve every ID/kind/order in the first success-then-failure stream, but change the last receipt's `verified=False` to `True`. The digest is identical. Replay applies the original rebind, resolves i, and reports no mismatch, whereas original execution left i open. Serialized originals and modified input are retained.

**Qualification and severity:** `schemas/types.py` describes Event as immutable, although the dataclass/from_dict do not authenticate that convention. This is a **Medium corruption/identity-reuse assurance gap**, not an ordinary identical-stream ordering counterexample or a demonstrated hostile-store compromise. The initial probe JSON labeled it High; `followup7656.json.content_hash_classification` explicitly supersedes that classification after inspecting the immutable-event contract. Hash canonical relevant content, or explicitly narrow and enforce the trusted immutable-ID assumption; the current “stream differs” guard is not content verification.

## 3. F-journal-refused-fsync — OPEN Medium

At `hive/reducer.py:393`, failed append now attempts `ftruncate(original_size)` **and fsync of the truncation** before reporting a clean refusal. This repairs the normal one-shot fsync failure. Independent tests confirm preservation of a prior committed entry, correct rollback size and the second fsync. An error before write, short write, error after complete write, and one-shot fsync errors before/after the real fsync all roll back safely in the exercised process/restart model.

The indeterminate branch at `hive/reducer.py:558` still fails the requested restart gate:

```text
hold p for i; collect successful i evidence; record candidate i
append complete rebind entry
inject append fsync failure AND ftruncate failure
rebind(...) -> False; live owner absent; live indeterminate fence set
second live rebind -> False
fresh HiveReducer(same journal); replay identical original events
# owner becomes i; i closes; audit says replayed; fence is None
```

`_journal_indeterminate` is initialized to None at every construction. No durable fence/abort marker prevents `_open_journal` from treating the surviving entry as committed. An operator is not required to inspect it before automatic replay. This is observable with ordinary fresh-object restart; it does not rely on hypothetical power loss.

A separate **close-after-durable-write** injected error returns False through the clean-refusal handler with no indeterminate state, although the entry is intact and replayable. The raw descriptor is actually closed before the injected error, so the probe does not leak it. Successful disk commit must not be represented as guaranteed refusal just because a later descriptor close reports an error.

Fault coverage includes nine append/rollback/close cases; the exact old always-failing-fsync witness; prior-entry rollback; and new-file/parent-directory startup fsync errors. New code uses raw `os.write`, so there is **no separate Python flush call** to inject. The write-to-fsync interval and rollback truncation-to-fsync interval were exercised. Failed rollback fsync after a successful truncation leaves an empty file in these process restarts, but physical power-loss durability is not established. Startup fsync failures raise explicitly.

**Required closure:** persist or otherwise reconstruct the indeterminate disposition so restart cannot auto-authorize a refused/uncertain operation; distinguish committed, rolled-back and uncertain results consistently, including post-commit close errors. Live-only fencing is insufficient.

## 4. F-journal-tail and caps

### Original F-journal-tail — CLOSED prior Medium

Startup and runtime append both set aside an unterminated ASCII or invalid-UTF-8 fragment before the new entry. Each actual aside file contains the exact fragment. Subsequent successful rebinds survive fresh serialized replay. Complete invalid UTF-8, malformed JSON and structurally invalid lines are counted/skipped without losing a following valid line. The old constructor UnicodeDecodeError is repaired.

Twelve additional fault cases cover startup/runtime quarantine write, aside fsync, truncate, journal fsync and directory fsync. Those raising errors prevent new entry publication (startup raises, append refuses).

**F-tail-aside-short-write — OPEN Low:** `_set_aside_tail` at line 331 ignores `os.write`'s return count. Writing only 3 bytes of a longer fragment causes the original to be truncated anyway; construction succeeds, or append/rebind returns True, while the aside is incomplete. This loses torn-tail forensic/recovery bytes, not a demonstrated previously committed valid record. Check/write all bytes before truncating the original.

### Candidate and real 64 MiB boundaries

The actual 256-key candidate cap was not reduced for these tests:

| Plans | Candidate keys | Active holds | Dropped-key count |
|---:|---:|---:|---:|
| 255 | 255 | 255 | 0 |
| 256 | 256 | 256 | 0 |
| 257 | 256 | 257 | 1 |
| 600 | 256 | 600 | 344 |

At 600 holds both reducers retain the oldest and every other hold; local JSON restore retains all. The omitted candidate requires explicit override or a later candidate re-send when capacity exists. After 270 rebinds, audit histories remain local 256/hive 200 with cumulative total 270 and 330 remaining holds. Per-plan candidate cap remains 8.

Five actual-size journal fixtures test an append ending one byte below 64 MiB, exactly at 64 MiB, one byte over, and files already at/over the cap. Only the first two succeed; all refusals leave bytes unchanged and p held. Successful entries replay. The large padding fixtures are excluded from publication, with exact generation recipe, sizes and SHA-256 retained. No cap constant was patched; fixed operation time/UUID only make exact entry length calculable.

**Residual aggregate bounds remain OPEN Low:** complete authoritative holds and retained plan identity/provenance are still uncapped, deliberately not dropped. The 64 MiB check is an append-admission limit; startup loads an already larger file. No admission/retirement/compaction workflow is provided or OOM measured.

**F-unapplied-observability — OPEN Low:** 201 synthetic mismatching journal entries yield only the newest 200 `journal_status()['unapplied']` records, pending zero, and no omitted/total counter. Errors are logged and the raw journal retains all 201, so this is not silent on every channel or lost authority. It does fail complete status enumeration beyond the history cap. Expose a cumulative/overflow indication and a way to retrieve the missing dispositions; do not truncate active holds.

## 5. Defaults, compatibility, documentation and authored tests

`HiveAppliance()` still constructs and ticks normally; **only rebind is refused** without a journal. `volatile_rebinds=True` explicitly restores volatile behavior. `HIVE_REBIND_JOURNAL` supplies the path, and an explicit argument overrides it. Direct `HiveReducer()` still permits volatile rebinds by default; the closed default finding is scoped to the public appliance.

Legacy v1 records lacking position/hash are reported unapplied with a reissue explanation and do not replay. After a new explicit operator rebind, the new v2 record replays while the v1 diagnostic remains visible. That fail-closed compatibility choice is correct, but operators need migration instructions.

**Recovery/migration documentation remains OPEN Low.** The appliance module's Usage block now shows a journal and opt-out. README has no journal configuration or upgrade explanation. The policy still says hive candidates/rebinds are in-memory and says nothing about position-bound full replay, old journal rejection, new default refusal, caps/rotation or uncertain-write recovery. The repository-wide caller search finds no production constructor call outside the module's example; remaining instantiations are tests. Existing ordinary-appliance callers remain usable, but prior callers relying on implicit volatile rebind must opt in or configure persistence. No claim is made that all external callers were audited.

The 18 new tests are legitimate focused controls, but the failed-rollback test checks only live fencing, not restart. Its “short_or_failed_write” test actually substitutes a directory, not a short write; independent probes cover real short writes. The new cap tests lower constants, while independent controls exercise the real boundaries. The old recovery-text test now genuinely restores a migration and asserts all reasons/hold visibility unconditionally. Direct invocation passes; poisoning restored text to empty causes an AssertionError, establishing that it is no longer vacuous.

## 6. Execution and regression accounting

**Full suite exactly once: 764 passed in 48.31s**, no failures/skips; runner wall time 48.85s. Python 3.10.12, pytest 9.1.1, installed build 1.5.0 (not requirements-dev's 1.6.1); packaging tests ran with recorded offline build-wheel hashes. Network guard blocks external Python socket connections. The independent harness reports **20/20 assertion groups**, including groups intentionally asserting defects; this is not 20 safety approvals. Focused followup and static checks exit 0. No initial fixture failure or second full-suite run.

| Retained/independent coverage | Result |
|---|---:|
| Exact foreign 7582 witnesses | 4/4, both reducers; 10 ordering variants plus mixed/unknown-source controls |
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
| H-oracle / F7 | Five poisoned-health controls detected; completeness mutant caught by both negative controls |
| Append/rollback/close / tail boundary faults | 9 / 12 cases, plus exact old fsync, prior-record and 2 startup-fsync controls |
| Actual journal/candidate boundaries | 5 journal sizes; 255/256/257 and retained 600 holds |

The 300-plan extraction retains the earlier sole recovery-text adaptation; semantics/lifecycle assertions are unchanged. The retained 600-hold helper has three explicitly recorded substitutions for the new hive candidate-key cap and overflow-preview refusal; audit/retention assertions remain intact. All source/extracted hashes and adaptations are recorded. The F7 failure-guard-only mutant still survives because intact completeness already excludes failed indices; this is not hidden as detection.

The unchanged `semantic_7133.py` again exits 1 for **three known obsolete legacy automatic-closure expectations**, with actual fail-closed results. Raw failures are retained and not relabeled passes or counted as authored-suite failures. Separate explicit-rebind controls pass. Plan-only evidence remains allowed under trusted-operator authority as in 7638; rebind does not transform it into incident-specific proof.

## Publication integrity

Only this report and new `experiments/20261008-astra-7656/` evidence are committed. The isolated product worktree remained clean and byte-identical across all 144 tracked non-experiment files; prior 7638 evidence verification passed 191 artifact/report hashes. Archived inputs include the four changed sources, complete `source/production.diff`, policy/setup inputs, helper provenance and original serialized witnesses. Outputs, stderr, exit codes, timings, fault journals, high-confidence credential-pattern scan and SHA-256 manifest accompany the report.

Test/build temporary files, 64 MiB padding fixtures, bytecode and third-party wheels are excluded; their relevant recipes/hashes remain. Raw patch/log whitespace is preserved; new-authored whitespace checks are separate. `verify_evidence.py` is read-only. Fast-forward-only publication and final fetched remote/local commit equality are verified after commit and recorded outside the manifest to avoid self-reference. No old evidence or scratch directory is staged.
