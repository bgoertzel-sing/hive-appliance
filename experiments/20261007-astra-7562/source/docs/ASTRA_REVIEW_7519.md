# Astra Review 7519 — 9194f52

Reviewer: **gpt-6-astra**, one reviewer, no delegation. Runtime session metadata reports `model: gpt-6-astra` for session `agent:main:subagent:36a139fc-49ec-4033-b1a6-09f7e8ec3bed`. The requested `session_status` tool was not exposed; `sessions_list` was the available verification, not a fallback model label. Request: Protomega2 message 7519, with Ben's approval in 7517.

Date: 2026-10-06. Full reviewed pin: **9194f52d72a0e853427fd725d2683cc39db39339**, verified equal to fetched `origin/main` before review. New clean worktree: `projects/hive-appliance/repos/hive-astra-7519`; branch `review/astra-7519`. No production/test source or previous evidence was edited. Repository-operations and experiment-ledger procedures were applied. Evidence: [README](../experiments/20261006-astra-7519/README.md).

## Verdict

| Requested item | Status | Conclusion |
|---|---|---|
| 1. Current quarantine / recovery wording | **CLOSED** | Authentic 300-plan migration; 300 → 151 → 0 current members, historical sample stays 256; 20 round trips at each stage. Old wording replaced. |
| 2. Per-event health oracle | **OPEN — Low residual** | Missing assertions are fixed and five health-only mutations are detected. Same-event open/close expectation is correct. A newly found already-resolved-first-incident case makes the oracle assert HEALTHY against correct UNKNOWN. |
| 3. Ben's multi-plan policy | **OPEN — Medium contract gap** | Owned-plan supersession passes 1,440 schedules. However, ownerless current-format plans can still close linked incidents, contradicting the new “only owned plans” requirement. |
| 4. Ten authored tests / full suite | **CLOSED as review task** | Tests are legitimate but omit the two boundaries above. **708 passed, 1 failed, 709 collected**, exactly one full run. Wheel packaging remains unqualified offline. |
| 5. Previously closed regressions | **CLOSED, retained scopes** | N1–N10, H2 and original named fixes retain their scoped closures in the reruns below. No prior evidence or assertions were silently rewritten. |

**Two new findings:** one Medium policy/code discrepancy and one Low test-oracle defect. Neither is evidence that failed sibling plans block independently sufficient owned repairs. The ownerless fallback pre-existed this commit; it is newly incompatible with the explicit policy, not a newly introduced implementation change.

## New finding P3-ownerless — Medium, OPEN

The policy requires immutable ownership and says only owned plans can close an incident: [policy lines 13–18](https://github.com/bgoertzel-sing/hive-appliance/blob/9194f52d72a0e853427fd725d2683cc39db39339/docs/POLICY_MULTI_PLAN_SUPERSESSION.md#L13). Both completion functions still have a fallback when the owner map is empty:

- [local reducer, line 523](https://github.com/bgoertzel-sing/hive-appliance/blob/9194f52d72a0e853427fd725d2683cc39db39339/controller/reducer.py#L523): match `inc.plan_id == plan_id` without an owner;
- [hive reducer, line 431](https://github.com/bgoertzel-sing/hive-appliance/blob/9194f52d72a0e853427fd725d2683cc39db39339/hive/reducer.py#L431): same linked-plan fallback.

Independent witness, ordinary current-format events:

```text
INCIDENT(id=i, plan_id=p)
INCIDENT(id=j, plan_id=p)
PLAN(id=p, incident_id="", steps=[{}])
RECEIPT(id=x, plan_id=p, step_index=0, verified=True)
```

**Observed:** both incidents close in both reducers; both owner maps remain empty; local quarantine is empty. The same result survives local snapshot/restore after every event. An empty `Plan.incident_id` is permitted by the public schema (its default is empty), not an invalid malformed-snapshot attack. This witness establishes no immutable owner and even closes two incidents with one ownerless plan.

Evidence: `review7519.json.new_boundaries.ownerless_policy_witnesses`; complete executable witness in `review7519.py`. This is distinct from foreign-owner completion, which correctly leaves the non-owning incident open in four early/late + restore controls. Legacy quarantine also remains effective.

**Required closure:** enforce proven ownership in both completion paths, or obtain a separate explicit policy decision allowing this fallback and document its meaning. Under the currently requested policy, linkage alone is not immutable ownership. Add ownerless-linked and multiply-linked negative controls, including restore, without weakening the owned-plan success rule.

## New finding H-oracle-resolved — Low, OPEN

[tests/test_astra7160.py:66](https://github.com/bgoertzel-sing/hive-appliance/blob/9194f52d72a0e853427fd725d2683cc39db39339/tests/test_astra7160.py#L66) uses `or loc.incidents` as evidence of a past open period. That is too broad.

```text
register a1                       # UNKNOWN
INCIDENT(id=i, resolved=True)      # never open; hive stays UNKNOWN
```

The new oracle expects HEALTHY solely because local incident history is nonempty, and `both()` raises `health mismatch: hive=unknown expected=healthy`. This is an oracle false positive, not a reproduced runtime health defect. The helper's own documented contract says UNKNOWN until the first **open** incident.

Evidence: `review7519.json.new_boundaries.already_resolved_oracle`. Track actual lifecycle/opening information independently, rather than treating every historical incident as formerly open; retain the valid same-event closure case below. No reducer change is indicated by this witness.

### The author's same-event correction is correct, not masking a reducer issue

For `PLAN(p,i,1)`, a verified receipt, then a late unresolved warning `INCIDENT(i)`, the agent remains UNKNOWN before INCIDENT. Processing that incident first creates an open incident (DEGRADED), then recognizes the completed owned plan and resolves it (HEALTHY). A spy around the real recomputation records exactly **DEGRADED → HEALTHY** within that event. Final HEALTHY is semantically correct: the repair is fully proven and no incidents remain. Critical severity analogues are exercised by the policy matrix. The flawed part is generalizing this to incidents arriving already resolved.

The revised `agree()` computes severity/lifecycle expectations from **local** incidents and previously expected health, not from hive health. `both()` calls it initially and after every event. This is independent of the hive health implementation, though not an independent incident-lifecycle model. The new review supplements it with explicit event-derived sequences and policy expectations.

Five in-memory fault injections, without editing source, all produce a health-specific assertion: force recomputation to HEALTHY, DEGRADED, FAILED, or UNKNOWN while preserving counts; and initialize a registered agent to HEALTHY instead of UNKNOWN. The explicit lifecycle trace is `UNKNOWN, UNKNOWN, DEGRADED, FAILED, FAILED, FAILED, HEALTHY, DEGRADED`.

## Quarantine follow-up — CLOSED

The new `Reducer.quarantined_plans()` returns a sorted detached list of the actual `_owner_unproven` set. Restore unconditionally replaces old persisted recovery wording whenever diagnostics exist. It correctly names `owner_unproven`, the accessor, and `legacy_ownerless_plans` as a capped historical sample not updated by rebinds.

Independent fixture construction uses the actual **e6afe16** reducer to produce 300 PLAN-before-INCIDENT histories, then the actual **ef18db3** reducer to migrate and record candidates. These historical module bytes are retained and verified against Git. Its real old recovery text is present in `authentic-300-before.json`; no current snapshot fields are deleted to fake this test.

At initial, 149-rebound, and all-300-rebound stages, current membership is independently tracked as an expected set. It is respectively **300, 151, 0**, while the historical sample remains **256** and total **300**. Each stage survives **20** JSON snapshot/restore rounds with exact state equality; mutating the accessor result cannot mutate the reducer. Fixture rebinds use explicit `allow_non_candidate=True` because capped candidate history cannot authorize all 300 by default. This is not a recommendation to automate the override. The retained 7195 controls separately verify default refusal when candidate information was pruned.

## Owned-plan supersession — verified subcase

`policy-schedules.json` retains **1,440 schedules / 15,840 checked event states**: all 720 permutations of incident arrival, p registration, q registration, p step-0 success, p step-1 success, and q failure, each live and with local restore after every event. Every schedule then repeats failure, successes, INCIDENT, and PLAN. Expected closure and health derive from the event specification, not reducer agreement. Pending evidence becomes eligible at registration; only a complete p closes i. q remains failed. No sibling failure blocks closure or reopens i.

This covers fail-before-complete, complete-before-fail, late INCIDENT/PLAN/receipts, duplicate events and restore boundaries. Hive has **no snapshot API**: its restart variant reconstructs from ordered prefix replay; it is not mislabeled as snapshot restore. Four additional foreign-owner controls reject ownership reassignment and contradictory receipts, and prevent p owned by j from closing i even when i links p.

The historical `two_plans_one_incident_failure` expectation is now explicitly adapted to Ben's policy in a **new copy only**: expected open counts change from seven leading ones to six, closing immediately on p's final success. `adaptation.diff` records the exact one-line change. All **398/398** retained new cases then pass.

## Authored ten-test assessment

All ten `tests/test_astra7195.py` tests pass in the sole full-suite run. They are legitimate assertion-bearing regressions, not tautologies:

- Two migration tests assert text, exact current/historical membership, bounded totals and restore replacement. Their fixture is synthetic; this review adds authentic historical producers and partial rebinds.
- Three health tests assert a literal lifecycle trace, UNKNOWN before any incident, and rejection of a health-only mutant. `both()` now adds per-event independent-of-hive-health assertions. They miss already-resolved-first arrival.
- Five policy tests assert explicit final open IDs, a retained sibling failed step, late arrival, post-closure failure, incomplete-plan refusal, and foreign-owner exclusion. Local/hive agreement is additional evidence, not their only oracle. They do not test truly ownerless linked plans, which is why their names/documentation overstate full “only owned” coverage.

## Retained regression evidence

| Scope | Result |
|---|---|
| N1–N4 and mixed receipt schedules (`new_cases.py`, one documented policy adaptation) | **398/398** |
| N5 ordered current-format / actual older arrival-v1 snapshots | **3,072/3,072 each** |
| Ambiguous legacy fail-closed / opposite-history witnesses | **384/384; 2/2** |
| Ownership lifecycle / authentic old-owner controls / agent namespace | **48/48; 6/6; 1/1** |
| N5 authentic linked/unlinked stale progress, explicit rebind + fresh evidence | **6/6 disk recovery paths** |
| N6 strict rejection, candidate/override, N7 diagnostics | Retained mechanism and 7173 assertions pass |
| N8 completion boundaries | **14/14**, plus H2 boundaries |
| H2 / N9 / N10 retained adapted 7173 groups | **10/10**, including **51 H2 schedules** |
| N9 receipt classification / N10 authentic capped histories, retained 7195 | **7/7**, including **64 per-receipt schedules** |
| A1/A2, H1/H2, U1/U2/U3, L1/S1, P1/P2 prior groups | **14/14 + 2/2** |
| Independent public orchestration and production path containment | All assertions pass |

These are overlapping schedules, not additive independent discoveries. The unchanged `semantic_7133.py` exits **1** because its three obsolete automatic-PLAN legacy-recovery composite expectations still fail (**0/3**). Their safety behavior is preserved; explicit recovery is separately verified by the six disk paths. This known legacy-policy difference is retained raw, not hidden or called a passing invocation. The original broad semantic families and authentic old modules were rerun, not merely quoted from the prior report.

## Exact full-suite result

Exactly one invocation, no dependency install, retry or second full run:

```text
/usr/bin/python3 -m pytest tests/ -v -p no:cacheprovider \
  --basetemp=.../20261006-astra-7519/pytest-tmp
cwd: .../20261006-astra-7519/source
```

**709 collected; 708 passed, 1 failed; exit 1; 48.4025 seconds wall time.** Failure: `tests/test_packaging.py::test_wheel_build`. Actual isolated-build stderr reports no available `setuptools>=61` distribution with recorded `PIP_NO_INDEX=1`; installed setuptools is 59.6.0. This is an offline provisioning failure, not proof of a broken wheel or a passing packaging check. Environment: Python 3.10.12, pytest 9.1.1, build 1.5.0, wheel 0.37.1. External Python socket connects are blocked by the inherited review guard; this is not an OS sandbox.

## Gate recommendation and limits

Retain 7195's **bounded current-format live repair/replay recommendation for explicitly owned plans**, with the original closed-finding scopes. The new changes do not alter receipt/completion implementation beyond comments and the quarantine accessor/guidance. **Do not claim complete compliance with Policy 3 or extend that recommendation to ownerless linked-plan closure** until P3-ownerless is resolved. The Low helper defect needs a test fix but is not a runtime gate regression. No actual deployment gate was changed.

**Legacy rebind remains manual and independently authorized**, using preview and retained audit. Actor/reason are metadata, not authentication or reconstructible historical ownership. Do not enable unrestricted automatic rebind or treat `allow_non_candidate=True` as inferred authorization. Packaging remains unqualified here.

Evidence includes every primary child's start/exit JSON and stdout/stderr, source hashes, unchanged historical helper provenance, the exact policy adaptation and retained checkpoint data. Publication excludes disposable pytest/tmp/cache directories, not primary logs or outcomes. `SHA256SUMS` and `final-integrity.json` bind the published evidence, source pin and report. Only this report and its new evidence directory are committed. No credentials or deployment state were changed.
