# Astra review 7542 — 85c505d

**Reviewer:** `gpt-6-astra`, single reviewer, no delegation. Runtime session metadata confirms `model: gpt-6-astra` for `agent:main:subagent:07797e6a-052e-403d-a939-6fa80be8256c`; see `model-verification.json`. Own transcript metadata additionally confirms provider `openai`, API `openai-responses`, model `gpt-6-astra` (`model-provider-verification.json`). This is not a fallback labeled Astra. Requested by Protomega2 (Telegram 7542), approved by glicerico (7540). Repository-operations and experiment-ledger procedures applied.

**Date:** 2026-10-06. **Reviewed pin:** `85c505d1608680f1ac965ad5fad46a573c032b35`, equal to `origin/main` in a new clean clone before testing. Clone: `projects/hive-appliance/repos/hive-astra-7542`; review branch: `review/astra-7542`. Read the complete six-file `c876525..85c505d` delta. No production/test source, credentials, previous evidence, or deployment state changed. The source snapshot and historical helper hashes were verified after testing.

**Evidence:** [run README](../experiments/20261006-astra-7542/README.md). Unless otherwise qualified, artifact names below are within that evidence directory. A passing finding-witness assertion demonstrates the described behavior, not that the product requirement is satisfied.

## Verdict

| Requested item | Verdict | Evidence / conclusion |
|---|---|---|
| 1. P3-ownerless safety | **CLOSED — prior Medium** | Exact 7519 witness leaves both incidents open in both reducers; 180 ownerless schedules / 1,224 per-event checks; six owned positive controls; 1,440 owned supersession schedules / 15,840 checks pass. |
| 2. Linked-ownerless operability | **OPEN — Medium** | Not in quarantine, no owner-specific diagnostic/log, preview/rebind refuse. An ordinary later owner-declaring PLAN *can* repair it; not irrecoverably stuck. Missing requested hold/rebind workflow, not a violation of the narrower “only owned plans close” rule. |
| 3. H-oracle-resolved | **CLOSED — prior Low** | Already-resolved first arrival remains UNKNOWN; same-event open/close is HEALTHY; all five health-only mutants caught. Expectations do not read hive health. |
| 4. F7 positive-test adaptation | **CLOSED** | Declaring `incident_id=inc_1` legitimately supplies the newly required prerequisite. Original intent was composite verification, not ownerless authorization. Adjacent old negative fixtures have a separate **Low** coverage gap below. |
| 5. Nine authored 7519 tests | **CLOSED as reviewed** | All nine pass; explicit expected open IDs/health make them non-tautological. Both reducers are exercised live; snapshot coverage is local only, correctly reflecting available APIs. |
| 6. Full suite / retained regressions | **CLOSED as execution and regression review; packaging remains unqualified** | One full run: **717 passed, 1 failed, 718 collected**. Only failure is offline wheel-build provisioning. N1–N10, H2 and the legacy quarantine follow-up retain their scoped closures. |

**Gate:** retain bounded current-format live repair/replay for **explicitly owned plans**. P3 safety is now compliant; do not claim delivery of linked-ownerless hold/rebind operability or extend the gate to unattended recovery of those plans. Legacy owner rebind remains manual, independently authorized, previewed and audited. No actual gate/deployment was changed.

## 1. P3-ownerless — CLOSED

Both completion functions now return if their durable owner map has no owner and match only the owner incident thereafter: [local](../controller/reducer.py#L517), [hive](../hive/reducer.py#L424). This implements Ben's decision (7525): linkage alone cannot authorize closure.

Exact retained witness, with local JSON snapshot/restore after **every event**, plus hive reconstruction from the serialized event prefix:

```text
INCIDENT(i, plan_id=p)
INCIDENT(j, plan_id=p)
PLAN(p, incident_id="", one step)
RECEIPT(x, plan_id=p, step_index=0, verified=True)
=> local open=[i,j]; hive open=[i,j]; both owner maps empty
```

`ownerless-witness.json` records every state and local snapshot. `ownerless-schedules.json` covers every permutation of PLAN, receipt, and one/two linked INCIDENTs, with plan-addressed, incident-only and dual-addressed receipts, live and restarted variants, plus duplicate receipt/PLAN/INCIDENT suffixes. All **180 schedules / 1,224 event states** leave every arrived incident open. Late PLAN, late INCIDENT, multiply linked and restoration boundaries are covered. These expectations come from arrived incident identities, not agreement between reducers.

**Important API qualification:** HiveReducer has **no snapshot/restore API**. Its restart evidence is serialized ordered-prefix replay into a new reducer, not a claim of hive checkpoint restoration. Local state is genuinely JSON-snapshotted/restored. Both are checked before/after the restart boundaries.

Six positive controls cover all three receipt-addressing modes, live and restarted: a two-step owned p does not close on its first success; its second closes i and leaves j open although j also links p. Four retained foreign-owner controls pass.

The **unchanged 7519 owned-plan matrix** also passes again: all 720 permutations of I, p, q, p-step-0, p-step-1 and q-failure, each live and restarted, with five duplicate/post-completion events. **1,440 schedules / 15,840 per-event checks** confirm p alone suffices, q stays failed, and sibling failure neither blocks nor reopens closure. Closure and health have event-derived expectations. See `policy-schedules.json`, `review7542.json.policy_schedules`.

## 2. O-ownerless-hold — OPEN, Medium operability gap

The project's recorded 7525 decision includes the recommended same hold/rebind path for linked-but-unowned plans. The implementation delivers the closure prohibition, **not that workflow**. These are different requirements.

After the exact witness and repeated local restore:

- `quarantined_plans()` is `[]`; `owner_unproven` is empty; `migration_diagnostics` is `{}`.
- p is registered and its verified set is `{0}`, but its owner is absent. Receipts are **credited/consumed**, not held for ownership proof.
- Both normal reducer logs, captured through DEBUG, contain no ownership/hold warning. Hive's generic registration/incident messages do not identify the blocked completion reason.
- `preview_rebind('p','i')` reports `allowed=False`, `refusal="plan is not quarantined"`. `rebind_plan_owner(...)` returns False. This remains true with deliberate `allow_non_candidate=True`; both refusals leave state unchanged. The attempted rebind itself emits a refusal warning, but normal processing did not expose the problem.
- Hive has neither a quarantine accessor nor a rebind API. Local current-format restore preserves the missing classification because the snapshot already contains `plan_owner={}`; it does not take the legacy migration branch.

**Not invisible in every sense, and not permanently unrecoverable.** Open incidents/failed health remain visible; a developer/operator comparing raw `plan_step_counts`, `plan_receipts` and `plan_owner` can infer missing ownership. Furthermore, a later ordinary `PLAN(p, incident_id=i, same steps)` establishes the first nonempty owner in **both** reducers and closes i using already accumulated progress; j remains open. No new receipt or operator rebind is required, and no `owner_rebinds` audit is created. This is an executable repair control, not speculation. Consequently, “incidents are stuck forever with no repair possible” would overstate the finding. Without corrected owner metadata, however, further successes and restores do not resolve the condition or put it on the documented actionable quarantine list.

**Pending growth:** no ownerlessness-specific unbounded pending queue was reproduced. For each addressing mode, **1,024 unique receipts** for a registered, linked ownerless plan leave pending count **0** in both reducers, including local restore. A late-PLAN control buffers **1,024 → 0** once the ownerless PLAN arrives, without closing i. The unbounded seen-ID sets grow to 1,024; unknown-plan/unlinkable-receipt buffering and seen-ID retention are pre-existing general behaviors, not new evidence that this fix accumulates pending receipts indefinitely.

**Why Medium:** an accepted legal schema value now leaves a completed repair apparently unresolved without the requested actionable hold reason or the advertised repair path; operators following quarantine/rebind guidance cannot repair it there. This is an availability/diagnostic workflow gap, **not false closure under Ben's ownership rule**, and not evidence that ordinary explicitly owned repairs are unsafe.

**Needed closure:** make linked-but-unowned current plans explicitly visible/held with an intentional, auditable ownership-establishment workflow (including late PLAN/INCIDENT and restore), or obtain and document a different recovery policy. Do not infer ownership from linkage to make the workflow convenient. Consider retained progress and multi-link ambiguity explicitly. The existing ordinary PLAN path must be reconciled with whichever authority policy is chosen; this review did not silently redefine it as a legacy override.

Evidence: `review7542.json.operability` includes raw state, normal logs, both preview/refusal controls, successful ordinary-PLAN repair and receipt counts.

## 3. H-oracle-resolved — CLOSED

`expected_health()` no longer uses mere incident history. `both()` identifies a new unresolved INCIDENT from the **event stream**, using an independent seen-ID set, and passes `opened_once` for that event. `prev` is the prior **expected** health returned by `agree()`, not the prior actual hive health.

Independent boundaries all pass:

| Stream boundary | Health |
|---|---|
| First INCIDENT already resolved | UNKNOWN |
| Two initially resolved incidents | UNKNOWN |
| Owned PLAN + all successes + late open INCIDENT | HEALTHY |
| Resolved arrival followed by new warning incident | DEGRADED |

The retained spy records **DEGRADED → HEALTHY** inside the late open/close event. Thus same-event HEALTHY remains legitimate. The explicit lifecycle trace is still `UNKNOWN, UNKNOWN, DEGRADED, FAILED, FAILED, FAILED, HEALTHY, DEGRADED`.

All **five** original in-memory health-only mutations are caught by health-specific assertions: force recomputation to HEALTHY, DEGRADED, FAILED, UNKNOWN (counts left intact), or initialize a registered agent HEALTHY. Poisoning hive health through all four values leaves the pure oracle's already-resolved expectation UNKNOWN.

The oracle is independent of **hive health**, but deliberately uses local incident lifecycle/severity; it is not a wholly independent model of both reducers. The event-derived policy/ownerless matrices supply additional independent lifecycle expectations. No product health defect was reproduced. See `review7542.json.health_mutations` and `.health_boundaries`.

## 4. F7 adaptation: legitimate; adjacent coverage weakness — OPEN, Low

Git history traces `TestF7CompositeReceipt` to **0744154**, “Apply P0 fixes F1-F13 from Astra review.” Its stated F7 purpose is “Receipt only resolves incident when ALL steps verified (composite).” The original positive fixture manually linked inc_1 and omitted the PLAN owner. Under the new authorization rule, that fixture lacks a required precondition. Adding `incident_id=inc_1` keeps its two-step completion assertion and is a **legitimate policy adaptation**, not evidence of a masked runtime regression. Original and current bytes/history are preserved in `git-source-audit.json`.

**New Low finding L-F7-negative-fixtures:** the adjacent `test_single_receipt_does_not_resolve` and `test_partial_failure_does_not_resolve` still register ownerless plans. Their open-state assertions now succeed for the ownership reason regardless of composite completeness. The partial-failure fixture also omits valid step indices. An in-memory mutant removing only the all-step-cardinality guard from local `_maybe_resolve` survives **all three** old F7 tests, including the adapted positive test. An independent explicitly owned incomplete-plan control detects that mutant. This is weak test coverage, **not a reproduced production completion defect**; newer tests and the independent matrices cover the behavior.

Recommended follow-up: supply explicit owners and valid distinct indices to the negative composite fixtures and assert the incident remains open after the first success, not just at the end. Evidence: `review7542.json.composite`. No test source was edited for this review.

## 5. Authored `test_astra7519.py` — legitimate, with limits

All **nine** tests pass in the sole full-suite run. Eight call `both()` for live local/hive agreement plus per-event health/step/count assertions; the remaining test is the explicit local restoration witness. Two tests exercise local restoration (the ownerless witness and owned positive control).

They contain explicit expected open identities, empty ownership and/or literal health assertions; they do not simply accept matching reducers. Ownerless linked, single/multiply linked, late link/receipt, owned/foreign-owner and both health boundaries are meaningful regressions. There is no hive snapshot coverage because no such API exists. The authored restoration test checks final open IDs after restoring every event, not explicit expected IDs after each prefix; the independent matrix adds that precision and serialized hive restart replay.

They omit operator quarantine/rebind visibility and the old F7 negative-fixture weakness. Those omissions do not make the nine tests tautologies or invalidate their covered closures.

## 6. Full suite and retained closures

Exactly **one** full-suite invocation; no dependency installation, retry, or second full run:

```text
/usr/bin/python3 -m pytest tests/ -v -p no:cacheprovider \
  --basetemp=.../20261006-astra-7542/pytest-tmp
cwd: .../20261006-astra-7542/source
718 collected; 717 passed; 1 failed; exit 1
45.56s pytest time; 46.1106s runner wall time
```

Failure: **`tests/test_packaging.py::test_wheel_build`**. The isolated build tries to provision `setuptools>=61` and `wheel`; under `PIP_NO_INDEX=1` its actual stderr says **“No matching distribution found for wheel.”** This does not establish a broken wheel, nor qualify packaging as passed. The claimed 718/0 is **not** the observed result. All nine new tests pass. Python/package versions and offline/socket-guard conditions are recorded in the evidence README/environment.

Retained independent helpers were copied byte-for-byte from 7519, executed on this pin, and verified afterward:

| Scope | Actual result |
|---|---|
| N1–N4 and mixed receipt cases, with 7519's documented policy adaptation retained | **398/398** |
| N5 current-format / authentic prior ordered-format schedules | **3,072/3,072 each** |
| Ambiguous legacy fail-closed / opposite-history witnesses | **384/384; 2/2** |
| Ownership lifecycle / authentic old-owner / agent namespace | **48/48; 6/6; 1/1** |
| N5 stale-progress explicit repair disk paths | **6/6** |
| N6 rebind/rejection, N7 diagnostics, pending-liveness mechanisms | All retained assertions pass |
| N8 completion boundaries | **14/14** |
| H2/N9/N10 retained 7173 groups | **10/10**, including **51 H2 schedules** |
| N9 receipt classification / N10 capped histories, 7195 | **7/7**, including **64 receipt schedules** |
| Earlier A/H/U/L/S/P groups and independent orchestration/path controls | Retained assertions pass |
| Quarantine follow-up, authentic 300-plan migration | Current **300 → 151 → 0**, historical sample **256**; **20** round trips at each stage |

Counts overlap; they are not independent discoveries to sum. The unchanged `semantic_7133.py` still exits **1** for its **three known obsolete automatic legacy-PLAN recovery expectations (0/3)**, just as in 7519. Its safety schedule families pass; the explicit manual-rebind disk controls separately pass. This known policy difference is preserved in raw logs, not relabeled green. The historical 7519 supersession adaptation was retained without further weakening.

## Publication and limits

Evidence includes every primary child invocation's exact command, start/exit JSON and stdout/stderr, a pinned source export, unchanged historical helpers, mutation/schedule witnesses, and integrity verification. Disposable pytest/tmp/cache files and untracked build products are excluded, not test outcomes. `SHA256SUMS` binds all published artifacts; `final-integrity.json` also binds this report. `verify_evidence.py` checks source, helper, artifact and report hashes.

Only this report and `experiments/20261006-astra-7542/` are publication changes. Fetch/rebase-if-needed and a credential-pattern scan precede the authorized main push. The tested production pin remains 85c505d even if a later publication requires rebasing the report-only commit. No production re-review of future changes is implied.

The staged whitespace check reports only preserved raw diff/log formatting, copied runner EOF spacing, and existing source-document Markdown hard breaks. These evidence bytes were retained rather than silently normalized; new report prose is whitespace-clean.
