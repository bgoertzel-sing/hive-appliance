# Astra Re-review 7146 — tracked evidence

Model (self-reported): GPT-6 (Codex; Astra reviewer role).
Routing verification: parent verifies the gateway session record; this header is not independent routing evidence.
Date: 2026-09-28. Reviewed pin: `8bbd10b` (full hash in evidence `environment.json`).
Worktree: `/home/openclaw/research-agent/projects/hive-appliance/repos/hive-astra-7146`.
Evidence: [20260928-astra-7146](../experiments/20260928-astra-7146/).
Inputs: both independent 7133 reviews and `ASTRA_7133_RECONCILIATION.md`.
No production edits, pushes, live repair commands, or dependency provisioning. The other `20260928-astra-7146/` directory was not touched.

## Verdict

**Keep live repair/replay gated.** The re-registration completion exploit is fixed, and quarantine fixes the exact ownerless stale-progress witness. However, **N8 still closes an incident with a newer failure pending**, and **N5 still admits stale progress when a legacy snapshot has a recoverable incident link**. Both are reproducible safety failures, independently of agreement between reducers. N6's historical ownership guarantee also remains incomplete; the literal rejection-before-any-mutation claim is false at public reducer entry points.

Full pytest was invoked **exactly once: 674 collected, 673 passed, 1 failed**, actual child exit **1**. Only isolated wheel-build provisioning failed offline. All nine new tests passed. The original 402 schedules are now **400 pass / 2 fail**, not 402 passes; both changed outcomes are explained below rather than silently rewriting their oracles.

## Per-finding status

Statuses are bounded to named defects, not whole-subsystem certification. N8 is the alias of the second 7133 review's safety finding called N7; N7 here always means diagnostics.

| ID | Status | Evidence and qualification |
|---|---|---|
| A1 | CLOSED, retained | Independent SQLite winner/stale worker lease probe passes. |
| A2 | CLOSED, retained | Active partial retained, orphan partial removed. |
| H1 | CLOSED, retained | Polling cannot hide an unresolved critical incident; public successful repair remains healthy. |
| H2 | PARTIAL | Original targeted/index/dedup group passes; N5/N8 unsafe completion remains. |
| U1 | CLOSED, retained | Checkpoint create/readback failures block dispatch; rollback failure audit retained. |
| U2 | CLOSED, retained | Bounded shell rollback/order/metadata/flags/CLI probes pass. |
| U3 | CLOSED for original scope | Incident dedup, composite progress and current round trips pass; historical migration is not certified. |
| L1 | CLOSED, retained | Timeout/stop ownership and eventual restart pass. |
| S1 | CLOSED, retained | Terminal transitions and invalid direct-SQL values rejected. |
| P1-symlink | CLOSED, retained | Main/thumbnail symlink and outside-creation controls pass. |
| P2-store | CLOSED, retained | Rooted production wiring, canonical paths, all mutators and outside sentinels pass. |
| N1 | CLOSED, retained | Real public repair success HEALTHY/0; failure FAILED/1, rolled_back. |
| N2 | CLOSED, retained | Distinct indices, dedup, retry, invalid index and legacy boolean controls pass. |
| N3 | CLOSED for original pre-PLAN batch defect | Original corrected terminal cases pass; late incident bypass is separately N8. |
| N4 | CLOSED for original timing defect | Original witness and seven repeated local snapshot boundaries pass. |
| N5 | PARTIAL | 384 fail-closed cases and exact B stale witness pass; linked legacy stale-progress counterexample still closes without fresh step 0. |
| N6(a), re-registration | PARTIAL under strict requested claim | Completion/link/progress exploit CLOSED; handler rejects before those mutations. Public local `state` and hive timestamps still mutate on rejected PLAN. |
| N6(b), old ownership | PARTIAL | Quarantine/replay contract works, but lost historical owner can be replaced by another PLAN; two authentic historical-owner oracles still fail. |
| N7, diagnostics | CLOSED for reported loss/visibility defect | Durable cumulative diagnostics and migration warning now present. Unbounded affected-plan list is a remaining scalability limitation. |
| N8, buffered failure | OPEN, High | Both reducers report HEALTHY/0 with newer step-0 failure still pending; all tested local snapshot boundaries reproduce. |

Original eleven: ten bounded CLOSED, H2 PARTIAL.

## Safety findings and exact witnesses

### N8: still completes while newer owner-addressed failure is pending

Observed current event stream:

```text
PLAN p -> i, two steps
RECEIPT p/0 true
RECEIPT i/0 false, incident-only
INCIDENT i
RECEIPT p/1 true
```

Both reducers close i with verified `{0,1}`, failure still pending, hive **HEALTHY/0**. Moving the failed receipt after INCIDENT also reproduces. The incident is not linked and its receipt is not drained before owner-based completion. A later same-owner PLAN drains the failure to verified `{1}`, failed `{0}`, but does not reopen i. Replaying PLAN **before** the final success keeps i open; a later fresh step-0 success legitimately closes it.

Evidence: `focused-witnesses.json` plus `boundary-and-disk.json`. The original focused current group has **14 rows: 4 pass / 10 fail**. Its failures are the two live N8 placements, five post-event snapshot boundaries, post-closure PLAN/no-reopen, and two older conservative liveness cases. Its four passes are exact stale migration, completed-plan rebound rejection, pre-success PLAN drain, fresh retry. Each old implementation has **6 rows: 3 pass / 3 fail**; both old reducers keep N8 open, while old rebound and the two liveness cases fail.

Additional N8 coverage: **14 schedules, 0 safety passes, 14/14 local/hive agreement after every event** = two failure placements × (live, pre-stream restore, five post-event boundaries). Each selected boundary restores local twice through JSON. These overlap the original focused cases and must not be added as disjoint discoveries. No hive snapshot API was invented.

### N5: exact B stale witness fixed, linked variant remains unsafe

The exact B witness uses authentic `e6afe16` producer and CheckpointManager: PLAN before incident; applied p/0 success; pending incident-only i/0 failure; unlinked INCIDENT i; checkpoint; current restore; PLAN; fresh p/1 only. **All 3 variants pass** now: direct, two current re-restores, repeated legacy restore. Ownerless quarantine drops old verified step 0, so fresh p/1 alone cannot close. Fresh p/0 then permits completion.

But the fix invalidates progress based on **ownership uncertainty**, not on discarded contradictory evidence. Change only the arriving INCIDENT to contain its legitimate `plan_id=p`:

```text
real e6afe16 producer:
  PLAN p -> i (2); p/0 true; i/0 false incident-only; INCIDENT i, plan_id=p
snapshot: plan_receipts={p:[0]}, pending @inc:i contains newer failure,
          one durable incident link i -> p
CheckpointManager disk round-trip -> 8bbd10b restore (and two current re-restores)
PLAN p -> i; fresh p/1 true
```

Observed: owner reconstruction succeeds; quarantine is empty; discard count is 1; stale `{0}` survives; fresh step 1 closes i. Authentic old loader on the **same snapshot and suffix** keeps i open, verified `{1}`, failed `{0}`. This is not merely disagreement about preserving discarded history: the direct safety oracle requires affected step 0 to be re-proven. Evidence: `new-risks.json` and `boundary-and-disk.json`, actual checkpoints in `linked-stale-checkpoints/`.

This is a concrete prelinked payload/legacy-migration witness, not a claim that normal Appliance emits that precise event ordering. The accepted schema and real old reducer produce it. **Inference:** invalidate affected success evidence when retiring pending buckets regardless of whether owner reconstruction succeeds.

### N6(a): core registration exploit repaired, strict atomicity not achieved

All A re-registration cases now pass: before completion plan-only, incident-only, explicit dual-address, after completion without new receipts, and current snapshot round-trip. B's rebound variants and foreign prelinked controls pass. Both retain the first nonempty owner and original step count. Other incidents are no longer closed merely because their link names p. Legitimate same-owner replay remains accepted.

At `_handle_plan`, rejection precedes step count/link/replay/completion changes. However, public `Reducer.reduce()` subsequently merges every non-RECOVERY event with a subject into component state. In `new-risks.json`, rejected `PLAN p -> other`, `subject='svc'`, changes **local keys `state` and `rejected_plan_registrations`**; state becomes `{'svc': {'id':'p','incident_id':'other','steps':[{},{}]}}`. Public HiveReducer updates event/agent/global timestamps before/after dispatch: changed keys `_state` and `rejected_plan_registrations`. Both pending buffers remain exactly unchanged; no receipt or plan counter drift was found beyond the rejection counter. Timestamps are normal observation bookkeeping, not demonstrated unsafe completion, but they falsify the literal “ANY mutation” statement. Local payload-state mutation is the substantive residual.

### N6(b): quarantine is safe until recovery, but cannot authenticate lost history

A's authentic ownerless witness now holds receipts without credit. On legitimate `PLAN p -> i`, it drains valid p/0, rejects p/1 addressed to other, and remains open; local and uninterrupted hive then agree. Prior to that PLAN their progress intentionally differs: local quarantines, hive knows the owner. Thus A's unchanged **18-case** harness reports **15 pass / 3 fail**: two intentional authentic baseline failures plus `old_snapshot_plan_before_incident`, whose failure is this conservative interim disagreement, not unsafe completion. Current-case agreement is **15/16**, and all sixteen current cases satisfy their final open-set expectation.

B authentic-old-ownership cases are **4 pass / 2 fail**. Both ambiguous-link cases now quarantine; both ordinary resolved-link controls pass. Remaining failures, one each for `e6afe16` and `5de0d53`:

```text
old producer: PLAN p -> i; INCIDENT other
snapshot loses first owner; current restore quarantines p
PLAN p -> other; verified p/0 + other; verified p/1 + other
```

Current accepts other as owner and closes it; historical-first-owner oracle requires other stay open. This uses **fresh evidence**, not spontaneous or stale-evidence closure. The implementation satisfies the narrower documented “PLAN re-establishes owner” contract, but no reducer field can establish whether this new declaration matches the lost original owner. Opposite old ownership histories still produce byte-identical snapshots. **Inference:** authenticated event replay or an explicit authoritative rebind contract is necessary to close the historical ownership guarantee; quarantine alone cannot recover information.

Use `corrected-old-owner-traces.json` for immutable intermediate ownership records. The unchanged B recorder retains owner-map references; its final tests remain valid, but two intermediate records required the supplied narrow correction harness.

## New-risk and availability probes

`new-risks.json` records **3/3 legitimate quarantine recovery cases**: two fresh receipts held before PLAN; fresh receipts after PLAN; repeated same-owner PLAN interleaved with receipts. Two current snapshot round trips precede recovery. All complete. Fresh receipts **without any owner-establishing PLAN remain held indefinitely**; this is deliberate fail-closed behavior, not a proven unbreakable deadlock. No permanent deadlock after legitimate nonempty-owner replay was observed. Recovery instructions should explicitly require that PLAN: the current generic `recovery` string only asks for fresh uniquely identified receipts.

Diagnostics survive **20 repeated current restores without multiplication**. A new legacy discarded entry added to a snapshot carrying count 1 makes count 2. Migration emits warnings; the pytest caplog test also passes. The affected-plan list is **not bounded by a fixed cap**: 2,048 ownerless input plans yield 2,048 stored IDs, 17,518 diagnostic JSON bytes. It is a deduplicated historical union, not exponential growth on repeated restores. IDs remain in diagnostics after recovery. This is a scalability/retention limitation, not evidence of a practical denial of service. `legacy_pending_discarded` is persisted within `migration_diagnostics`, not as a top-level field; A's obsolete `counter_in_snapshot=false` check must not be misread as continued loss.

Other conservative liveness limitations persist: PLAN before INCIDENT plus incident-only success waits for another PLAN; INCIDENT after all plan success remains open until a trigger. Both exist at the old baselines. They are not the N8 unsafe success defect.

## Exact rerun accounting

All scripts have stdout/stderr and actual child exits saved. Launchers return zero after recording children; that is **not** a child pass.

| Harness/group | Result | Child exit / interpretation |
|---|---|---|
| `adversarial.py` | Stops at first historical expected-bug assertion | 1; expected with repaired original N3 |
| `adversarial-inverted.py` | 3 corrected terminal pairs pass | 0 |
| `new_cases.py` | **397/398**, including **384/384** permutations | 1; one changed multi-plan outcome |
| `supplementary.py` | **3/4** | 1; old unsafe prelink expectation now rejected |
| Original 7024 total | **400/402** | Do not report all-green |
| `probes.py` | **14/14** scoped groups | 0 |
| `older-regressions.py` | **2/2** groups | 0 |
| `independent.py` | N1/N2, snapshot, public repair, rooted wiring pass | 0 |
| A original semantic | Current **1,920/1,920**; lifecycle **11/13** | 1; two baseline failures; legacy old equivalence oracle below |
| A legacy old equivalence | **0/384** exact uninterrupted progress matches | Intentional discard contract; 0 premature closures, 96 old false-noncompletion labels |
| A legacy information loss | Same-byte histories reproduced; both restored stay open | 1, obsolete lossless-success expectation |
| A expanded | Lifecycle **15/18**, fail-closed+fresh **384/384** | 1; baseline ×2 and quarantine interim disagreement |
| A followup | Current ownerless now safe on legitimate owner replay; old rebound controls remain unsafe | 0; observation harness, not universal success assertion |
| B current arrival-v1 | **3,072/3,072** | Part of semantic child exit 1 |
| B authentic 5de0d53 ordered format | **3,072/3,072** | Same oracle/boundary set |
| B authentic e6afe16 fail-closed+fresh | **384/384** | No premature completion |
| B opposite-byte-history disk witnesses | **2/2** | Conservative discard and fresh recovery |
| B exact stale-progress disk variants | **3/3** | Original witness repaired |
| B ownership/lifecycle | **46/48** | Two conservative late-event liveness cases |
| B authentic old ownership | **4/6** | Missing-owner/rebind cases ×2 |
| B agent namespace | **1/1** | Same plan/receipt IDs across agents remain isolated |
| B focused | Current **4/14**, each baseline **3/6**, total **10/26** | 1; overlaps semantic findings, not disjoint total |
| Extra N8 boundaries | **0/14 safety**, **14/14 agreement** | Probe exit 0 records observations, not safety success |
| Extra linked stale disk control | Current fails; real old loader stays open | Observation artifact, not pytest |

The 3,072 sweep contains the original 1,920 subset: 384 receipt permutations/address assignments × eight boundaries versus five. Selected boundaries restore twice. These overlapping counts must not be summed as independent schedules.

**Every original failing witness:**

- `two_plans_one_incident_failure`: q->i has verified 0 / failed 1; later p->i has both successes. At event 6 p now closes i (old oracle expects open until q retries). Source explicitly allows owner-authorized retry plans to supersede the forward incident link. This is an observed contract change, not a no-evidence closure: p is complete and owns i. Define/document supersession before treating this old test as obsolete; unrelated plan failure must not silently override intended repair policy.
- `prelinked_incident_only_different_plan_incident`: INCIDENT i prelinked p; INCIDENT other; pending i-only success; PLAN p->other. Old oracle wanted both closed; new code correctly rejects i's non-owner receipt and leaves both open. This failure is a legitimate safety correction.

No agreement mismatch was found in the original **402 schedules / 2,426 event states**, or B's **48 lifecycle cases / 276 event states** (`agreement-audit.json`). This does not validate their direct oracles: the first group contains two outcome mismatches, the second two liveness failures, and N8 separately demonstrates both reducers agreeing on unsafe health. A's ownerless migration intentionally diverges in progress before recovery, as above.

`independent.json` public paths use real Appliance/planner/verifier/HiveAppliance/LocalAgentAdapter with a receipt-producing executor double. Success: indices `[0,1]`, verified `[true,true]`, outcome `resolved`, local/hive open 0, HEALTHY. Failure: `[true,false]`, `rolled_back`, local/hive open 1, FAILED after two ticks. No arbitrary host repair command was run; separate shell regression checks touch bounded temporary files.

## Modified-test assessment

Delta `623c92b..8bbd10b` adds **nine tests in `tests/test_astra7133.py`**; existing production tests are not modified or deleted. These are legitimate positive/negative regression additions, not weakened old assertions. All nine pass in the sole suite run. They cover A's conflicting registrations, same-owner replay, owner-only receipts, synthetic ownerless quarantine, progress discard and durable/logged diagnostics.

They **do not cover both reviews adequately**: no N8 schedule, no real old producer + CheckpointManager stale-progress fixture, no linked stale-progress migration, no authentic ambiguous old ownership/rebind test, no public-state atomic rejection assertion, no bounded-diagnostics check. Their `both()` helper compares only open incident IDs after each event, not verified/failed sets, pending evidence, links, component state or health. Same-owner replay coverage is simple; our separate held-receipt replay controls extend it. The ownerless fixture is current snapshot field deletion rather than authentic old serialization. These omissions explain why nine passes coexist with the safety failures.

The older 7133 change to `test_astra7024.py` (already present at base `623c92b`) remains a legitimate explicit conservative legacy contract change: discard assertion plus fresh recovery, not deletion of final completion. It does not cover pre-existing applied success. No modified test can certify retirement of newer pending failures while retaining stale success.

## Full pytest, exactly once

```text
/usr/bin/python3 -m pytest tests/ -v -p no:cacheprovider \
  --basetemp=.../20260928-astra-7146/pytest-tmp
cwd: .../20260928-astra-7146/source
674 collected; 673 passed, 1 failed in 42.16s
actual child exit: 1; timed_out: false; wall: 42.542s
```

[stdout](../experiments/20260928-astra-7146/pytest.stdout), [stderr](../experiments/20260928-astra-7146/pytest.stderr), [exit record](../experiments/20260928-astra-7146/pytest-exit.json).

Only `tests/test_packaging.py::test_wheel_build` failed: isolated build cannot obtain `wheel` with `PIP_NO_INDEX=1` (requires wheel and setuptools>=61). This is an observed offline dependency-provisioning failure, not a reducer assertion. The author's 674-pass claim was not reproduced in this environment. No install command, packaging retry, or second pytest invocation was performed.

## Prioritized remaining fixes

1. **N8:** establish late ownership/linkage and drain eligible pending evidence coherently before completion. Cover both receipt placements, all boundaries, and post-closure replay.
2. **N5:** invalidate successes affected by retired pending evidence, independent of ownership reconstruction; add both unlinked and prelinked authentic disk fixtures.
3. **N6:** make public rejected-PLAN state mutation policy explicit and enforce it; require authenticated historical replay or explicit rebind authority where legacy first ownership is unknowable.
4. Define multi-plan retry/supersession semantics; preserve legitimate same-owner drain/completion and conservative quarantine recovery. Document the mandatory recovery PLAN.
5. Bound/summarize diagnostic ID retention and include current unresolved quarantine state in operator guidance; preserve cumulative counts. Requalify the exact witnesses before lifting the gate.

## Provenance and limitations

`run_review.py` pins the full commit, exports tracked source, copies original 7075 scripts, records hashes/environment, refuses a second suite invocation via exclusive start/output creation. `run_extra.py` executes the independent copied harnesses. All helper modules and authentic baseline reducers are copied into this evidence tree; A's files live under `review-a/` to avoid output-name collisions. `HIVE_SRC` is the pinned worktree; pytest uses the tracked export. Source manifests and final integrity checks establish unchanged production input.

**Label caveat:** unchanged `focused_witnesses.py` has hardcoded current label `623c92b`; in this new evidence its current-class rows actually import **8bbd10b** through HIVE_SRC. Old baseline rows remain authentic e6afe16/5de0d53. Do not mistake that inherited label for a different execution pin. B's recorder correction is supplied and rerun; use corrected snapshots for intermediate owners. Raw failures and old contract expectations were retained, not suppressed or rewritten.

To repeat, use a fresh evidence directory and clean pinned worktree; preserve the copied script layout, `guard/sitecustomize.py`, `tmp/`, legacy modules and HIVE_SRC environment. The launchers record actual child exits; observation probes may exit zero while explicitly saving failed safety oracles. Python 3.10.12, pytest 9.1.1; offline variables and Python socket guard are recorded (not an OS sandbox). UUIDs/checkpoint names are incidental; ordering sweeps are finite and exhaustive only over their stated sets. This review is not a live upgrade, transport attack, global concurrency proof or whole-codebase certification. Parent owns integration and publication.
