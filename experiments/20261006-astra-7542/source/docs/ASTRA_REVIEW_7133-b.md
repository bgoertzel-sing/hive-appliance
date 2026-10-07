# Astra Review 7133

Date: 2026-09-28. Exact reviewed commit:
`623c92be3e2ab96fd76024881066628b6c73abb5`.
Inspected delta: `5de0d53..623c92b`; production changes are confined to
`controller/reducer.py` and `hive/reducer.py`.
Worktree: `projects/hive-appliance/repos/hive-astra-7133` (clean).
Selected model: **gpt-6-astra**, explicitly supplied by the requesting parent;
this is routing provenance, not a separate runtime measurement.

## Findings First

### 1. N5 PARTIAL: discarding pending failures leaves stale successes usable (High, new regression)

The loader restores verified indices at
[controller/reducer.py:298](https://github.com/bgoertzel-sing/hive-appliance/blob/623c92be3e2ab96fd76024881066628b6c73abb5/controller/reducer.py#L298),
then discards every legacy pending bucket at
[controller/reducer.py:309](https://github.com/bgoertzel-sing/hive-appliance/blob/623c92be3e2ab96fd76024881066628b6c73abb5/controller/reducer.py#L309)
without invalidating affected pre-existing step successes. A discarded *newer
failure* therefore exposes an older success as if it were sufficient evidence.

**Authentic `e6afe16` producer, actual CheckpointManager disk round-trip:**

```text
PLAN p -> i, two steps                 # INCIDENT i has not arrived
RECEIPT stale_success: p/0, true       # applied: verified={0}
RECEIPT later_failure: i/0, false      # incident-only, pending
INCIDENT i                            # still unlinked
legacy snapshot -> checkpoint -> 623c92b restore
PLAN p -> i, two steps                # links incident
RECEIPT fresh1: p/1, true              # no fresh step-0 success
```

The real old snapshot contains `plan_receipts={"p":[0]}` and a pending
`@inc:i` bucket holding the later failure. Restore reports
`legacy_pending_discarded=1`, but preserves verified step 0. After only fresh
step 1, **local closes i with verified={0,1}, failed={}**. The semantic oracle
requires i to remain open until affected step 0 is re-proven. It does **not**
require retaining the discarded failure or equality with uninterrupted history.

All three variants reproduce: direct restore, two new-format re-restores, and
repeated restore of the same old snapshot. A fresh success for step 0 permits
completion. Applying the same actual snapshot and suffix through both
`e6afe16` and `5de0d53` loaders leaves i open with verified={1}, failed={0}.
Thus this is a **new migration regression**, not merely the old ambiguous-order bug.

The original 7075 witness is fixed: both byte-identical old histories now stay
open with no credited progress, discard exactly three entries, and require two
fresh successes. All **384/384** old pre-PLAN permutation cases also safely
discard four entries and recover with fresh receipts. Those snapshots have no
already-applied progress, which is why they do not expose this regression.

**Required repair:** invalidate affected success evidence, or reject/quarantine
an ambiguous snapshot until authentic event replay or fresh evidence establishes
safe progress. Discarding only the pending containers is insufficient.

Evidence: [legacy-stale-progress.json](../experiments/20260928-astra-7133-b/legacy-stale-progress.json),
[focused baseline controls](../experiments/20260928-astra-7133-b/focused-witnesses.json)
(`stale_legacy_migration`),
[original witnesses](../experiments/20260928-astra-7133-b/legacy-original-witnesses.json),
and [actual checkpoints](../experiments/20260928-astra-7133-b/legacy-checkpoint/).
Appliance restore delegates to this loader at
[controller/appliance.py:408](https://github.com/bgoertzel-sing/hive-appliance/blob/623c92be3e2ab96fd76024881066628b6c73abb5/controller/appliance.py#L408);
the migration experiment used CheckpointManager plus Reducer, not a live upgrade.

### 2. N7 OPEN: owner fallback resolves before buffered failure is applied (High, new regression)

The newly added owner fallback at
[controller/reducer.py:243](https://github.com/bgoertzel-sing/hive-appliance/blob/623c92be3e2ab96fd76024881066628b6c73abb5/controller/reducer.py#L243)
and [hive/reducer.py:407](https://github.com/bgoertzel-sing/hive-appliance/blob/623c92be3e2ab96fd76024881066628b6c73abb5/hive/reducer.py#L407)
can close a late-arriving, unlinked incident without first applying its buffered
receipts. INCIDENT insertion does not establish the existing PLAN link or drain
pending evidence; incident-only admission consults that missing link at
[controller/reducer.py:201](https://github.com/bgoertzel-sing/hive-appliance/blob/623c92be3e2ab96fd76024881066628b6c73abb5/controller/reducer.py#L201)
and [hive/reducer.py:376](https://github.com/bgoertzel-sing/hive-appliance/blob/623c92be3e2ab96fd76024881066628b6c73abb5/hive/reducer.py#L376).

**No legacy snapshot is needed:**

```text
PLAN p -> i, two steps
RECEIPT p/0 true
RECEIPT i/0 false, incident-only
INCIDENT i
RECEIPT p/1 true
```

Both reducers close i, while the newer step-0 failure is **still pending**;
hive displays **HEALTHY/0**. Moving the failure after INCIDENT also reproduces.
Every one of the five local snapshot boundaries, each restored twice, reproduces.
A duplicate PLAN afterward finally applies the failure (verified={1}, failed={0})
but **does not reopen i or correct HEALTHY/0**. This is not a failure arriving
after legitimate completion: the failure arrived before the decisive success.

Both old local/hive implementations (`e6afe16` and `5de0d53`) leave the incident
open under these exact schedules. Their linkage delay was incomplete, but the
new fallback changes that conservative result into unsafe completion.
Control: replay PLAN **before** the last success drains the failure and keeps
i open; a subsequent fresh step-0 success completes normally.

**Required repair:** make late ownership/link establishment and pending receipt
application coherent before deciding completion. An owner fallback cannot bypass
unapplied evidence relevant to that owner.

Evidence: [focused-witnesses.json](../experiments/20260928-astra-7133-b/focused-witnesses.json),
`late_pending_failure`, `late_pending_failure_after_incident`, five
`late_pending_failure_current_boundary_*` cases, and the duplicate-PLAN controls.

### 3. N6 PARTIAL: first ownership is stored but not enforced on all paths (Medium)

**Conflicting PLAN still creates an unauthorized second link.**
[controller/reducer.py:154](https://github.com/bgoertzel-sing/hive-appliance/blob/623c92be3e2ab96fd76024881066628b6c73abb5/controller/reducer.py#L154)
and [hive/reducer.py:319](https://github.com/bgoertzel-sing/hive-appliance/blob/623c92be3e2ab96fd76024881066628b6c73abb5/hive/reducer.py#L319)
use `setdefault` for the owner map, but then link the incident named by the
*later* PLAN even when it disagrees with that owner. Resolution accepts any
`incident.plan_id == plan_id`, independently of authoritative ownership.

Minimal witness: INCIDENT i, INCIDENT other, PLAN p->i (one step), successful
p/0, then PLAN p->other (one step). **The last PLAN alone closes other without
any receipt for it.** Both owner maps still correctly say p->i; both reducers
nevertheless report zero open incidents and hive HEALTHY. The two-step variant
also fails in seven schedules: live plus all six local snapshot boundaries,
with two re-restores per boundary. Same-owner duplicate PLAN and changed-count
controls correctly retain the original count/progress.

**Incident-only receipts bypass the owner check.** The explicit dual-address
guard at [controller/reducer.py:197](https://github.com/bgoertzel-sing/hive-appliance/blob/623c92be3e2ab96fd76024881066628b6c73abb5/controller/reducer.py#L197)
and [hive/reducer.py:368](https://github.com/bgoertzel-sing/hive-appliance/blob/623c92be3e2ab96fd76024881066628b6c73abb5/hive/reducer.py#L368)
does not validate ownership again after deriving an effective plan from an
incident link. After a conflicting PLAN, or an INCIDENT other prelinked to p,
an incident-only success for other/0 contributes to p even though p belongs
to i. A p/1 success then closes both. Even legitimate plan-only receipts close
an unrelated prelinked incident once p completes.

**Old snapshots cannot reconstruct permanent first ownership generally.**
[controller/reducer.py:324](https://github.com/bgoertzel-sing/hive-appliance/blob/623c92be3e2ab96fd76024881066628b6c73abb5/controller/reducer.py#L324)
chooses the first incident-list link when the owner map is absent. Authentic
old snapshots with two incidents linked to p can represent opposite first-PLAN
owners with **byte-identical JSON**, proved separately for `e6afe16` and
`5de0d53`. Incident insertion order is not PLAN ownership order. A PLAN that
preceded its incident may leave no owner link at all; restore then accepts a
later conflicting PLAN as the first owner. Four of six explicit old-owner
migration cases fail; the two ordinary resolved-link controls pass.

The original resolved-target and unlinked-target dual-address witnesses **are
fixed**, including local new/old snapshot controls. The completed-plan rebound
also reproduces in both baseline implementations: this part is a pre-existing
residual, not a newly introduced production regression. New owner-map migration
does not safely handle missing/ambiguous historical ownership.

**Required repair:** enforce the authoritative owner at PLAN registration,
incident-link admission, effective receipt admission, and resolution. For old
snapshots lacking recoverable first-owner evidence, preserve uncertainty and
fail closed or reconstruct from an authentic event log rather than inventing it.
Severity remains Medium for these adversarial identity payloads; no external
transport injection or host damage was demonstrated.

Evidence: [ownership-lifecycle.json](../experiments/20260928-astra-7133-b/ownership-lifecycle.json),
[authentic-old-ownership.json](../experiments/20260928-astra-7133-b/authentic-old-ownership.json),
[corrected intermediate owner traces](../experiments/20260928-astra-7133-b/corrected-old-owner-traces.json),
and [baseline/identical-snapshot controls](../experiments/20260928-astra-7133-b/focused-witnesses.json).

## Verdict And Statuses

**Keep live-repair/replay readiness gated.** N5 and N6 make real progress on
their original examples, but cannot be closed. H2 remains PARTIAL and N7 is a
new safety regression. Reducer agreement is not an oracle: the unsafe N6/N7
schedules agree on the wrong answer. No whole-codebase readiness claim follows.

| ID | Status at 623c92b | Bounded evidence |
|---|---|---|
| A1 | CLOSED, retained | Stale worker loses lease; independent SQLite winner survives. |
| A2 | CLOSED, retained | Active partial kept, orphan partial removed. |
| H1 | CLOSED, retained | Polling cannot mask a genuinely unresolved critical incident. |
| H2 | PARTIAL | Original groups pass; N5/N6/N7 still defeat broader safe completion. |
| U1 | CLOSED, retained | Failed checkpoint create/readback blocks dispatch; rollback failures recorded. |
| U2 | CLOSED, retained | Real-shell rollback/order, honest flags, metadata and CLI controls pass. |
| U3 | CLOSED for prior named defect | Lifecycle/dedup/composite round-trip passes; N5/N6 migration is not certified. |
| L1 | CLOSED, retained | Timeout/stop ownership and eventual restart pass. |
| S1 | CLOSED, retained | Terminal transition and invalid direct-SQL state checks pass. |
| P1-symlink | CLOSED, retained | Main/thumbnail symlinks rejected without outside creation. |
| P2-store | CLOSED, retained | Rooted wiring, all mutators, canonical paths and sentinel checks pass. |
| N1 | CLOSED, retained | Public repair success HEALTHY/0; failed second step FAILED/1. |
| N2 | CLOSED, retained | Distinct indices, dedup, retries, invalid indices/legacy booleans pass. |
| N3 | CLOSED for original pre-PLAN batch defect | Original failure-last cases pass; separate late-incident bypass is N7. |
| N4 | CLOSED for original timing defects | Original schedules and seven repeated-restore boundary controls pass. |
| N5 | PARTIAL; new stale-progress regression | Original buckets discarded/count correct; affected old success remains usable. |
| N6 | PARTIAL | Named lifecycle witnesses fixed; first-owner enforcement and ambiguous old restore incomplete. |
| N7 | OPEN, new High | Owner fallback completes with pending newer failure. |

Original eleven IDs: ten bounded CLOSED, H2 PARTIAL. These are scoped statuses,
not certificates for every path involving those subsystems.

## Exact Execution Results

Seven original scripts were copied **byte-for-byte** from the original 7075
evidence into this new directory; their portable `HIVE_SRC` import roots point
at the pinned worktree, and their `tmp/` parent exists. Old evidence was not edited.

| Harness | Actual child exit | Result |
|---|---:|---|
| adversarial.py | 1 | Expected old-bug assertion fails at first corrected N3 check; later checks not reached. |
| adversarial-inverted.py | 0 | Three corrected expectations pass (1/1, 0/0, 2/2 terminal pairs). |
| new_cases.py | 0 | 398/398: 14 named cases and 384 permutations/address assignments. |
| supplementary.py | 0 | 4/4 additional lifecycle/prelink schedules. |
| probes.py | 0 | 14/14 earlier scoped regression groups. |
| older-regressions.py | 0 | 2/2 rooted-store/all-mutator and prior H2 groups. |
| independent.py | 0 | N1/N2, current snapshots, public repair and production path wiring pass. |
| semantic_7133.py | 1 | Recorded semantic failures below; no harness exception or timeout. |
| focused_witnesses.py | 1 | Baseline comparisons and additional late-event failures below. |
| correct_owner_traces.py | 0 | Six final outcomes unchanged; two intermediate owner records corrected. |

**Original schedule reconciliation: 14 + 384 + 4 = 402 pass, 0 fail.** Other
regression groups, the three inverted checks and independent additions are not
silently included in that denominator.

| Independent semantic group | Pass | Fail | Total |
|---|---:|---:|---:|
| Current arrival-v1 ordering/restores | 3,072 | 0 | 3,072 |
| Authentic 5de0d53 ordered-list migration/restores | 3,072 | 0 | 3,072 |
| Authentic e6afe16 pre-PLAN buckets, fail-closed + fresh recovery | 384 | 0 | 384 |
| Original identical-byte legacy histories + disk restore + recovery | 2 | 0 | 2 |
| Authentic legacy stale-progress restore variants | 0 | 3 | 3 |
| Current ownership/lifecycle/boundary cases | 34 | 14 | 48 |
| Authentic old ownership migrations | 2 | 4 | 6 |
| Cross-agent same plan/receipt-ID namespace control | 1 | 0 | 1 |

The current-format sweep includes the original **1,920** cases (384 receipt
permutations/address assignments x five pre-PLAN boundaries), plus **1,152**
cases at three further boundaries: after PLAN, fresh step 0, and fresh step 1.
Every selected boundary is restored **twice**, via sorted-key JSON. Expectations
explicitly calculate latest step evidence, open identity and hive health; they
do not merely compare reducers. The same 3,072 schedules also use the real
5de0d53 ordered-list producer, which has no `pending_format` or `plan_owner`.

Of the 14 failed lifecycle cases, 12 are N6 owner/link variants and two are
conservative late-event liveness limitations. They are not 14 distinct bugs.
The separate focused run records **26 rows**: each baseline has 3 pass/3 fail
of six controls, and current has 2 pass/12 fail of fourteen controls. These
include repetitions and causal controls for the findings, not a disjoint
aggregate to add to the main sweep.

Public repair uses real Appliance, planner, verifier, HiveAppliance and
LocalAgentAdapter, with a receipt-producing executor double (not host repair).
Both paths execute indices [0,1]. Success verifies [true,true], outcome
`resolved`, local/hive open=0, HEALTHY. Failed second step verifies [true,false],
outcome `rolled_back`, local/hive open=1, FAILED after two hive ticks.
The earlier shell rollback probes separately execute bounded temporary-file
commands; no live service or production state is modified.

## Changed Tests And Remaining Limits

The amended `test_legacy_bucketed_pending_snapshot_restores` at
[tests/test_astra7024.py:154](https://github.com/bgoertzel-sing/hive-appliance/blob/623c92be3e2ab96fd76024881066628b6c73abb5/tests/test_astra7024.py#L154)
is **legitimate for the requested fail-closed compatibility change**. It adds
discard-count and remains-open assertions, then requires fresh evidence before
completion. Comparing that case to uninterrupted discarded history would be
the wrong oracle. No original test was removed; the diff adds six lines there
and nine new test functions in `tests/test_astra7075.py`. All nine new cases
and the amended test pass in the one full suite.

Coverage is nonetheless insufficient: the handwritten legacy fixtures have no
existing verified progress; owner tests never attempt a conflicting/rebound
PLAN or an ambiguous real old snapshot. The test named
`test_n5_information_loss_opposite_outcomes_both_stay_open` uses two constructed
bucket dictionaries; it does not itself prove that opposite histories produce
identical bytes. This review does prove that with actual old producers.

Two additional **pre-existing conservative liveness limitations** remain:
PLAN before INCIDENT followed by incident-only successes does not drain the
receipt until another PLAN; an INCIDENT arriving after all plan successes is
not automatically resolved. Both keep the incident open/FAILED rather than
manufacturing success. They reproduce at both baselines and are included in
the failed semantic counts, but are not mislabeled new High regressions.

`pending_format="arrival-v1"` is emitted; restore dispatches by container type,
not by validating that marker. The bounded sweeps establish compatibility for
the actual old dict and ordered-list formats, not an arbitrary future version.
`legacy_pending_discarded` counts entries on that restore; a subsequent new-format
restore resets it to zero. It is not a durable historical loss counter.
Neither observation is promoted to a separate safety finding here.

HiveReducer exposes no equivalent snapshot/restore API. Snapshot boundary tests
restore the local reducer and keep hive on its actual event stream; no invented
hive persistence contract is claimed. Agent scoping is checked with ordinary
distinct agent IDs, not arbitrary hostile identifier encodings or transport input.

## Full Pytest Once

Invoked **exactly once by this reviewer**, on a 245-file tracked-source copy:

```text
/usr/bin/python3 -m pytest tests/ -v -p no:cacheprovider \
  --basetemp=/home/openclaw/research-agent/projects/hive-appliance/experiments/20260928-astra-7133-b/pytest-tmp
cwd: .../experiments/20260928-astra-7133-b/source
665 collected; 664 passed, 1 failed; pytest duration 72.93s
actual child exit 1; timed_out=false; launcher wall time 73.65s
```

Only `tests/test_packaging.py::test_wheel_build` fails: the isolated build cannot
obtain `setuptools>=61` under `PIP_NO_INDEX=1`. This is an observed offline build
dependency provisioning failure, not a reducer assertion failure. No build
dependency installation, packaging-specific retry or second full suite occurred.
The commit message's 665-pass claim is author evidence, not this review's result.
Previous parent packaging success belongs to 7075, not a new installed-package
qualification of 623c92b.

See [pytest-exit.json](../experiments/20260928-astra-7133-b/pytest-exit.json)
and [pytest.stdout](../experiments/20260928-astra-7133-b/pytest.stdout).
Launchers return zero after saving statuses; **launcher exit is not child exit**.

## Provenance And Reproduction

Evidence: [20260928-astra-7133](../experiments/20260928-astra-7133-b/).
`run_review.py` checks the full pin, exports tracked files, copies original
harnesses and records environment, commands, elapsed time and actual exits.
Its start markers and exclusive output creation refuse accidental overwrite,
including a second full pytest invocation. Legacy reducers are verbatim
`git show` exports from `e6afe16` and `5de0d53`; focused controls also export
both old hive reducers. Schemas, hive types and CheckpointManager are unchanged
across those baselines and the reviewed pin.

To reproduce into a **fresh sibling evidence directory**, copy the authored
launchers/probes, set `HIVE_SRC` to a clean checkout of the full pin, and run:

```text
/usr/bin/python3 run_review.py
/usr/bin/python3 run_semantic.py
/usr/bin/python3 run_focused.py
/usr/bin/python3 run_trace_correction.py
```

Keep the original `20260928-astra-7075` input directory available. Individual
copied original harnesses also run in any fresh directory with a `tmp/` child
and `HIVE_SRC` set. Expected failure statuses are documented above; rerunning
the launchers in this sealed directory is intentionally refused.

Python 3.10.12; pytest 9.1.1. No stochastic sampling or seed: finite ordering
sweeps are exhaustive only over their stated case sets. UUIDs/checkpoint names
are incidental. Offline flags and a inherited Python socket guard are recorded
in `review-env-overrides.json`; this guard is not an OS security sandbox.

**Recorder correction disclosed:** the first semantic script retained references
to local owner maps in some intermediate trace records; later insertions could
appear retroactively in those records. Open sets, verified/failed steps,
snapshots, and final-state assertions were not affected. A new focused recorder
deep-copies state; a six-case narrow recheck corrects the two affected old-owner
intermediate records and confirms all six final outcomes unchanged. Initial
files remain untouched; use `corrected-old-owner-traces.json` for those states
and focused traces for causal timing. No full-suite rerun was used to correct it.

`source-sha256.json`, `copy-provenance.json`, `verification.json` and `SHA256SUMS`
record source/evidence integrity. Final verification checks the original evidence
seal, all copied-script bytes, all 245 pinned source files and the clean worktree.
Scratch/source-copy build outputs are excluded from the evidence seal; source
content has its separate manifest. No secrets or environment dumps are stored.

Applied research rules: 2 (semantic invariants), 4 (independent review),
5 (reproducible pin/evidence), 7 (reducer and checkpoint boundaries).
No production edits, global installs, commits, pushes, deployment or publication
were performed. This is not a live upgrade, real transport attack, hostile
snapshot validation, global-concurrency or whole-codebase certification.
Parent owns project/task integration and publication.

**Next unresolved work:** repair stale-progress invalidation (N5), late-owner
pending-evidence completion (N7), and authoritative ownership/migration (N6),
then independently requalify these exact witnesses before lifting the gate.
