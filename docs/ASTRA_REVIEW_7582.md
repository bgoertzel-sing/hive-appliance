# Astra independent re-review 7582 — 4d5fdff

**Reviewer:** `openai/gpt-6-astra`, single reviewer, no delegation/fallback. Own session metadata and assistant transcript independently identify model `gpt-6-astra`, provider `openai`, API `openai-responses`; see evidence `model-verification.json`.

**Requested:** Protomega2, Telegram 7582; approved by glicerico, 7580. Ben's 7574 instruction, “sure implement the hold and rebind workflow,” agrees with the project decision dated 2026-10-07, option (a), message 7547. Telegram authority context is supplied by the requester; the decision file was independently read and preserved. **Date:** 2026-10-08. **Pin:** `4d5fdff7902963b2d07329e959f938451a109107`, verified equal to `origin/main` on clean clone and subsequent fetch. Full six-file delta since `df805ab`, commits `1a4f740` and `4d5fdff`, and both complete reducers were read.

**Evidence:** [README](../experiments/20261008-astra-7582/README.md), [independent results](../experiments/20261008-astra-7582/review7582.json), [focused controls](../experiments/20261008-astra-7582/followup7582.json). Names below refer to this evidence directory. Repository-operations, experiment-ledger and GitHub procedures applied. Only this report and new evidence are published. No product/test source edits, prior-evidence edits, credential changes or live operations.

## Verdicts and gate

| Item | Verdict | Result |
|---|---|---|
| D-option-conformance: selected workflow/provenance | **CLOSED — prior Medium** | The recorded hold/candidate/preview/audited-rebind workflow is now implemented for currently linked ownerless plans. No further reconciliation of the reversed option labels is needed. Lifecycle completeness remains open below. |
| O-ownerless-hold: exact witness and ordinary current-held re-send | **CLOSED — prior Medium, scoped** | Both hold APIs enumerate p; re-send records only candidate i; preview predicts i; audited rebind closes only i, leaves j open, clears reason. Restore/replay and late links work. |
| O-ownerless-hold: evidence safety across rebind | **OPEN — High, F-foreign-progress** | Both reducers retain pre-rebind successes explicitly addressed to j and use them to close new owner i. They do not buffer/revalidate that evidence when ownership becomes known. |
| O-ownerless-hold: non-audited escape | **OPEN — Medium, F-hold-expiry** | After the last linked incident resolves through another owned plan, the hold disappears. Formerly held p can then acquire a new owner via ordinary PLAN and close it using old evidence, without rebind audit. Hive also permits the existing INCIDENT(resolved=True) route. |
| Preview/rebind validation and live-state purity | **CLOSED for checked state/validation; OPEN Low for logging** | Full deep live-state equality, detached results, refusals, candidates, pending receipts and would_close pass. Hive preview emits a real “incident resolved” INFO message from its simulation. |
| Hive restart durability | **OPEN — Medium operability/audit limitation** | Event replay reconstructs holds and candidates, not operator rebinds/audit. It fails closed back into hold after an audited repair, unlike local snapshot restore. No new automatic fail-open on full replay demonstrated. |
| O-retention | **CLOSED — prior Medium** | 600/600 open incidents and holds retained, including oldest. Capacity warning observed. Resolved-only history still trims to 500 on incident insertion. |
| Late-link WARNING | **CLOSED** | Both reducers warn after completed ownerless p receives late links; no incident closes. |
| Bounds | **CLOSED for audit/per-plan caps and complete holds; OPEN Low for aggregate resources** | Local audit 256, hive 200; candidates 8/plan. Local candidate map 256 keys, hive has no global candidate-key cap. No current hold lost at caps. |
| Docs/docstrings/provenance | **CLOSED for corrected decision; OPEN Low for residual inaccuracies** | Local restored diagnostic guidance still calls owner_unproven the entire current quarantine. “Side-effect-free” hive preview and unconditional removal of re-send repair need qualifications. |
| Authored tests / retained safety regressions | **CLOSED as execution and legitimacy, not complete safety coverage** | Full suite once: **738 passed, 0 failed, 0 skipped**. New authored tests pass 8+5; changed 7542 tests pass 7. Independent failures/findings below are not hidden by suite success. |

**Gate recommendation:** keep the previously bounded explicitly-owned-plan repair/replay gate. **Do not approve the new ownerless hold/rebind path for production closure yet**: fix F-foreign-progress and the unaudited formerly-held transition. Preserve the retention and late-link fixes. Hive recovery/audit persistence needs an explicit operational solution before relying on it as a durable ownership authority. No deployment or gate state was changed by this review.

## 1. What is now fixed

The exact requested serialized witness, with local snapshot/restore and hive event-prefix replay after every event:

```text
INCIDENT(i, plan_id=p)
INCIDENT(j, plan_id=p)
PLAN(p, incident_id="", one step)
RECEIPT(x, plan_id=p, step_index=0, verified=True)
PLAN(p, incident_id=i, one step)
```

Both remain open `[i,j]`, have no p owner, and report `ownerless_linked` through both quarantine APIs (local key p, hive key `a1:p`). Both record candidate `[i]`. Deep-copy equality of **all** live reducer fields holds around previews; mutating returned candidate/receipt lists does not mutate either reducer. Both previews report allowed, `hold_reason=ownerless_linked`, candidate i and `would_close=[i]`. The receipt was already consumed as progress, so `held_receipts=[]` is an accurate description of the buffer, not proof that receipt evidence is being quarantined.

Audited `rebind_plan_owner(p,i,actor="Astra-7582",reason="fixture authority")` succeeds; i closes, j stays open, owner maps and audit agree, hold reason clears. Local JSON restore preserves the repair and audit.

Additional independent coverage:

- **144 hold/rebind schedules**, permutations of two INCIDENTs, ownerless PLAN and receipt, three addressing modes, live versus snapshot/serialized-replay variants, duplicate suffixes, candidate re-send and final audited rebind. **1,152 event-prefix checks** plus rebind checks.
- Retained **180 ownerless no-closure schedules / 1,224 states**, six owned-positive controls, four foreign-owned controls and **1,440 owned supersession schedules / 15,840 states**.
- Blank/whitespace/non-string actor/reason rejection; missing, resolved, differently linked and noncandidate targets refused without state change; explicit noncandidate override remains available.
- A receipt addressed only to an unlinked target remains buffered, appears in both previews and closes the chosen owner only when audited rebind makes it eligible. A 60-receipt control confirms application and audit clipping.
- Proper a1/a2 envelopes with identical plan/incident IDs keep candidates and rebinds isolated; a1 rebind cannot consume a2 candidate or close a2 incident. This is normal namespace isolation, not a claim about arbitrary delimiter-bearing identifier encodings.

**Unlinked ownerless plans:** no hold exists until an open incident links them. If linkage arrives first, subsequent owner-declaring PLAN is candidate-only. If a nonempty owner is declared while p has never been linked/held, normal first-owner assignment remains legal, and a late owning INCIDENT can close from existing plan receipts. That is outside the policy's currently linked-ownerless predicate; it is not the formerly-held escape below.

## 2. F-foreign-progress — OPEN High

[Local receipt handling](../controller/reducer.py#L433), [local rebind](../controller/reducer.py#L274), [hive receipt handling](../hive/reducer.py#L520), [hive rebind](../hive/reducer.py#L206).

Minimal counterexample in both reducers:

```text
INCIDENT(i, plan_id=p)
INCIDENT(j, plan_id=p)
PLAN(p, incident_id="", one step)
RECEIPT(x, plan_id=p, incident_id=j, step_index=0, verified=True)
PLAN(p, incident_id=i, one step)       # only records candidate i
preview_rebind(p,i)                   # held_receipts=[], would_close=[i]
rebind_plan_owner(p,i,actor=op,reason=proof)
```

**Actual:** i closes, j stays open. The only successful evidence explicitly names **j**, not i. The incident-only variant (empty receipt plan_id, incident_id=j) does the same. Four independent cases cover both addressing modes with/without local restore and serialized hive replay.

**Control:** declare i as owner before submitting the identical j receipt. Both reducers reject it, verified progress stays empty, and `[i,j]` remain open. A receipt naming j after rebind also cannot finish i. Therefore safety depends on whether the receipt arrives before versus after ownership proof.

Cause: ownerless_linked blocks closure but **not receipt application**. Only local legacy owner_unproven causes buffering. Current linked-ownerless receipts are consumed into step-index sets and marked seen; their incident identity is no longer represented in the progress sets. Rebind drains pending receipts but neither invalidates nor revalidates already admitted progress. Preview honestly predicts the unsafe actual result, but shows no buffered evidence from which an operator could discover this contradiction. Audit records closure with zero pending receipts.

This is a false-resolution safety defect, not a request to infer ownership from links. The older re-send path also reused such progress; the new audited API still fails to establish the intended recovery safety. **Remedy:** hold provenance-bearing receipts for unknown ownership and reapply against the chosen owner in arrival order, or invalidate unprovable progress and require fresh evidence. Preserve the existing N3/N5 ordering and fail-closed rules. Do not discard conflicting failures in a way that manufactures a successful completion.

Evidence: `review7582.json.foreign_progress_defect` and `followup7582.json.foreign_receipt_owned_controls`.

## 3. F-hold-expiry — OPEN Medium

[Local current-held predicate](../controller/reducer.py#L573), [hive predicate](../hive/reducer.py#L180), [PLAN assignment](../controller/reducer.py#L379), [hive PLAN assignment](../hive/reducer.py#L483).

```text
INCIDENT(i, plan_id=p); PLAN(p, owner=""); RECEIPT(p, step 0, success)
PLAN(p, owner=i)                      # p HELD; i is candidate only
PLAN(q, owner=i); RECEIPT(q, step 0, success)
                                      # legitimate owned q closes i
                                      # p disappears from both hold lists
INCIDENT(k, plan_id="")
PLAN(p, owner=k)                      # assigns owner, closes k, NO rebind audit
```

The sibling q closure itself conforms to Ben's any-owned-plan policy. The problem is that p's ownership uncertainty has no persistent disposition: the last link's closure removes the gate, while p retains old success and a stale candidate. This disproves “a formerly held ownerless plan can only get an owner through audited rebind.” It does **not** demonstrate bypass while a linked incident remains open.

The policy currently describes a *current* linked/open predicate; it does not explicitly specify permanent latching. Accordingly this is a **Medium lifecycle/conformance gap**, not a claim that sibling completion must be prohibited. Preserve an auditable disposition for formerly held plans, or explicitly specify and test safe retirement/reuse semantics. Do not assert that every historical re-send path is gone.

Hive has a shorter route through its pre-existing duplicate INCIDENT handler: `INCIDENT(i, resolved=True)` marks i resolved, clears p's derived hold, then ordinary PLAN can assign p to k. Local dedup ignores that duplicate resolution, so the same stream leaves local `[i,k]` open and hive none. The duplicate-INCIDENT divergence predates this patch; the new hold now depends on it. Agent unregister likewise removes link state rather than providing a rebind audit; it is a lifecycle reset, not an audited ownership repair.

Evidence: `review7582.json.non_audited_unhold`.

## 4. Durability, limits and diagnostic qualifications

### Hive restart: loss versus re-derivation

Hive has no snapshot/restore API. A fresh empty reducer loses **all** in-memory state, including incidents and the state from which holds are derived. It is misleading to describe that as “only candidates/audit are lost,” but also misleading to claim ordered replay necessarily loses the hold.

Full serialized event replay of the witness reconstructs p's hold, candidate i and open `[i,j]` consistently with pre-rebind local state. After an operator rebind, replaying the same ordinary event log reconstructs that **pre-rebind** hold again: no operator-rebind event was recorded, so owner/audit/closure cannot be reproduced. Local current snapshot restore retains the completed repair and audit. Pure ordinary-event replay of the local reducer also cannot recreate a side-channel operator call; the distinction is local checkpoint support, not a different event semantics.

**OPEN Medium operability/audit limitation:** recovery loses authorization history and may repeat an already completed operator action. Full replay is fail-closed here, not a demonstrated unsafe automatic ownership assignment. A persisted, replayable operator operation/audit or a durable hive checkpoint would be needed for equivalent recovery. Partial replay and upstream cursor recovery were not claimed or tested.

### Bounds and retention

| Structure | Local | Hive | Observed |
|---|---:|---:|---|
| Current holds, 600 open linked plans | 600 | 600 | No global hold truncation; oldest retained; local restore retains all. |
| Owner candidate plan keys | 256 | No global cap | At 600 holds: local 256 keys / 344 drops counted; hive 600 keys. |
| Candidates per plan | 8 | 8 | Further distinct candidates omitted; current hold remains. |
| Audit records | 256 | 200 | After 270 rebinds: bounded history, cumulative total 270, remaining 330 holds. |
| Receipt IDs per audit | 32 per effect kind | 50 total held IDs | 60 buffered successes: counts 60 in both, IDs clipped to 32/50; closure correct. |

Local candidate-key overflow does **not** lose a hold, but can require deliberate `allow_non_candidate=True` or a later candidate re-send after space is freed. It counts dropped keys but still logs “recorded as owner candidate”; per-plan overflow is also not described by that log. Do not interpret either candidate sample as the authoritative hold list. Hive “capped candidates” means per-plan only, not globally bounded memory.

The retention fix preserves every OPEN per-agent incident and warns above 500; independent 600-plan evidence confirms 600/600. Resolved history trims on incident insertion: 550 resolved plus one open ends at 500 total. A large backlog that becomes resolved via receipts can remain above 500 until another incident insertion; there is no claim of instantaneous pruning on every state mutation. Hive-level correlated-incident retention is a separate structure, not the per-agent hold source.

**OPEN Low aggregate-resource limitation:** complete current-state views and hive candidate keys are unbounded. This is not a measured OOM or reason to silently drop active holds. Pagination/admission/overflow accounting is preferable to truncating the authoritative list.

### Preview logging and stale guidance — OPEN Low

`preview_rebind()` deep live-state purity passes. However, hive simulation calls `_maybe_resolve_plan`, which logs `Agent a1 incident i resolved (all 1 plan steps verified)` at INFO. The real i remains open. That unqualified message can mislead operational logs; simulated closures should be silent or clearly labeled. Local existing N9 no-log regression controls remain passing.

After local restore with a current ownerless candidate, `migration_diagnostics['recovery']` still says “authoritative CURRENT quarantine is owner_unproven.” In the witness owner_unproven is empty but `quarantined_plans()==['p']`; the message is now false as a complete enumeration rule. The main policy's provenance and reason-map docstrings were corrected. Its “audit then closes” wording is conceptual: actual code applies rebind/closure before appending the audit, with no separately demonstrated crash-atomic transaction. Historical 7542 test header dates/option wording are explicitly marked superseded, not current decision evidence.

## 5. Test legitimacy and actual execution

The sole full-suite command is preserved in `pytest-started.json` / `run_primary.py`. Actual output: **738 passed in 48.77s; no failures or skips**. Runner wall time 49.39s. Python 3.10.12, pytest 9.1.1, installed build 1.5.0 (not the requirements-dev pin 1.6.1); exact environment and offline build-wheel hashes are preserved. Packaging ran rather than skipped. No second full-suite run.

The **8** hold tests and **5** retention/late-link tests are legitimate. The **7** changed 7542 tests strengthen the policy assertion: the old successful re-send expectation becomes candidate-only/no closure, including restore. They do not weaken the ownerless safety requirement. Limitations: authored preview state checks cover only selected hive fields (independent tests compare the complete object); the test named “unknown_resolved_and_other_plan_targets” does not actually construct a resolved target (independently covered here); none catches foreign pre-rebind progress, hold expiry, or restart audit loss.

| Independent retained coverage | Actual result |
|---|---:|
| N1–N4/mixed receipt schedules | 398/398 |
| Current-format and prior ordered-format semantic sweeps | 3,072/3,072 each |
| Legacy fail-closed sweep / original witnesses | 384/384; 2/2 |
| Ownership lifecycle / authentic old ownership / namespace | 48/48; 6/6; 1/1 |
| N8 boundary/disk | 14/14 |
| Explicit stale-progress disk recovery / rebind controls / pending liveness | 6/6; 8/8; 6/6 |
| H2/N9/N10 7173 groups | 10/10 (including 51 H2 schedules) |
| N9/N10 7195 groups | 7/7 (including 64 receipt schedules) |
| Legacy 300-plan quarantine | 300 → 151 → 0 current holds; 20 JSON roundtrips per stage; history remains 256 |
| H-oracle | Literal health sequence and five poisoned-health controls detected |
| F7 | Original owned trio passes; identical completeness-gate mutant caught by both negatives |

An additional failure-guard-only mutant survives the F7 trio: for these valid event-derived states, a failed step has already been removed from verified progress, so the intact cardinality guard is sufficient. This is not evidence that the repaired completeness negatives are vacuous.

**Explicit exception:** unchanged `semantic_7133.py` exits 1 for three known obsolete stale-progress expectations: it demands automatic closure after fresh receipts despite an unproven legacy owner and without an operator rebind. Actual state remains fail-closed. Original source, output and failure records are retained; the separate explicit-rebind disk controls pass. This is not counted as 738 suite failures or silently relabeled a passing old script. The new finding witnesses pass their assertions because they reproduce the described defects, not because product conformance is established.

## Publication integrity

Tracked non-experiment product files were compared byte-for-byte with the reviewed pin; source and unchanged helper hashes, exact subprocess commands, stdout/stderr, exit codes, timings, serialized cases and mutation evidence are included. Disposable test/build outputs and third-party wheels are excluded from publication; wheel hashes remain. High-confidence credential-pattern scan plus focused fixture/log inspection is recorded, not presented as an exhaustive secret detector. `SHA256SUMS` and `verify_evidence.py` verify the delivered artifacts and report.

Whitespace check qualification: the full evidence diff flags verbatim patch context, captured stdout spacing, an unchanged historical helper EOF and archived Markdown hard breaks. Those evidence bytes were preserved; the scoped new-authored report/helpers check passes. See `staging-checks.json`.
