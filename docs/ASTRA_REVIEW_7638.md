# Astra independent re-review 7638 — f18bc2c

**Reviewer:** `openai/gpt-6-astra`, single reviewer, no delegation or fallback. Own-session metadata and assistant history confirm provider `openai`, model `gpt-6-astra`, API `openai-responses`; see `model-verification.json`. **Date:** 2026-10-08. **Request:** Telegram 7638, following review 7582 (`af31967`). **Reviewed pin:** `f18bc2c7349f139707d1a9de9cf673d30bdea0fc`, equal to `origin/main` at clean clone. All five changed files were read completely, including both reducers, appliance wiring and both test files. The recorded hold/rebind decision and `docs/POLICY_MULTI_PLAN_SUPERSESSION.md` were read; Ben's 7547/7574 authority context was supplied with the assignment. The project decision input is preserved.

**Evidence:** [index](../experiments/20261008-astra-7638/README.md), [final independent results](../experiments/20261008-astra-7638/review7638-final.json), [sole full-suite output](../experiments/20261008-astra-7638/pytest.stdout). Artifact names below refer to this evidence directory. Repository-operations, experiment-ledger and GitHub procedures applied. No product/test-source changes, prior-evidence changes, credentials changes or live operations.

## Verdict and gate

**Do not approve ownerless hold/rebind for production closure yet.** The exact named-foreign-evidence and ordinary hold-expiry witnesses are repaired, but two High counterexamples remain: unregister/re-register bypasses the hold and credits foreign evidence, and journal replay can close an incident that the original audited execution left open. The optional journal also has two Medium crash-recovery defects. Preserve the existing bounded explicitly-owned-plan gate; this review does not alter any operational gate or approve wider deployment.

| Item | Verdict | Result |
|---|---|---|
| F-foreign-progress, exact 7582 witnesses | **CLOSED — prior High, scoped** | Both addressing modes, live/local restore/serialized hive replay: rebind leaves i open, reports discarded step 0 in preview and audit; fresh j evidence still cannot close i, fresh i evidence does. |
| F-hold-expiry, sibling closure and hive duplicate resolved INCIDENT | **CLOSED — prior Medium, scoped** | Holds persist as `ownerless_held`; ordinary PLAN only records candidate; audited rebind required. Local roundtrip and hive replay pass. |
| Lifetime-wide no-unaudited-owner promise | **OPEN — High, F-unregister-escape** | Hive unregister clears the latch but retains plan/progress; re-register then ordinary PLAN closes a different incident from explicitly foreign evidence without an audit. |
| Hive journal ordering/replay safety | **OPEN — High, F-journal-order** | Journal is applied at the first reconstructed hold, not the original operation position. Three streams change an originally open incident to resolved on restart. |
| Journal write-ahead/basic replay/idempotence | **CLOSED for tested mechanics, not full durability** | JSONL write/flush/fsync precedes mutation; open failure refuses unchanged; normal replay retains actor/reason and `replayed=True`; double event replay does not duplicate audit or append. |
| Refusal after fsync failure | **OPEN — Medium, F-journal-refused-fsync** | API returns False but intact flushed entry remains and authorizes the operation on restart. |
| Truncated-tail recovery and later append | **OPEN — Medium, F-journal-tail** | Append after an unterminated corrupt tail returns success/fsyncs, but next restart discards that successful operation together with the tail. |
| Default production journal persistence | **OPEN — Medium, existing operability limitation** | `HiveAppliance` forwards an explicit path but defaults to None; no production call site/configuration supplying a path was found. Default remains in-memory. |
| Hive preview INFO noise | **CLOSED — prior Low** | Closing preview produces no INFO-or-higher messages, no real closure, no journal writes or state mutation. |
| Local recovery guidance | **CLOSED — prior Low** | Actual restored text names `Reducer.quarantined_plans()` and all three reasons. |
| Aggregate bounds | **OPEN — Low, unchanged** | Complete hold lists, hive candidate-key map and now journal history remain globally unbounded. Do not fix by dropping active holds. |
| Retention, late-link warnings and retained safety gates | **CLOSED for exercised controls** | 600/600 holds retained, warnings observed; 1,440 owned supersession schedules and other regressions pass. |
| Authored tests | **CLOSED for legitimate changed expectations; OPEN Low test gap** | Full suite **746 passed**; seven new tests have substantive assertions, while the eighth recovery-text test takes an empty-text branch and asserts nothing. Corrected 7195 tests independently cover the text. |

## 1. Foreign evidence and hold repairs

The exact earlier stream was replayed, changing only the expected result from the prior defect assertion:

```text
INCIDENT(i, plan_id=p); INCIDENT(j, plan_id=p)
PLAN(p, incident_id="", one step)
RECEIPT(x, plan_id=p, incident_id=j, step=0, verified=True)
PLAN(p, incident_id=i)             # candidate only
preview_rebind(p,i); rebind(p,i)   # i and j remain open
RECEIPT(j-again, ..., incident_id=j)   # still open
RECEIPT(i-new, plan_id=p, incident_id=i, step=0, verified=True)
                                 # only i closes
```

The incident-only receipt variant uses empty `plan_id`, `incident_id=j`. Four exact cases cover both addressing modes with and without JSON local snapshot restore/serialized hive event replay. Preview and audit both report `foreign_steps_discarded=[0]`, and preview predicts no closure. A second rebind to j is refused because p is now owned, not quarantined.

Ten additional live/restored variants cover foreign failures, target success overwritten by foreign failure, foreign failure overwritten by target success, and ordering with plan-only evidence. Discarding a foreign failed step does **not** recover an earlier success: both success/failure sets lose that step, so completion must be re-proven. A three-step mixed case retains i's step 0 and plan-only step 2, drops j's step 1 and closes only after fresh i step 1. Pre-change current snapshots without `plan_step_src` discard unknown-provenance progress on rebind. Existing owned-plan behavior passes 1,440 schedules / 15,840 event states.

The prior sibling-q expiry stream now retains p as `ownerless_held`, including local JSON restore and complete serialized hive replay. A later PLAN(p,k) leaves k open and records only candidate k; audited rebind is required. Hive duplicate `INCIDENT(i,resolved=True)` likewise leaves the latch. Local duplicate-INCIDENT dedup remains different, but no longer creates the old hive hold escape. Late links and authentic legacy rebind controls remain passing.

### Incident-less evidence: allowed, but not incident proof

**Yes: a plan-only receipt collected while held can be credited to a newly introduced rebind target.** Independent witness: hold p linked to j; collect plan-only success; q legitimately closes j; introduce unlinked k; PLAN(p,k) records a candidate; audited rebind closes k with that old success. Preview explicitly predicts k's closure and discards no step.

This preserves the plan-addressed receipt semantics and the original 7582 plan-only acceptance witness; the receipt proves a step of **p**, not an arbitrary unrelated plan. Under the existing trusted-operator authority contract, it is acceptable only when the operator establishes that this plan and its evidence apply to the chosen incident. Candidate presence alone is not such proof. It is **not** a guarantee that all pre-rebind evidence names the target, nor a safe generic reassignment mechanism. The code comments claiming “only evidence naming the new owner” need this qualification. Requiring incident-specific fresh evidence would be a stricter policy change, not a silent reinterpretation of the accepted plan-only witness.

## 2. F-unregister-escape — OPEN High

[HiveReducer.unregister_agent](../hive/reducer.py#L459), also exposed through [HiveAppliance.unregister_agent](../hive/appliance.py#L90).

```text
register_agent(a1)
INCIDENT(j, plan_id=p); PLAN(p, owner="")
RECEIPT(x, plan_id=p, incident_id=j, step=0, success)
# p is held, owner absent, explicit source j
unregister_agent(a1); register_agent(a1)
INCIDENT(k, plan_id="")
PLAN(p, owner=k)
# k closes; no rebind audit
```

Unregister removes incidents and `_held_ownerless`, but leaves `_plan_steps`, verified/failed indices, step-source provenance, receipt dedup and candidates. Thus this is **not a clean lifecycle reset**. With no surviving link/latch, normal PLAN assigns k and completion uses j's retained success without `_discard_foreign_steps`. The same identity a1:p survives, ownership changes via an unaudited path, and the incident closes falsely under the new foreign-evidence rule.

Preserve quarantine/identity state across temporary unregister, or implement an explicit complete retirement/new-incarnation boundary that cannot retain old plan evidence. Removing only the safety latch is unsafe. Evidence: `F_unregister_escape` in final results. The earlier review mentioned unregister as a reset limitation; the new retained-provenance counterexample establishes concrete false closure and warrants High severity.

## 3. F-journal-order — OPEN High

[Journal replay](../hive/reducer.py#L314) is invoked after every ordinary event. Entries contain operation, identifiers, actor/reason, timestamp and candidate flag, but no event-log position or state boundary. `_replay_journal` ignores timestamp/candidate and applies as soon as an open target and hold exist.

```text
INCIDENT(i, plan_id=p); INCIDENT(j, plan_id=p)
PLAN(p, owner="", one step)
RECEIPT(yes, p, incident_id=i, success)
RECEIPT(no,  p, incident_id=i, failure)
PLAN(p, owner=i)                     # candidate
rebind(p,i)                          # journal appended; i remains OPEN
restart with journal; replay same serialized ordinary events
# journal applies immediately after initial ownerless PLAN
# yes now closes i; no records failure but cannot reopen i
```

**Actual after restart:** i resolved while p has a failed step. **Original:** i open with that same failure. Two additional variants reproduce the error: plan-only success then failure, and target-i success then foreign-j failure (the latter originally invalidates progress, but replay rejects the failure after prematurely establishing ownership).

This is false resolution, not merely audit loss, and does not require corruption or concurrent writers. The benign authored restart test has no success-then-failure transition, so it cannot detect this ordering error. Persistence must preserve the original operator-operation boundary relative to ordinary events; simply replaying all journal entries at the first possible hold is insufficient.

Even the benign restart control changes audit semantics: the original candidate is true and discarded steps are `[0]`; replay applies before candidate/evidence arrival and records candidate false and discarded steps `[]`. Actor/reason and `replayed=True` are preserved, but this is not an equivalent restoration of the original audit's effects. Preserve original operation/effect metadata separately from replay effects.

## 4. Journal durability and fault injection

### Confirmed mechanics

A real fsync wrapper observed a complete JSONL record on disk while live owner/audit were still unchanged. Normal restart loads the entry before any hold exists, then eventually restores owner and original actor/reason with `replayed=True`; it does not rewrite the file. Replaying the complete event stream twice and invoking journal replay again leaves one audit record. Duplicate physical journal lines likewise apply only once, although the redundant entry stays pending indefinitely rather than being retired.

An actual append-open failure (journal path replaced with a directory after construction) returns False with the complete reducer object unchanged. This does not establish safety at later failure points.

### F-journal-refused-fsync — OPEN Medium

[Append](../hive/reducer.py#L304) writes and flushes before `os.fsync`. Fault injection makes fsync raise `OSError`. The public API returns False, logs refusal, and does not mutate live ownership/audit. However, the complete entry already exists. A fresh reducer loads it and applies the allegedly refused operation, including closure.

This is an **indeterminate commit**, not a guaranteed refusal. Define a recoverable commit/abort or explicit indeterminate/fenced outcome, and test restart following each write/flush/fsync failure boundary. Do not promise fail-closed refusal solely from the absence of live mutation. Evidence: `F_journal_refused_fsync`.

### F-journal-tail — OPEN Medium

[Loader](../hive/reducer.py#L281) warns and skips malformed complete JSON lines and structurally invalid entries; a later good complete line is still replayed. A truncated terminal fragment is also skipped. But that fragment is left physically in place:

```text
existing file: {"op":                # no newline
successful append: {complete valid entry}\n
next restart: concatenated line is invalid; both are skipped
```

The new call returned True and fsynced, yet restart loses its ownership/audit and restores the hold. Repair/quarantine the torn tail before admitting further successful appends, with an explicit recovery contract. An invalid UTF-8 byte also raises `UnicodeDecodeError` during construction rather than receiving line-level recovery; this is an additional availability limitation in the same loader area. Evidence: raw journal files and `F_journal_tail`.

### Default configuration and limits

[HiveAppliance constructor](../hive/appliance.py#L49) correctly forwards a supplied path, but defaults to None. Repository production-code/documentation search found no construction/configuration that supplies a persistent path. The usage example still constructs `HiveAppliance()`. The default therefore retains the earlier **Medium loss-of-rebind/audit-on-restart limitation**; the new optional mechanism does not close it for production, and enabling it currently introduces F-journal-order.

No parent-directory fsync, rotation/compaction or multi-writer serialization is implemented. These are static limitations, not separately demonstrated power-loss or concurrent-writer failures here. Existing file fsync was exercised, not physical power interruption.

## 5. Low items and test legitimacy

Hive preview uses a detached simulation with `_quiet=True`, journal disabled and pending journal emptied. Full-object equality and output-alias probes pass; no INFO-or-higher resolution message is emitted. Local restored recovery text actually names `Reducer.quarantined_plans()`, `owner_unproven`, `ownerless_linked` and `ownerless_held`.

The changed `test_astra7195.py` replaces an obsolete exact guidance string and **adds** assertions for all reasons. It does not weaken semantic/quarantine tests. Its 300-plan loop remains substantive. All eight tests in `test_astra7582.py` pass in the full suite, but its final recovery-text test never restores a snapshot, obtains empty `migration_diagnostics`, then skips its only assertion under `if rec:`. **Low coverage gap**, not a remaining product-text bug: the changed 7195 tests and independent restore probe really check the text. The seven other new tests are legitimate scoped controls, but omit incident-only foreign evidence, unregister, journal ordering and post-write failure/tail handling.

Aggregate resources remain **OPEN Low**: 600 active holds are correctly retained, local candidate keys cap at 256 with 344 drops counted, hive retains 600 keys, per-plan candidate cap is 8, and audit histories cap at 256/200 while cumulative totals reach 270. No active hold disappears. New hold-latch/provenance state and append-only journal likewise need lifecycle/admission/compaction policy rather than silent authoritative-state truncation. No measured OOM is claimed.

## 6. Execution and regression accounting

The **full suite was run exactly once**: **746 passed in 43.16s**, no failures or skips; runner wall time 43.56s. Python 3.10.12, pytest 9.1.1, build 1.5.0 (not the declared requirements-dev 1.6.1); packaging tests ran. Environment, build-wheel hashes and exact commands are recorded. The clean product tree remained byte-identical to the pin.

Final independent harness: **15/15 groups met their assertions**, including four groups that intentionally assert the reproduced defects. This is not “all safety checks passed.” The initial independent run had one fixture setup error: it supplied an existing directory to the constructor, so loading failed before append could be tested. The final harness constructs normally and then substitutes the directory for append fault injection; it also detaches owner-map evidence. Both runs are retained; only independent probes were rerun, never the full suite.

| Retained coverage | Result |
|---|---:|
| Exact named-foreign 7582 witnesses | 4/4; two reducers per case |
| Foreign/failed/plan-only ordering variants | 10/10 plus mixed three-step and unknown-provenance controls |
| Hold/rebind schedules | 144 / 1,152 event-prefix checks |
| P3-ownerless schedules | 180 / 1,224 states |
| Owned supersession schedules | 1,440 / 15,840 states |
| Owned positives / foreign-owned controls | 6/6; 4/4 |
| N1–N4/mixed receipt controls | 398/398 |
| Current/prior-ordered semantic sweeps | 3,072/3,072 each |
| Legacy fail-closed / original witnesses | 384/384; 2/2 |
| Ownership lifecycle / authentic old ownership / namespace | 48/48; 6/6; 1/1 |
| N8 boundary/disk | 14/14 |
| Explicit stale-progress disk / rebind / pending liveness | 6/6; 8/8; 6/6 |
| H2/N9/N10 7173 groups | 10/10, including 51 H2 schedules |
| N9/N10 7195 groups | 7/7, including 64 receipt schedules |
| Authentic legacy quarantine | 300 → 151 → 0; 20 JSON roundtrips per stage; history 256 |
| H-oracle | Literal health sequence; five poisoned-health controls detected |
| F7 | Owned trio passes; completeness mutant caught by both negatives |
| Active retention and late links | 600/600, oldest retained; warnings in both reducers |

The authentic 300-plan helper's **sole** extraction adaptation changes its obsolete guidance-string assertion to the new authoritative hold-list text; all lifecycle assertions are unchanged, with old/new text and extraction hash recorded. The F7 failure-guard-only mutant still survives because failed indices have already been removed from verified progress and the completeness check remains; this does not make the two completeness-negative tests vacuous.

The unchanged `semantic_7133.py` again exits 1 for **three known obsolete expectations** demanding automatic closure from legacy unproven ownership without operator rebind. Actual results remain fail-closed; all three raw cases and the failure output are retained. They are not hidden as passes or counted as authored-suite failures. Separate explicit-rebind controls pass.

## Publication integrity

Only this report and new `experiments/20261008-astra-7638/` evidence are published. Source verification covers all 142 tracked non-experiment files before report creation; the five reviewed files and policy/setup inputs are archived. Unchanged helper hashes, subprocess outputs/exit codes, serialized witnesses, fault journals, a high-confidence credential-pattern scan and artifact SHA-256 manifest accompany the report. Test/build scratch and third-party wheels are excluded from publication; wheel hashes remain. Raw captured patch/log whitespace is preserved; a separate new-authored-file whitespace check is recorded. Fetch/fast-forward-only publication and final remote/hash verification are recorded outside the committed manifest to avoid self-referential hashes.
