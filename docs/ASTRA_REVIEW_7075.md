# Astra Review 7075

Date: 2026-09-28. Reviewed pin: `5de0d533a9070585c8c87129ba4c2598e3b7ac8b`.
Production repair: `d6ab556`; inspected delta: `e6afe16..5de0d53`.
Worktree: `projects/hive-appliance/repos/hive-astra-7075`.
Selected model: `gpt-6-astra`; parent reports session_status `openai/gpt-6-astra`.
That routing statement is parent-provided provenance, not a separate runtime measurement by this reviewer.

## Findings First

### 1. N5 remains PARTIAL: legacy pending snapshots can manufacture completion (High)

**Current in-memory ordering is repaired, but legacy migration is not fail-closed.**
[controller/reducer.py:283](https://github.com/bgoertzel-sing/hive-appliance/blob/5de0d533a9070585c8c87129ba4c2598e3b7ac8b/controller/reducer.py#L283)
flattens old plan/incident buckets in bucket order. This cannot recover the original
interleaving. The migrated receipts subsequently overwrite step results in that
invented order at [controller/reducer.py:199](https://github.com/bgoertzel-sing/hive-appliance/blob/5de0d533a9070585c8c87129ba4c2598e3b7ac8b/controller/reducer.py#L199).

**Executable witness, produced by the real `e6afe16` Reducer, persisted and loaded
through the real CheckpointManager, then restored into the reviewed Reducer:**

```text
INCIDENT i, unlinked
seed1:       plan p,     step 1, verified true
old_success: incident i, step 0, verified true
new_failure: plan p,     step 0, verified false
legacy snapshot -> disk checkpoint -> current restore
PLAN p: incident i, two steps
```

The old snapshot contains the p bucket `[seed1, new_failure]` followed by the
incident bucket `[old_success]`. Restore accepts it and replays precisely that
order. **Restored local: open=0, verified={0,1}, failed={}.** Uninterrupted current
local and hive both correctly retain **open=1, verified={1}, failed={0}**.
There was no retry after the failure. `Appliance.restore()` directly delegates
to this restore method at [controller/appliance.py:408](https://github.com/bgoertzel-sing/hive-appliance/blob/5de0d533a9070585c8c87129ba4c2598e3b7ac8b/controller/appliance.py#L408).
The probe used the real checkpoint manager plus direct Reducer restore, not a
live appliance upgrade or host repair.

**Independent sweep:** 384 authentic legacy snapshots, 288 reproduce the original
stream's semantic result and **96 do not**. Of the 96, **24 prematurely close**,
24 falsely remain open, and 48 retain the expected open count but wrong step
state. These are manifestations of one ordering/information-loss defect.
By contrast **1,920/1,920 new-format snapshot schedules pass**: all 384 receipt
permutations/address assignments, each restored at five prefix boundaries.

The follow-up `legacy_information_loss.py` constructs two streams with opposite
latest step-0 outcomes but **byte-identical legacy snapshot JSON**. The current
loader closes both. Thus a different bucket sort is not a general repair:
the information needed to select the correct outcome is absent.

**Required fix:** version the migration policy and fail closed for ambiguous
pending evidence, or recover authentic arrival order from a durable event log.
Do not claim lossless legacy ordering from bucket flattening. Require fresh
evidence when completion cannot be reconstructed safely.

Evidence: [semantic-summary.json](../experiments/20260928-astra-7075/semantic-summary.json),
[all legacy cases](../experiments/20260928-astra-7075/semantic-legacy-migrations.json),
[information-loss witness](../experiments/20260928-astra-7075/legacy-information-loss.json),
and [disk checkpoint](../experiments/20260928-astra-7075/legacy-checkpoint/).
The new migration adapter is in this delta; the underlying legacy ordering
defect was already known. This is not a claim that old production was safe.

### 2. N6 OPEN: receipt identity is not durable across incident lifecycle (Medium, pre-existing)

The local admission check searches only open incidents at
[controller/reducer.py:186](https://github.com/bgoertzel-sing/hive-appliance/blob/5de0d533a9070585c8c87129ba4c2598e3b7ac8b/controller/reducer.py#L186)
and [controller/reducer.py:210](https://github.com/bgoertzel-sing/hive-appliance/blob/5de0d533a9070585c8c87129ba4c2598e3b7ac8b/controller/reducer.py#L210).
Hive does the same at [hive/reducer.py:359](https://github.com/bgoertzel-sing/hive-appliance/blob/5de0d533a9070585c8c87129ba4c2598e3b7ac8b/hive/reducer.py#L359).
Both know step counts but do not retain an authoritative plan-to-incident owner
against which every dual-address receipt is checked.

**Resolved-target witness:** register `p -> i` (two steps) and `q -> other`
(one step); successfully complete q; submit valid p/0; then submit verified
`plan_id=p, incident_id=other, step_index=1`. Both reducers count the contradictory
receipt and close i; hive displays **HEALTHY/0**. The same receipt arriving while
other is still open is rejected. Restoring the local snapshot after q completes
does not change the unsafe result. A resolved incident still has its recorded
q linkage; resolution should not authorize its receipts to complete p.

**Unlinked-target variant:** with i and other open, register `p -> i`, submit
valid p/0, then verified `p/1` naming `incident_id=other`, which has no plan.
Local closes i and leaves other open; hive closes **both**. The extra hive
resolution comes from [hive/reducer.py:398](https://github.com/bgoertzel-sing/hive-appliance/blob/5de0d533a9070585c8c87129ba4c2598e3b7ac8b/hive/reducer.py#L398),
which allows receipt identity to resolve an unlinked incident as well as the
plan-linked incident. Even under a policy that lets the plan identity take
precedence, resolving unrelated other is not supported by PLAN p's target.

**Provenance and scope:** both examples also reproduce with the `e6afe16` local
Reducer and the unchanged hive/schema implementation. These are **pre-existing
limitations, not newly introduced production regressions**. The local docstring
explicitly promises rejection for an *open* contradictory target, and the
original N4 timing schedule is now fixed. N6 identifies why that narrower
contract cannot justify broad targeted-completion safety; it is not a claim
that the documented open-only check fails its own stated condition.
Severity remains Medium because these are adversarial Event payloads; no real
transport injection or external damage was demonstrated.

**Required fix:** retain and enforce plan ownership independently of open/closed
incident state; specify dual-address admission and refuse contradictory or
unsupported fallback targets before recording step progress.

Evidence: [semantic-lifecycle.json](../experiments/20260928-astra-7075/semantic-lifecycle.json),
cases `resolved_identity_current`, `resolved_identity_snapshot`,
`resolved_identity_baseline`, `unlinked_identity_current`, and
`unlinked_identity_baseline`; `open_identity_control` passes.

## Verdict And Statuses

**Keep the gated live-repair/replay readiness restriction.** The original
402-schedule repair claim is independently reproduced, and bounded closure of
the named N4 timing defect is justified. N5 cannot be closed across supported
legacy restore, and H2 cannot be closed on reducer agreement alone.
No whole-codebase readiness or cleanliness claim follows from this review.

| ID | Status at 5de0d53 | Bounded evidence |
|---|---|---|
| A1 | CLOSED, retained | Stale-worker and concurrent SQLite claim regression passes. |
| A2 | CLOSED, retained | Live partial preserved; orphan partial removed. |
| H1 | CLOSED, retained | Polling preserves genuine unresolved critical incidents; normal completed repair remains healthy. |
| H2 | PARTIAL | Original buffered/index/dedup cases pass; unsafe legacy completion and lifecycle identity cases remain. |
| U1 | CLOSED, retained | Checkpoint create/readback failure blocks dispatch; rollback failures remain recorded. |
| U2 | CLOSED, retained | Bounded real-shell rollback, order, honest flags, metadata and CLI probes pass. |
| U3 | CLOSED for prior named defect | Incident/dedup/composite and current-format snapshots pass; this does not certify the N5 legacy migration. |
| L1 | CLOSED, retained | Worker timeout/stop ownership and eventual restart probes pass. |
| S1 | CLOSED, retained | Terminal state and invalid direct-SQL state checks pass. |
| P1-symlink | CLOSED, retained | Main/thumbnail planted symlinks rejected without outside creation. |
| P2-store | CLOSED, retained | Rooted production wiring, canonical admission, all mutators and outside-sentinel checks pass. |
| N1 | CLOSED, retained | Real public repair: success HEALTHY/0; failed second step FAILED/1. |
| N2 | CLOSED, retained | Distinct valid indices, dedup, retry and legacy boolean rejection pass. |
| N3 | CLOSED, retained | Buffered successes followed by failure stay open until fresh retry. |
| N4 | CLOSED for named 7003/7024 defects | Contradiction timing schedule now rejects in both reducers; all seven local snapshot boundary variants pass. Broader identity limitation is N6. |
| N5 | PARTIAL | Live and new-format ordering repaired; authentic legacy restore still unsafe. |
| N6 | OPEN, new review finding | Resolved/unlinked identity examples above; pre-existing at baseline. |

Original eleven IDs: ten bounded CLOSED, H2 PARTIAL. These statuses preserve
earlier finding scope; they do not certify every recovery or identity behavior.

## Original Harness Reruns

Read prior reports 7024, 7003 and 6986 and their evidence semantics. Copied the
seven published original scripts from the pinned worktree into this new evidence
directory, unchanged. Their published change from the original workspace scripts
is the import-root expression supporting `HIVE_SRC`; provenance and exact path
adaptation diffs are retained. `HIVE_SRC` points to the pinned worktree. Required
`tmp/` directories were created. No tracked original evidence was overwritten.

| Harness | Actual exit | Result |
|---|---:|---|
| adversarial.py | 1 | Expected old-bug assertion fails at the first N3 check; later checks are not reached. Not a product regression. |
| adversarial-inverted.py | 0 | All three corrected expectations pass: terminal pairs 1/1, 0/0, 2/2. |
| new_cases.py | 0 | **398/398:** 14 named cases plus 384 systematic permutations/address assignments. |
| supplementary.py | 0 | **4/4:** lifecycle/prelink schedules. |
| probes.py | 0 | 14/14 earlier scoped regression groups. |
| older-regressions.py | 0 | 2/2 rooted-store/all-mutator and prior H2 groups. |
| independent.py | 0 | Prior N1/N2, pending/progress snapshots, public repair and production attachment wiring checks pass. |

**Count reconciliation: 14 + 384 = 398; 398 + 4 = 402.** The inverted three
checks, other regression groups and new independent probes are separate, not
additions hidden inside that 402. The 7024 result was 229 pass/173 fail across
these same 402 schedules; here it is **402 pass/0 fail**.

Public repair uses real Appliance, planner, verifier and LocalAgentAdapter,
but a receipt-producing executor double rather than host commands. Success
executes [0,1], verifies [true,true], resolves locally and displays HEALTHY/0;
failure verifies [true,false], returns rolled_back, and remains FAILED/1 after
two hive ticks. Historical unused functions in copied probes were not executed.

## Independent Probes And Changed Tests

`semantic_probes.py` uses a direct latest-evidence oracle for expected verified
and failed indices, not one reducer as the reference for the other. Results:

- New-format snapshots: **1,920/1,920** pass, including sorted-key JSON serialization.
- Actual legacy-producer snapshots: **288/384** match; 96 semantic failures as above.
- Lifecycle: **8/13** pass; five failures include baseline and snapshot repetitions
  of the two N6 identity variants, not five distinct defects.
- Whole semantic harness: **exit 1**, no timeout; failures retained in JSON.
- Separate information-loss witness: **exit 1** for the unsafe migration result;
  explicit assertions confirm identical old snapshots and correct uninterrupted results.

The initial optional identical-snapshot comparison was false because a missing
incident payload timestamp was regenerated on each reduction. Its original
output is retained. `legacy_information_loss.py` fixes the incident timestamp
explicitly in a separate run, proving byte identity. No production behavior or
earlier results were edited to obtain this proof.

The production delta touches **only controller/reducer.py**. `tests/test_astra7024.py`
is additive: six functions, eight collected cases after parametrization. No
older test is weakened or removed. All eight pass in the full suite. The
384-case test does include explicit latest-wins expectations as well as
local/hive agreement; that is substantive positive coverage. However the
legacy test at [tests/test_astra7024.py:154](https://github.com/bgoertzel-sing/hive-appliance/blob/5de0d533a9070585c8c87129ba4c2598e3b7ac8b/tests/test_astra7024.py#L154)
contains only two successful receipts for different indices. It cannot expose
cross-bucket conflicting outcomes and is local-only, despite the file header's
claim that every stream runs through both reducers. The newly published
rebuild harness was inspected but not substituted for the original scripts.

## Full Suite And Packaging

**Full pytest invoked exactly once by this reviewer**, on a tracked-source copy
under this evidence directory to contain build outputs:

```text
/usr/bin/python3 -m pytest tests/ -v -p no:cacheprovider \
  --basetemp=/home/openclaw/research-agent/projects/hive-appliance/experiments/20260928-astra-7075/pytest-tmp
cwd: .../experiments/20260928-astra-7075/source
655 passed, 1 failed, 656 collected; 41.92s pytest duration
actual child exit: 1; timeout: false; launcher wall time: 42.50s
```

Only `tests/test_packaging.py::test_wheel_build` fails: isolated pip cannot
obtain `setuptools>=61` with `PIP_NO_INDEX=1`. This is an observed offline
build-dependency provisioning failure, not a reducer assertion regression.
No dependency installation or packaging-specific retry was performed here.
The runner exits zero after recording child statuses; its exit is **not** the
pytest exit. See [pytest-exit.json](../experiments/20260928-astra-7075/pytest-exit.json)
and [pytest.stdout](../experiments/20260928-astra-7075/pytest.stdout).

**Separate parent-verified packaging evidence: PASS.** Read
[parent results.json](../experiments/20260928-astra-7075-packaging/results.json):
dependency-provisioned isolated wheel build, fresh venv creation, offline
`--no-index --no-deps` wheel install, isolated installed imports of cli,
controller.appliance, hive, conversation.client and recovery, and installed
CLI `--help` all exit 0. Parent ran these, not this reviewer. This resolves the
bounded packaging smoke question without rewriting the independent offline
suite result as 656 passes.

## Reproduction, Integrity And Limits

Evidence: [20260928-astra-7075](../experiments/20260928-astra-7075/).
`run_review.py` creates the source export, copies the original harnesses, sets
`HIVE_SRC`, records versions/env overrides, and saves each real subprocess exit.
It refuses to overwrite a prior full-suite run. For a new complete rerun, copy
the authored launchers and independent probe files into a fresh sibling evidence directory at the same
depth, leaving the pinned worktree unchanged; the historical 7024 guard input
must remain available. Run `run_review.py`, `run_semantic.py`, then
`run_legacy_information_loss.py` with `/usr/bin/python3`. Individual original
scripts can also be copied into a fresh directory, given a `tmp/` child, and
run with `HIVE_SRC` set to the pinned worktree. Their exit/output semantics are
documented above. Expected failing probes intentionally exit nonzero.

`environment.json`, `review-env-overrides.json`, `source-sha256.json`,
`copy-provenance.json`, `original-harness-path-adaptations.diff`, `verification.json`
and `SHA256SUMS` record provenance and integrity. Python 3.10.12; pytest 9.1.1;
no stochastic sampling or seed: ordering sweeps are exhaustive over the stated
finite cases. Legacy local source is exported verbatim from `git show
e6afe16:controller/reducer.py`; hive and schemas are unchanged across the delta,
so baseline claims here are bounded to those focused reducer probes.
The first evidence-verifier run incorrectly required one import-path edit even
for byte-identical supplementary.py; its exit 1 and correction are preserved in
verification-initial.json. The corrected verifier passes; no tests were rerun.

Applied research rules: 2 (explicit semantic invariants), 4 (independent review),
5 (pinned reproducibility), 7 (reducer and snapshot boundaries). Prior safety
gates are retained unless specifically closed above. No production source edits,
pushes, live service mutation or publication by this reviewer. The inherited
Python socket guard blocks external Python socket connections; it is not an
OS sandbox. No arbitrary hostile snapshots, every possible event ordering,
real transport adversary, host repair, global concurrency or whole-codebase
certification is claimed. Parent owns publication and final task integration.

**Next unresolved work:** make ambiguous legacy pending restoration fail closed;
enforce durable plan/incident identity, then requalify the concrete witnesses.
