# Astra Re-review 7160 — ef18db3

Model (self-reported): GPT-6 (Codex; Astra reviewer role).
Routing verification: the parent verifies the gateway session record; self-identification is not independent routing evidence.
Date: 2026-09-28. Pin: `ef18db3` (full hash in evidence `environment.json`).
Worktree: `/home/openclaw/research-agent/projects/hive-appliance/repos/hive-astra-7160`.
Evidence: [20260928-astra-7160](../experiments/20260928-astra-7160/).
Compared with 7146 at `8bbd10b`, both 7133 reviews, and their reconciliation. No production edits, pushes, dependency installs, or live host repair commands.

## Verdict

**I would lift the current-format live-repair gate at this pin, on the bounded safety evidence below. I would not lift an unrestricted legacy recovery/rebind gate.** The demonstrated N8 premature-HEALTHY failure and both N5 stale-progress fixtures are repaired; conflicting PLANs now leave public state unchanged except the intended rejection counter; ordinary PLANs no longer replace lost historical owners. No new event-driven incident closure without verified evidence was found.

This is not approval for automatic legacy recovery or exposing `rebind_plan_owner` to untrusted callers. Rebind is a trusted in-process authority override, not authentication of lost history: it can assign a quarantined plan to an unrelated unlinked incident, and held post-migration plan-only successes can then close that incident. Its caller must supply the missing authority. There is no production caller/integration in this pin. The remaining late-INCIDENT liveness defect, diagnostic retention growth, and multi-plan supersession contract deserve fixes, but the tested current-format live paths did not produce unsafe success.

**Full pytest exactly once: 682 collected, 681 passed, 1 failed, true exit 1.** The failure is isolated offline wheel-build provisioning (`setuptools>=61` unavailable with `PIP_NO_INDEX=1`), not a reducer assertion. The claimed 682 passes were not reproduced in this environment. All eight new tests passed.

## Finding ratings

CLOSED is limited to the named safety defect and tested contract, not whole-subsystem certification. N8 is the other 7133 review's finding named N7; N7 here means migration diagnostics.

| ID | Status | Observation / qualification |
|---|---|---|
| A1 | CLOSED, retained | SQLite competing lease/stale-worker probe passes. |
| A2 | CLOSED, retained | Active partial retained; orphan partial removed. |
| H1 | CLOSED, retained | Poll cannot mask unresolved critical incident; public repair outcomes correct. |
| H2 | PARTIAL | Targeted/index/dedup and N5/N8 safety now pass; late INCIDENT after all successes still waits for another trigger. |
| U1 | CLOSED, retained | Checkpoint create/readback failures prevent dispatch; rollback failure audit retained. |
| U2 | CLOSED, retained | Bounded shell rollback, order, metadata, flags and CLI probes pass. |
| U3 | CLOSED for original scope | Incident identity, composite progress and current round trips pass; legacy needs explicit authority. |
| L1 | CLOSED, retained | Timeout/stop ownership and eventual normal restart pass. |
| S1 | CLOSED, retained | Invalid status/direct-SQL terminal transitions rejected. |
| P1-symlink | CLOSED, retained | Main/thumbnail symlink and outside-creation controls pass. |
| P2-store | CLOSED, retained | Production-root wiring, canonicalization and all mutator boundary controls pass. |
| N1 | CLOSED, retained | Actual Appliance repair success HEALTHY/0; failure FAILED/1, rolled_back. |
| N2 | CLOSED, retained | Distinct index, retry, duplicate, invalid-index and legacy-boolean controls pass. |
| N3 | CLOSED for original scope | Whole-buffer-before-completion corrected terminal pairs pass. |
| N4 | CLOSED for original scope | Original timing witness and repeated snapshot boundaries pass. |
| N5 | CLOSED, safety | Linked and unlinked authentic stale-progress disk witnesses cannot close with stale step 0; fresh recovery works with required explicit rebind when owner lost. |
| N6(a) | CLOSED | Full public local/hive state unchanged on conflicting PLAN except each rejection counter increments once. |
| N6(b) | CLOSED under explicit-authority contract | 6/6 authentic historical-owner cases safe; ordinary PLAN cannot rebind. Historical owner cannot be inferred from information-losing snapshots. Manual override remains a trust boundary, below. |
| N7 | CLOSED for loss/visibility defect | Diagnostics durable, cumulative and logged. Not globally bounded; N10 below. |
| N8 | CLOSED for reported safety defect | 14/14 additional schedules remain open with newer failure; fresh retry can complete; post-closure PLAN does not reinstate the old exploit. |
| N9, rebind hardening | OPEN, trust-boundary limitation | Accepts resolved targets and unrelated unlinked targets; no actor/reason/authentication parameter. No unauthenticated event path to this method found. |
| N10, retention | OPEN, scalability limitation | Candidate values capped at eight per plan, but plan keys, ownerless history and rebind history have no global cap. |

Original eleven: ten scoped CLOSED, H2 PARTIAL. N9/N10 are limitations exposed/confirmed by this review, not demonstrated high-severity remote exploits.

## Direct safety evidence

### N8: both failure placements, every boundary, replay and retry

The unsafe sequence from 7146 is now safe:

```text
PLAN p -> i (2)
p/0 verified
incident-only i/0 failed
INCIDENT i
p/1 verified
```

Moving the failure after INCIDENT is also safe. `boundary-and-disk.json` has **14 schedules = two placements × (live, pre-stream restore, five post-event boundaries)**. Each selected local snapshot boundary is JSON-restored twice. **14/14 safety passes and 14/14 local/hive agreement after every event** (open IDs, verified sets, failed sets). Both retain the failed index; the prior unsafe HEALTHY/0 state is absent. Hive has no snapshot API; none was invented.

`focused-witnesses.json` separately retains the post-closure PLAN oracle, pre-success PLAN drain and fresh step-0 retry. Current rows are **13/14**, with only `late_incident_after_completion_liveness` failing. These overlap the 14 boundary schedules and are not additional independent successes. Current rows carry the inherited label `623c92b`; imports actually use ef18db3 via HIVE_SRC. Baseline labels remain real old code.

### N5: real e6afe16 producer and CheckpointManager, linked and unlinked

The old producer records applied p/0 success, a newer buffered incident-only i/0 failure, and then INCIDENT i. In the linked variant that INCIDENT explicitly has `plan_id=p`. Old disk checkpoints are created/read with real CheckpointManager; the linked fixture reconstructs ownership without quarantine.

Observed linked restore now removes stale step 0 and records `legacy_verified_invalidated=1`. PLAN plus fresh p/1 leaves i open. Fresh p/0 then closes it. The unchanged `boundary_and_disk.py` old-loader control also keeps i open before fresh p/0.

The unlinked fixture stays quarantined. Ordinary PLAN and two fresh receipts alone no longer recover it, intentionally. The unchanged three old stale-progress tests report **0/3 composite passes**, because they require automatic PLAN-based recovery; **all three pass the direct no-stale-closure safety oracle**. After explicit legitimate rebind, recovery succeeds.

`mechanism-probes.json` / `mechanism-checkpoints/` contain **6/6 complete safety-and-recovery passes**: linked/unlinked × direct/current-restored-twice/legacy-restored-twice. Unlinked cases use the explicit rebind; linked cases do not. All require fresh p/0 before closure. Each final disk variant has its own directory. An initial probe run reused CheckpointManager's same-second ID in one directory; its observations are preserved as `mechanism-probes-first.json`, but the final isolated disk fixtures are the review artifacts.

Both independent **384-case legacy fail-closed + fresh recovery sweeps pass 384/384**, with no premature completion. Those matrices overlap; do not add them into 768 independent schedules. These cases generally register the plan after restoring buffered receipts, so do not replace the explicit ownerless-plan rebind fixtures.

### N6(a): literal public-state rejection tested

`mechanism-probes.json.rejected_full_state` saves complete before/after local and hive dictionaries: component state, agent/global timestamps, all plan/progress/owner/link/seen-ID structures, pending buckets and counters. The stream includes an unresolved pending receipt and the rejected PLAN has `subject='svc'`.

**Only `rejected_plan_registrations` changes**, once in each reducer. No component merge, timestamp change, drain, relink or step mutation occurs. The earlier `new-risks.json` independent comparison agrees. The phrase “ANY mutation” should be understood to exclude the intentional audit counter, as the new test explicitly does.

### N6(b): authentic historical cases and explicit rebind

B's authentic `e6afe16` and `5de0d53` producers each exercise missing owner, ambiguous links and recoverable resolved links: **6/6 pass**, versus 4/6 previously. The two historically wrong ordinary PLAN registrations now remain quarantined and do not close the replacement incident. `corrected-old-owner-traces.json` provides immutable intermediate owner maps; the older semantic recorder holds map references in intermediate traces, so use its final oracles, not those references, for ownership timing.

The authentic opposite-history snapshots still demonstrate information loss. No algorithm here recovers unavailable ownership history. The explicit method makes that authority change deliberate rather than accepting a later ordinary PLAN.

## New-mechanism probes and remaining risks

### Pending-block liveness and fresh-evidence recovery

Six live controls in `mechanism-probes.json.pending_liveness` compare open IDs, verified/failed sets, displayed count and health at every event:

- Invalid-index pending evidence is consumed without credit and does not permanently block legitimate fresh successes.
- Unknown unrelated plan pending evidence does not block p.
- Contradictory dual-address evidence is rejected and does not block p.
- Another agent's pending p/i failure does not block agent a's p/i completion.
- Two plans owning one not-yet-linked incident leave an incident-only failure ambiguous and conservatively block completion; same-owner PLAN selects linkage, drains the failure, and fresh retry recovers.
- A late INCIDENT after all plan successes remains open until another PLAN/receipt trigger; same-owner PLAN recovers. This conservative liveness defect predates the new fix.

All six have per-event agreement. Four immediately legitimate unambiguous cases complete; the two conservative cases recover after the explicit trigger/retry suffix. **No permanent deadlock of these legitimate plans was observed.** This is finite coverage, not a proof for arbitrary malformed snapshots. In particular, the three unchanged `new_risks.py` quarantine-recovery controls now fail their old ordinary-PLAN recovery expectation; they are not evidence of irrecoverability because explicit rebind succeeds.

### Rebind's actual authority boundary (N9)

Eight cases test outside quarantine, missing incident, incident linked to a foreign plan, resolved incident, unrelated unlinked incident, duplicate call, held successes and held newer failure. Observations:

- Outside quarantine: false. Missing target: false. Foreign nonempty link: false.
- After a successful rebind, a second rebind is false. A failed first call does not consume the right to make a valid call later.
- A quarantined plan **can** bind to a resolved incident. This adds an audit record but does not reopen it or close a different incident in the tested case.
- A quarantined plan **can** bind to an unrelated unlinked incident; candidate-list membership and historical identity are not checked.
- No evidence: rebind alone closes nothing. Held post-migration successes: rebind drains and may immediately close its selected owner. Held newer failure prevents that completion.
- JSON snapshot/restore twice preserves every tested resulting state, including quarantine, candidates and audit.

A separate real-completion probe (`resolved-plan-probe.json`) first completes p with the authentic old reducer. A uniquely linked resolved plan reconstructs its owner and rejects rebind (not quarantined). Adding a second authentic legacy incident link makes ownership ambiguous; restore quarantines p, drops its old successes, and permits rebind to the already-resolved original incident. It does not close the other open incident. Thus the actual guard is quarantine, not completed-plan lifecycle status.

`rebind-authority.json` demonstrates the exact abuse boundary with authentic old producer: historical PLAN p->historical loses its owner; two **fresh post-migration plan-only successes** are held; explicit `rebind_plan_owner('p','unrelated')` closes unrelated and leaves historical open. Without those fresh successes, both stay open. Twenty current restores retain one audit entry without multiplication.

**Interpretation:** this is possible misuse by a trusted operator/caller, not an event-driven bypass or closure with no verified receipt. The method explicitly declares itself operator-authoritative, and repository search found no production caller outside its definition. Before wiring it into an API/CLI, require an authorized operator, identify the source of ownership evidence, record actor/reason, reject resolved targets unless deliberately supported, and show held evidence before applying it. It cannot establish physical applicability of plan-only evidence to a newly chosen unrelated incident.

### Bounds and diagnostics (N10)

Observed: 32 distinct candidate proposals retain eight for one plan; candidate state survives restore. Across 128 quarantined plans, 128 candidate-map keys and then 128 rebind records persist. All 128 incidents stay open without receipts. The unchanged size probe retains 2,048 ownerless IDs. Thus **per-plan candidate values are bounded, global histories are not**. Owner candidates are removed after rebind, but historical ownerless IDs remain. Repeated restores do not multiply entries. Rebind warnings are present in saved stderr.

The migration `recovery` text now correctly requires explicit rebind. One older warning/comment still says “until a PLAN re-establishes the owner”; that is stale guidance, not actual behavior.

## Exact rerun accounting

Harness exit codes are recorded independently; launcher exit zero does not mean its children passed. Overlapping matrices must not be summed.

| Harness / group | Exact result | Interpretation |
|---|---|---|
| Original expected-bug `adversarial.py` | exit 1 | Stops at first repaired historical N3 bug expectation. |
| `adversarial-inverted.py` | 3 corrected terminal pairs pass; exit 0 | Retained N3 controls. |
| `new_cases.py` | **397/398**, including **384/384** permutations; exit 1 | `two_plans_one_incident_failure` changed outcome. |
| `supplementary.py` | **3/4**; exit 1 | `prelinked_incident_only_different_plan_incident` old unsafe expectation rejected. |
| Original 7024 total | **400/402** | Same two explained differences as 7146. |
| `probes.py` | **14/14 groups**, exit 0 | A1–S1 and P1/P2 scoped regressions. |
| `older-regressions.py` | **2/2 groups**, exit 0 | Rooted mutators and prior H2 residual. |
| `independent.py` | All retained controls pass, exit 0 | N1/N2, snapshots, real public repair, rooted production wiring. |
| A original current sweep | **1,920/1,920** | Five boundaries. |
| A old exact-equivalence sweep | **0/384**; 0 premature closures; 96 old false-noncompletion labels | Obsolete lossless-migration oracle, not 384 safety failures. |
| A original lifecycle | **11/13** | Failing names `resolved_identity_baseline`, `unlinked_identity_baseline`; authentic old controls. |
| A information-loss script | exit 1 | Same-byte histories retained; obsolete restored-success expectation. |
| A expanded lifecycle | **16/18** | Failures only `resolved_baseline`, `unlinked_baseline`; **16/16 current agreement**. |
| A expanded fail-closed + fresh | **384/384**, 0 premature closures | Expanded script exits 0 despite intentionally failing old controls. |
| A followup | exit 0 | Observation harness, not a universal assertion. |
| B current arrival-v1 | **3,072/3,072** | Eight boundaries; contains 1,920 subset. |
| B authentic 5de0d53 ordered format | **3,072/3,072** | Same finite schedule set. |
| B authentic e6afe16 fail-closed + fresh | **384/384** | Direct safety and fresh recovery. |
| B opposite-history disk witnesses | **2/2** | Conservative retirement of ambiguous evidence. |
| B old unlinked stale disk composite oracle | **0/3** | Safety passes 3/3; old automatic-recovery requirement fails. |
| B lifecycle | **47/48** | Only `late_incident_after_completed_plan`. |
| B authentic old ownership | **6/6** | Both prior missing-owner counterexamples now safe. |
| B agent namespace | **1/1** | Same IDs remain agent-isolated. |
| Focused current | **13/14** | Only late-INCIDENT-after-completion liveness. |
| Focused e6afe16 / 5de0d53 | **3/6 each** | Each fails rebound and both old late-event liveness cases. Total focused **19/26**. |
| Additional N8 boundaries | **14/14 safety; 14/14 agreement** | Both failure placements, live/pre-stream/all post-event boundaries. |
| Authentic disk fixtures with explicit recovery | **6/6** | Linked and unlinked × three restore modes. |
| New pending/liveness controls | **6/6 per-event agreement; all recover** | Direct observations as above. |

The focused harness initially failed before executing cases because copied old hive modules collided with its exclusive-create operation. That failed attempt is preserved (`focused_witnesses.stderr`, exit 1). Copied modules were renamed with `.copied`; the unchanged harness then generated authentic modules and ran (`focused-retry-*`). This was not a pytest rerun.

**Every original 7024 mismatch:**

1. `two_plans_one_incident_failure`: q->i has a failed step; complete later p->i closes i. Both plans own i, and code permits a complete owner-authorized retry plan to supersede the forward link. This is completion backed by p's full verified evidence, not N8-style pending failure on p. Original oracle wants q retried. Document the intended supersession contract before retiring this assertion.
2. `prelinked_incident_only_different_plan_incident`: prelinked i->p but PLAN p->other; old oracle wanted both incidents closed. New owner-only admission correctly leaves them open. This is a legitimate safety correction.

`agreement-audit.json`: original **402 schedules / 2,426 event states**, and B lifecycle **48 / 276**, have **zero open-ID/step-set agreement failures and zero recorded health contradictions**. This is supplementary to direct expected outcomes, not a substitute. The synthetic A `old_snapshot_plan_before_incident` now benefits from new current linking before dropping its owner field; do not mistake its pass for an authentic ownerless legacy case. Those cases are separately exercised with real old producers above.

## End-to-end and prior regressions

`independent.json` runs actual Appliance, planner/verifier, HiveAppliance and LocalAgentAdapter paths with a receipt-producing executor double. Success executes indices `[0,1]`, receipts `[true,true]`, outcome `resolved`, local/hive open **0**, **HEALTHY**. Failure receipts `[true,false]`, outcome `rolled_back`, local/hive open **1**, **FAILED** after ticks. No arbitrary host repair command was executed. Bounded shell rollback tests use temporary files.

A1, A2, H1/H2, U1, U2 metadata/shell/CLI, U3, L1 timeout and normal lifecycle, S1, P1 and P2 effect boundary all pass. Rooted-store mutators reject outside paths, symlink escapes and invalid finalization while preserving valid inside updates. N1–N4 retained controls and both current-format sweeps pass their original scoped safety oracles.

## Assessment of changed tests

`modified-tests.diff` shows eight additions in `tests/test_astra7146.py` and the explicit-rebind change to 7133. The additions are legitimate regressions, not weakened old assertions: both N8 placements, retry, six local cut positions with double restore, linked legacy invalidation, full-state rejection, ordinary PLAN non-rebind and persisted explicit rebind are covered.

The 7133 change is a legitimate stricter contract: ordinary PLAN must leave progress quarantined, explicit rebind is asserted, then valid held/fresh evidence recovers while foreign evidence is rejected. Its synthetic fixture now blanks current-generated incident links to emulate the old producer, because current late INCIDENT links automatically. This makes the intended fixture possible but does not replace testing authentic serialized legacy inputs; this review does that.

**The `both()` helper still compares only open incident IDs after each event. It has not been upgraded to compare step sets or health.** A few individual final assertions inspect local failures or hive count, but not full per-event agreement. Snapshot-boundary N8 test is local-only and covers one placement; copied external probes cover both placements and hive agreement. The linked migration fixture is synthetic, not an old producer plus CheckpointManager. Rebind tests omit resolved targets, foreign unlinked authority transfer, global bounds, and stale pending from another agent. Thus eight passes are useful but do not alone cover both reviews' full witnesses.

## Full pytest, once

Command and actual exit are in [pytest-exit.json](../experiments/20260928-astra-7160/pytest-exit.json); [stdout](../experiments/20260928-astra-7160/pytest.stdout) and [stderr](../experiments/20260928-astra-7160/pytest.stderr) are preserved.

```text
/usr/bin/python3 -m pytest tests/ -v -p no:cacheprovider \
  --basetemp=.../20260928-astra-7160/pytest-tmp
cwd: .../20260928-astra-7160/source (tracked export of ef18db3)
682 collected; 681 passed, 1 failed in 47.18s
actual child exit 1; timed_out false; wall 47.658s
```

Only `tests/test_packaging.py::test_wheel_build` fails: build isolation cannot provision setuptools>=61 in the offline environment (wheel is also listed as a build requirement). No dependencies were installed by this review, no packaging retry was made, and pytest was not invoked a second time.

## Prioritized follow-ups

1. Before enabling legacy rebind operationally: define and enforce trusted operator authority, preview affected owner/held evidence, record actor/reason, decide resolved-target policy, and supply a deliberate recovery workflow. Do not expose this method as an ordinary event or unauthenticated endpoint.
2. Document multi-plan supersession and turn its chosen safety policy into explicit tests. Fix late-INCIDENT-after-completion liveness by reconsidering already-complete owned plans after coherent drain.
3. Bound or summarize ownerless/rebind history and total candidate-map keys; retain actionable current quarantine separately from historical diagnostics. Correct the obsolete PLAN-recovery warning.
4. Promote real producer + disk linked/unlinked fixtures, both N8 placements at every boundary, per-event step/health agreement, explicit recovery, and namespace/pending controls into the maintained suite.
5. Re-run packaging in an already provisioned build environment as a separate release check. This report does not convert an offline provisioning failure into a passing suite.

## Reproducibility and limits

All copied helpers, authentic old reducers, command records, stdout/stderr, checkpoints, source export, diffs and hashes are in the evidence tree. `run_review.py` pins the full hash and uses exclusive pytest start/output files. `run_extra.py` runs copied semantic harnesses; `mechanism_probes.py`, `rebind_authority.py` and `audit_results.py` capture independent additions. `copy-provenance.json` records the 7146 originals; `7075-copy-provenance.json` records the runner's older helper sources. `final-integrity.json` verifies worktree/source hashes and clean status; `SHA256SUMS` covers final review evidence outside temporary/export trees. Use a fresh directory for repetition; do not rerun the exclusive suite launcher in this evidence directory.

HIVE_SRC points to the pinned worktree; pytest uses its tracked export. Python/pytest and offline overrides are recorded. The inherited Python socket guard is not an OS sandbox. Results are finite ordered schedules, not a transport/concurrency proof or general assurance about corrupt/untrusted snapshots. No hive restore API, physical repair verification or identity authentication beyond existing schemas was invented. The parent owns routing verification, integration and publication.
