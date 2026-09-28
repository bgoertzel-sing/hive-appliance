# Astra Re-review 7133 — tracked evidence

Model (self-reported): GPT-6 (Codex; Astra reviewer role).
Model routing: parent verifies the gateway session record; this header is not independent routing evidence.
Date: 2026-09-28.
Reviewed commit: `623c92be3e2ab96fd76024881066628b6c73abb5` (`main` pin supplied by parent).
Worktree: `/home/openclaw/research-agent/projects/hive-appliance/repos/hive-astra-7133`.
Evidence: [20260928-astra-7133](../experiments/20260928-astra-7133/).
Scope: independent re-review of N5/N6 changes since `5de0d53`, original regression reruns, one full pytest invocation. No production source edits, pushes, live repairs, or dependency provisioning.

## Verdict

**Retain the gated live-repair/replay restriction.** N5's unsafe legacy-pending completion is repaired under the explicit fail-closed migration contract. The original N6 resolved/unlinked receipt witnesses are repaired, but **N6 remains PARTIAL**: conflicting PLAN re-registration bypasses first-owner completion safety, and some authentic old snapshots cannot reconstruct an owner and admit contradictory progress. Agreement alone is not safety: both current reducers incorrectly close unrelated incidents in the re-registration witness.

Observed headline results:

- **384/384** legacy restores stay open with no pending-derived progress; **0 premature closures / 0 closures of any kind before fresh evidence**. Each stays open after fresh step 0 and closes only after fresh step 1.
- **1,920/1,920** current-format snapshot schedules pass the original latest-evidence oracle.
- **402/402** original 7024 schedules pass (398 new-cases + 4 supplementary).
- Both byte-identical legacy information-loss snapshots now stay open, including the history whose uninterrupted result legitimately closes.
- Real public `Appliance.repair()` path: success **HEALTHY/0**, failure **FAILED/1** after two hive ticks, using a receipt-producing executor double, not host repair commands.
- Full pytest, invoked **exactly once**: **664 passed, 1 failed, 665 collected**, true child exit **1**. The failure is isolated wheel-build dependency provisioning under `PIP_NO_INDEX=1`, not a reducer assertion. All nine new tests pass.

## Per-finding status

| ID | Status | Evidence / bounded scope |
|---|---|---|
| A1 | CLOSED, retained | Stale worker and concurrent SQLite claim checks pass. |
| A2 | CLOSED, retained | Live partial retained; orphan partial removed. |
| H1 | CLOSED, retained | Polling retains real critical incidents; public completed repair remains healthy. |
| H2 | PARTIAL | Original buffered/index/dedup cases pass; N6 targeted-completion holes remain. |
| U1 | CLOSED, retained | Checkpoint create/readback failures block dispatch; rollback failures retained. |
| U2 | CLOSED, retained | Bounded shell rollback/order/flags/metadata/CLI regression checks pass. |
| U3 | CLOSED for prior scope | Incident/composite/dedup and current snapshot probes pass; not certification of every historical migration. |
| L1 | CLOSED, retained | Worker timeout/stop ownership and eventual restart probes pass. |
| S1 | CLOSED, retained | Terminal and invalid direct-SQL state probes pass. |
| P1-symlink | CLOSED, retained | Main/thumbnail symlink and outside-creation protections pass. |
| P2-store | CLOSED, retained | Rooted production wiring, canonical admission, mutators, outside sentinels pass. |
| N1 | CLOSED, retained | Public repair success HEALTHY/0; failed step FAILED/1, rolled_back. |
| N2 | CLOSED, retained | Distinct indices, dedup/retry, invalid index and legacy boolean checks pass. |
| N3 | CLOSED, retained | Buffered success followed by failure remains open until valid retry. |
| N4 | CLOSED for named scope | Original timing witness plus seven local snapshot boundaries pass. |
| N5 | CLOSED under changed migration contract | All 384 bucketed snapshots discard pending evidence; both information-loss histories stay open; all 1,920 new-format schedules pass. |
| N6 | PARTIAL | Original resolved/unlinked/foreign dual-address witnesses fixed; re-registration and ownerless legacy restore still unsafe (below). |
| N7 | OPEN, Low; new observability finding | Legacy evidence discard counter is in-memory only, absent from snapshot/operator reporting and reset by the next restore. |

Original eleven: **10 bounded CLOSED, H2 PARTIAL**. These statuses do not certify whole-codebase readiness.

## N6: first owner is stored, but not enforced as the completion authority

**Observed, Medium:** both reducers retain `p -> i` in their owner map, yet a second `PLAN p -> other` also sets `other.plan_id = p`. The second PLAN is **neither rejected nor silently ignored**: ownership remains unchanged but incident linkage mutates. Completion accepts every incident linked to p, even when it contradicts the retained owner.

Minimal stronger witness:

```text
INCIDENT i; INCIDENT other
PLAN p -> i (2 steps)
verified p/0; verified p/1       # i legitimately closes; other remains open
PLAN p -> other (2 steps)       # both now close other with NO new receipt
```

Both local and hive end with no open incidents; hive displays **HEALTHY/0**. Re-registering before completion also closes both on plan-only receipts, including after a local snapshot round trip. Incident-only receipts naming the newly linked non-owner also count toward p and close both: the owner check is guarded by an explicit receipt `plan_id`, not the subsequently inferred effective plan. Explicit dual-address `p + other` receipts are correctly rejected, so omitting plan identity changes admission.

Source: [local PLAN linkage](https://github.com/bgoertzel-sing/hive-appliance/blob/623c92b/controller/reducer.py#L150), [local completion](https://github.com/bgoertzel-sing/hive-appliance/blob/623c92b/controller/reducer.py#L243), [hive PLAN linkage](https://github.com/bgoertzel-sing/hive-appliance/blob/623c92b/hive/reducer.py#L317), [hive completion](https://github.com/bgoertzel-sing/hive-appliance/blob/623c92b/hive/reducer.py#L405).

Evidence: `expanded-results.json`, cases `reregister_plan_only`, `reregister_incident_only`, `reregister_after_complete`, `reregister_snapshot`, and passing control `reregister_dual_address`. All these current cases agree after **every event**; agreement confirms common behavior, not correctness. `followup-results.json` reproduces the no-new-receipt closure with **both authentic e6afe16 reducers**, establishing that the vulnerability is pre-existing and remains unclosed by the new first-owner claim.

A PLAN with an empty owner followed by a nonempty owner establishes the latter: operational semantics are first **nonempty** declared owner, not literally every first PLAN. This is recorded as a contract qualification, not a separate defect.

### Owner rebuilding fails when the legacy snapshot has no incident link

**Observed, Medium:** old snapshots with durable incident links reconstruct owners correctly, including resolved targets. But PLAN-before-INCIDENT can leave no stored link at all:

```text
old producer: PLAN p -> i (2 steps); INCIDENT i; INCIDENT other
snapshot -> current local restore     # owner map cannot be rebuilt
verified p/0
verified p/1, incident_id=other        # current local admits; live current hive rejects
PLAN p -> i                          # local closes i using the contradictory receipt
```

This is generated using the **real e6afe16 local reducer**, not only by deleting the new field. After the contradictory receipt, open counts agree but step progress already diverges. After PLAN replay, local has only `other` open; uninterrupted current hive has **i and other** open, with p verified `{0}` rather than local `{0,1}`. The snapshot contains no pending receipts, so this is **not a failure of the N5 discard sweep**. Receipt admission when owner is unknown is the remaining N6 issue.

Evidence: `followup-results.json` → `authentic_ownerless` contains original snapshot and every post-restore event/state. `expanded-results.json` → `old_snapshot_plan_before_incident` independently records the field-removal compatibility analogue. Restoration alone does not close an incident; the closure requires later contradictory evidence and re-registration. No claim of a spontaneous restore-only closure is made.

**Inference / fix:** reject conflicting re-registration before all mutation; make immutable effective ownership govern linkage, receipt admission (including incident-only), and completion. Where an old snapshot cannot prove ownership, quarantine progress until authoritative linkage is recovered, and revalidate previously admitted evidence before using it. Do not guess owner from arbitrary link iteration when links conflict.

### N6 controls and exact expanded counts

Expanded harness: **18 lifecycle cases**, **11 pass / 7 fail** under their declared safety expectations. Two failures are intentional authentic baseline controls; the other five are four re-registration variants and the ownerless restore divergence. Current-case agreement holds after every event in **15/16** cases; the sole current divergence is the ownerless restore. The baseline unlinked case also diverges, as expected.

Resolved and unlinked witnesses each pass current, new-snapshot, and owner-field-absent snapshot variants when incident links exist: **6/6**. Foreign-owner receipt rejection, valid owner incident-only receipts, unlinked incident-only buffering, and explicit conflicting dual-address re-registration controls pass. The follow-up authentic baseline and ownerless cases are separate evidence, not included in the 18.

The unchanged 7075 semantic harness reports lifecycle **11/13**: only its two baseline-local cases fail. Because that original harness combines the old local reducer with the *current* hive reducer, it is not by itself an all-old baseline now that hive changed. The expanded/follow-up harnesses explicitly load **both old implementations** for the baseline conclusions above.

## N5 contract, information loss, and discard side effects

The original `semantic_probes.py` and `legacy_information_loss.py` were copied byte-for-byte and rerun against the pin. Their historical `match uninterrupted` expectations are intentionally **not** the new legacy contract:

- Original semantic output: new-format **1,920 pass / 0 fail**; legacy **0/384 match exact uninterrupted progress**, **0 premature closures**, **96 false-noncompletion labels** under the old oracle; lifecycle **11/13**. True exit **1**. All 384 exact-progress comparisons fail because verified/failed evidence is discarded, not because all 384 close incorrectly.
- Original information-loss output proves byte-identical legacy snapshots and correct opposite live outcomes again. Both restored snapshots now have `open=[i]`, verified/failed empty. True exit **1** because the old oracle expects the uninterrupted-success history to close. This is expected contract drift, not an unsafe migration result.
- A separate explicit fail-closed oracle in `expanded_probes.py` runs all **384 authentic legacy snapshots**, requires empty step evidence and open i, then injects two unique fresh receipt IDs. **384/384 pass**; zero close before fresh evidence or after just fresh step 0. Cases and intermediate states are retained in `legacy-fail-closed-cases.json`.
- The original real CheckpointManager witness likewise remains open after restore and PLAN. New snapshots declare `pending_format: arrival-v1`; list-shaped pending receipt restoration retains order. The loader actually selects migration policy by container shape, not by consulting the tag.

**Discard is deliberately broader than ambiguity.** Both a single plan bucket with two successful distinct steps, and a two-bucket snapshot with only one receipt per step, lose their otherwise unambiguous pending evidence. Each records discarded=2 and remains open with empty progress. This is an acceptable conservative **safety** tradeoff if documented as whole-format retirement requiring new receipts; it is not lossless migration and it sacrifices availability. N5 is closed for preventing unsafe legacy-pending completion, not for preserving every recoverable old result.

### N7: operators are not told that evidence was discarded

Observation: production search for `legacy_pending_discarded` finds only its initialization, reset, and assignment in the local reducer. No logging, event, health/CLI surfacing, or durable snapshot field consumes it. Both side-effect fixtures show `counter_in_snapshot=false`, and the next current-format snapshot/restore resets the counter from **2 to 0**. It is inspectable programmatically during the current reducer lifetime, but not surfaced through an operator interface in the inspected production paths.

Inference: an operator can see unresolved incidents without a durable explanation that upgrade discarded completion evidence. Add a persisted migration diagnostic and operator-visible warning with count/affected plans and fresh-evidence recovery instructions. Evidence: `expanded-results.json` → `discard_side_effects`, `operator-visibility-search.txt`, and snapshot implementation. This low-severity diagnostic issue alone does not negate N5 safety closure.

## Prior regressions and original harnesses

| Harness | True exit | Result |
|---|---:|---|
| adversarial.py | 1 | Historical expected-bug assertion fails at first N3 check; expected for fixed code. |
| adversarial-inverted.py | 0 | All three corrected terminal-pair checks pass. |
| new_cases.py | 0 | **398/398** = 14 named + 384 permutations/address assignments. |
| supplementary.py | 0 | **4/4**, completing **402/402** original schedules. |
| probes.py | 0 | **14/14** earlier scoped regression groups. |
| older-regressions.py | 0 | **2/2** rooted-store/all-mutator and H2 groups. |
| independent.py | 0 | N1/N2, pending/progress snapshots, public repair, production attachment checks pass. |

`independent.json` records public success calls `[0,1]`, verified `[true,true]`, outcome `resolved`, local/hive open 0 and health `healthy`; failure calls `[0,1]`, verified `[true,false]`, outcome `rolled_back`, local/hive open 1 and health `failed`. This is real Appliance/planner/verifier/LocalAgentAdapter integration with a receipt-producing executor double, not arbitrary live host execution. No historical unused functions in the scripts were treated as executed coverage.

## Modified-test assessment

The changed `test_astra7024.py::test_legacy_bucketed_pending_snapshot_restores` is a **legitimate explicit contract change**, not merely deletion of the closure assertion. It now asserts discard count 2, open incident after PLAN, then adds two fresh receipts and retains the final closed assertion. It intentionally abandons lossless legacy restore even for this unambiguous example. Its new expectation matches the information-loss impossibility result and the conservative implementation; it should be accompanied by migration/operator documentation.

All **nine** `test_astra7075.py` tests pass in the single full suite. Coverage includes mixed legacy fail-closed + fresh completion, legacy conflicting evidence examples, new-format round trip/tag, resolved dual-address rejection, new/old owner-field snapshot restoration, unlinked/open contradictions, buffered contradiction, and positive consistent dual-address / PLAN-before-INCIDENT behavior.

Limitations: the information-loss test uses two handcrafted bucket dictionaries, not two opposite event histories proven to serialize byte-identically; our unchanged independent witness supplies that proof. New tests mostly inspect final states and their helper does not assert local/hive agreement after every event. They do **not** test conflicting PLAN re-registration, incident-only receipt bypass after that re-registration, completion of a second incident with no new receipts, authentic ownerless old snapshot from PLAN-before-INCIDENT, or durable/operator-visible discard diagnostics. Their older-snapshot test removes the owner field only after links already exist, missing the reconstruction hole. Passing nine tests therefore supports the named repaired witnesses, not the broader first-owner claim.

## Full pytest — one invocation only

Command: `/usr/bin/python3 -m pytest tests/ -v -p no:cacheprovider --basetemp=.../20260928-astra-7133/pytest-tmp`.
Cwd: tracked-file export at `experiments/20260928-astra-7133/source`.

**665 collected; 664 passed, 1 failed in 64.16s. Actual child exit 1; timeout false; launcher wall time 64.797s.** See [stdout](../experiments/20260928-astra-7133/pytest.stdout), [stderr](../experiments/20260928-astra-7133/pytest.stderr), and [true exit record](../experiments/20260928-astra-7133/pytest-exit.json).

Only `tests/test_packaging.py::test_wheel_build` fails: isolated build cannot find `setuptools>=61` with `PIP_NO_INDEX=1`. The parent claim of 665 passes is not independently reproduced under this offline environment. No package dependency was provisioned, no packaging retry or second suite run was performed. The enclosing launcher returns 0 after recording child results; that **is not the pytest exit**. The isolated build attempted its normal dependency resolution and failed; this reviewer did not run a separate install command.

## Provenance and reproducibility

`run_review.py` exports only tracked files from the pinned worktree, copies the original seven 7024 harnesses, uses `HIVE_SRC` pointing to the pinned worktree, isolates build artifacts, records environment/versions/source hashes and every subprocess exit, and refuses a second full-suite invocation in this evidence directory. `run_semantic.py`, `run_legacy_information_loss.py`, `run_expanded.py`, and `run_followup.py` run the respective probes without overwriting prior exit evidence. For repetition, copy authored launchers/probes to a **fresh sibling evidence directory** and use the same pin. Baseline sources are exact `git show e6afe16:...` exports.

Original-harness scripts and the two 7075 semantic scripts are hash-verified against their copied sources. `original-reruns-verification.json` records an empty pinned-worktree git status and unchanged source/original harnesses; final integrity evidence independently repeats the checks. `commit.diff`, `modified-tests.diff`, `copy-provenance.json`, `source-sha256.json`, `environment.json`, `review-env-overrides.json`, and `SHA256SUMS` preserve provenance. Python socket guard and offline variables constrain these experiments but are not an OS sandbox. Finite ordering sweeps are exhaustive over their stated sets; this is not coverage of arbitrary events, hostile snapshots, transport attacks, or real host repair.

## Prioritized remaining fixes

1. **N6:** Reject conflicting PLAN identity atomically before linking incidents or replaying pending receipts; enforce the immutable owner in all completion paths and after effective plan inference for incident-only receipts. Add before/after-completion and snapshot regressions.
2. **N6 legacy ownership:** Fail closed when old snapshots lack sufficient owner evidence; recover authoritative PLAN identity and revalidate progress rather than accepting contradictory evidence before later PLAN replay. Add the authentic PLAN-before-INCIDENT witness.
3. **N7:** Persist and surface discard diagnostics; document that all bucketed pending evidence is retired, including unambiguous subsets, and that fresh uniquely identified receipts are required.
4. Re-run these concrete failing witnesses after fixes, then re-evaluate the gated live-repair readiness decision. Obtain a separately dependency-provisioned packaging result if release packaging is in scope; do not relabel this suite as 665 passes.
