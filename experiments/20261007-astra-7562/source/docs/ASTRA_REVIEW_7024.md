Model (self-reported): GPT-6 (Codex)

# Astra re-review 7024 — e6afe16

Date: 2026-09-27. Repository: `bgoertzel-sing/hive-appliance`.
Reviewed pin: `e6afe163410abb48175c562032786a8c7a7278f6`; worktree `repos/hive-astra-7024`.
Change reviewed: `e13aa6d..e6afe16`; prior source review: `44aaef8` (the intervening commit adds the prior report).
The model line is self-identification, not gateway provenance; the parent verifies the gateway session record separately.

## Verdict

**Not ready to approve the reducer layer for gated live repair.** The original N3 schedule is fixed, and the original N4 schedule now agrees. Nevertheless, independently constructed buffered streams still cause premature **local** resolution or local/hive disagreement:

- **New N5, High:** local PLAN processing concatenates plan-addressed receipts before incident-only receipts, losing their original arrival order. An older success can override a newer failure, or an older failure can override a newer verified retry.
- **N4 remains PARTIAL, Medium:** buffered contradictory evidence is rejected at different times. If the other incident resolves before this receipt's PLAN arrives, local reduction accepts evidence that hive already rejected.

**Original findings: 10 CLOSED, H2 PARTIAL. N1/N2/N3 CLOSED for their named defects; N4 PARTIAL.** Ordinary end-to-end public repair succeeds at HEALTHY/0; a failed step stays FAILED/1. These positive results do not establish correctness of buffered transport/replay schedules.

**Full pytest run exactly once: 647 passed, 1 failed, 648 collected; true exit 1.** The only failure is offline wheel-build dependency provisioning. The claimed 648 passing tests is not reproduced in this environment.

## Findings table

| ID | Status | Observed evidence |
|---|---|---|
| A1 | CLOSED | Prior blocked-worker/concurrent SQLite-claim probe passes: stale worker cannot replace winner's completed bytes/row. |
| A2 | CLOSED | Live partial retained; orphan partial removed. |
| H1 | CLOSED | Every polled health state preserves an active critical incident; failed composite remains FAILED/1; genuine completion survives subsequent healthy poll. |
| H2 | **PARTIAL** | Missing/late PLAN, distinct indices, invalid/bool indices, dedup, untargeted receipts, normal buffering and retries pass. N3 is fixed, but mixed-address buffer ordering (N5) and lifecycle-dependent identity rejection (N4 residual) still violate shared completion semantics. |
| U1 | CLOSED | Checkpoint create/readback failure blocks dispatch; rollback-load failures remain durable; metadata restoration passes. |
| U2 | CLOSED | Bounded real-shell rollback, newest-first ordering, missing/failing rollback flags, metadata and CLI probes pass. |
| U3 | CLOSED | Prior incident/dedup/composite snapshots pass; new pending-buffer JSON roundtrips preserve state. Snapshot persistence does not fix the logical N4/N5 defects, which also reproduce after restore. |
| L1 | CLOSED | Timed-out worker retains stop signal/liveness; replacement refused; eventual restart and normal worker pass. |
| S1 | CLOSED | Terminal-state validation and invalid direct-SQL state rejection pass. |
| P1-symlink | CLOSED | Planted-root-symlink main/thumbnail checks reject without outside creation. |
| P2-store | CLOSED | Default/custom production stores are rooted; external, relative, traversal and external-symlink paths reject; accepted paths canonicalize. Append/update/finish containment and download/delete outside-sentinel preservation pass. |
| N1 | CLOSED | Real `Appliance.repair()`, unlinked recorded incident, SimplePlanner, ExitCodeVerifier and LocalAgentAdapter: successful two-step executor produces local 0 / hive HEALTHY/0; failed second step produces local 1 / hive FAILED/1. |
| N2 | CLOSED | Distinct step indices required locally; duplicate step 0 cannot complete; invalid indices rejected; verified retry clears failure; identity/snapshot and legacy-boolean checks pass. |
| N3 | CLOSED | Original success0/success1/failure0/PLAN now leaves both open with failed step 0. Fresh verified retry closes both. Pure plan-addressed batch permutations pass. |
| N4 | **PARTIAL** | Original registered-plan contradiction, simple buffered contradiction and ordinary incident-only cases pass. Contradiction arising while buffered can be forgotten locally once the other incident resolves; detailed counterexample below. |
| N5 | **OPEN — High, new** | Mixed plan-addressed/incident-only buffers are reordered locally on PLAN; both premature completion and false non-completion reproduced, including after snapshot restore. |

CLOSED is bounded to the named defect and exercised schedules, not subsystem certification. N5 is a newly demonstrated finding; no baseline execution was used to claim its historical introduction.

## 1. Rerun of the 7003 adversarial harness

The original evidence file was left untouched. [Copied adversarial.py](../experiments/20260927-astra-7024/adversarial.py) changes only the worktree import path. It exits **1** at its first assertion because it explicitly expected the old N3 bug (`[local=1,hive=0]`). Consequently its later assertions and JSON write are not reached in that unchanged-assertion run.

[adversarial-inverted.py](../experiments/20260927-astra-7024/adversarial-inverted.py) changes only the two obsolete expected terminal pairs and the JSON output filename. It exits **0**; [results](../experiments/20260927-astra-7024/adversarial-inverted.json):

| Prior check | Old expected pair | Observed corrected pair | Interpretation |
|---|---|---|---|
| Buffered successes, then failure, then PLAN | 1 / 0 | 1 / 1 | Expected inversion: N3's exact reproduction fixed. |
| Same stream followed by fresh verified retry | 0 / 0 | 0 / 0 | Does **not** invert; terminal retry behavior remains correct. Intermediate post-PLAN pair is now 1 / 1. |
| Contradictory identity with both plans registered | 1 / 2 | 2 / 2 | Expected inversion: N4's exact reproduction fixed. |

Protomega2's warning about old assertions is correct. A failing old-bug assertion is not itself a regression.

## 2. Independent identical-stream probes

[new_cases.py](../experiments/20260927-astra-7024/new_cases.py) feeds the same Event object to both reducers. After every event it asserts equality of **open incident identities**, displayed hive count, verified-step sets, failed-step sets, and explicit expected counts. Failed assertions are recorded while the stream continues, so later retry behavior is visible. Where applicable, local state is JSON-snapshotted/restored midstream; the hive reducer continues uninterrupted. No hive snapshot API is asserted.

**398 schedules: 227 pass, 171 fail.** These are probe assertions, not additional pytest invocations. Eleven of fourteen named schedules pass; three mixed-address cases fail. The 384 systematic schedules cover all 24 orderings of success/failure for each of two indices, across all 16 assignments of plan-only versus incident-only addressing. Of those, **216 pass, 168 fail**: 84 disagree on open incidents; another 84 disagree on step progress while remaining open. Those 168 failures are manifestations of one ordering defect, not 168 separate findings.

Passing named coverage includes:

- Failure then success within buffer; multiple failed indices; retries before and after PLAN; duplicate retries and duplicate old failures; PLAN replay.
- Buffered receipts for two different plans naming one incident, including the first linked plan remaining failed while the other completes. Evidence for the second plan does not resolve the first plan's incident.
- Receipts with neither identity resolve nothing.
- Incident-only receipt held for incident `i`, followed by a PLAN linking **another** incident; it remains held until the correct PLAN links `i`.
- Contradictory identity introduced while buffered, with the contradictory incident still open when the receipt's plan arrives.
- Pending failure buffer, incident-only buffer, and contradictory buffer snapshot/restore.

[supplementary.py](../experiments/20260927-astra-7024/supplementary.py) adds four lifecycle/prelink schedules: two pass, two expose the N4 residual (ordinary and snapshot variants). **Combined new coverage: 402 schedules, 229 pass, 173 fail.** Full traces: [new-cases.json](../experiments/20260927-astra-7024/new-cases.json), [supplementary.json](../experiments/20260927-astra-7024/supplementary.json).

### N5 — local buffering loses arrival order across identity forms (High)

**Observed minimal two-step schedule** (`mixed_early_incident_success_late_plan_failure`):

```text
INCIDENT i, initially unlinked
receipt is: incident_id=i, no plan_id, step 0, verified=true
receipt pf: plan_id=p, step 0, verified=false
receipt 1:  plan_id=p, step 1, verified=true
PLAN p: incident_id=i, two steps
```

Before PLAN both have one open incident. After PLAN:

- Local: **open=0**, verified `{0,1}`, failed `{}`.
- Hive: **FAILED/1**, verified `{1}`, failed `{0}`.

There has been **no retry after the failed step**. A subsequent fresh verified step-0 receipt makes both resolved. JSON snapshot/restore before PLAN reproduces the same premature local resolution.

The reverse schedule (incident-only **failure** first, later plan-addressed **success**, then step 1 and PLAN) instead leaves local open while hive correctly resolves HEALTHY/0.

**Source-backed explanation:** `controller/reducer.py:144` pops the plan bucket, then lines 148–149 append the incident-only bucket. Each bucket preserves its own order, but the merged batch does not preserve the common event order. `_apply_receipt` uses last-applied evidence per index. Hive's single pending dictionary is traversed in arrival order (`hive/reducer.py:324`). Applying a whole batch before completion fixes N3 but does not make an incorrectly ordered batch correct.

**Assessment/inference:** High because authoritative local incident state can clear despite the newest evidence being failure. The ordinary synchronous public-repair stream does not exhibit this; no live transport injection or host damage was demonstrated. The finding concerns the explicitly supported buffered receipt API and replay semantics.

### N4 residual — rejection timing depends on unrelated incident lifecycle (Medium)

**Observed schedule** (`buffer_contradiction_then_other_resolved`):

```text
INCIDENT i; INCIDENT other
receipt bad: plan_id=p, incident_id=other, step 0, verified=true
receipt good: plan_id=p, step 1, verified=true
PLAN q: incident_id=other, one step
receipt q0: plan_id=q, step 0, verified=true   # resolves other
PLAN p: incident_id=i, two steps
```

At PLAN q, hive rechecks all pending receipts and rejects `bad`: `other` is now linked to q, not p. Local reduction only examines q's relevant buckets and leaves `bad` pending under p. After q0 both have only `i` open. At PLAN p, **local closes i (open=0), hive keeps i FAILED/1**. Local's identity check now searches only open incidents, so resolved `other` no longer supplies the contradiction. A fresh clean p/0 retry finally closes hive too. Snapshot/restore between q0 and PLAN p retains the divergence. Control: if `bad` first arrives after PLAN q, both reject it and agree throughout.

**Source-backed explanation:** local `_handle_plan` scans only the plan/incident buckets (`controller/reducer.py:144`), whereas hive revisits every pending receipt after each PLAN (`hive/reducer.py:324`). Both identity checks use open incidents, but they execute at different lifecycle points (`controller/reducer.py:209`, `hive/reducer.py:359`). Hive remembers its rejection via the seen-receipt set; local never made that rejection.

**Assessment:** The original N4 sequence is fixed, but the broader claimed same identity contract is not. Keep N4 PARTIAL rather than declare closure based only on that sequence. No production injector or baseline introduction test was performed.

## 3. H2 decision

**PARTIAL**, not CLOSED or wholly OPEN. Missing PLAN fails closed; valid late PLAN replays receipts; index validation, dedup, distinct composite completion and straightforward retries work. The original buffered premature hive resolution (N3) is specifically closed. However H2 is about sound targeted completion under buffering/replay, and N5/N4 still allow identical evidence streams to produce inconsistent or premature local completion. Atomic resolution must be paired with consistent ordering and identity-admission semantics.

## 4. Regression evidence

- [probes.py](../experiments/20260927-astra-7024/probes.py): the prior 7003 copy of the 6986 regression harness, with only import pin updated and existing scoped CASES retained. **14/14 groups pass, exit 0**: A1, A2, H1, H1/H2 interaction, U1, U2 metadata/shell/CLI, U3, L1 timeout/normal, S1, P1, P2 effect boundary.
- [older-regressions.py](../experiments/20260927-astra-7024/older-regressions.py): copied directly from **6986**; selected original `p2_store_now` and `h2_prior_residual_now` function bodies unchanged, pin updated, historical unrelated CASES replaced by those two calls. **2/2 pass, exit 0**. All rooted mutators reject outside paths; untargeted receipt stays FAILED/1; partial composite stays open; completion is HEALTHY/0 and remains so after polling.
- [independent.py](../experiments/20260927-astra-7024/independent.py): 7003 independent probes rerun with only pin substitution, **exit 0**. Covers N1 real public repair, N2 distinct-index/replay/invalid-index/legacy-snapshot behavior, pending/progress snapshots, and production default/custom attachment paths and consumer effects.
- Public repair uses a receipt-producing in-memory executor, **not host repair commands**. Both success/failure execute indices `[0,1]`; success verification `[true,true]`, outcome `resolved`, local 0 and hive HEALTHY/0. Failure verification `[true,false]`, recovery outcome `rolled_back`, local 1 and hive FAILED/1. The final count is checked after two hive ticks.

Historical unused functions remain in copied harness files; their presence does not mean they were executed. Their active CASES and exit files identify executed coverage.

## 5. Changed-test assessment

[Exact test diff](../experiments/20260927-astra-7024/modified-tests.diff): **only a new file**, `tests/test_astra7003.py`, with eight tests. No older tests or assertions were removed, altered or weakened in `e13aa6d..e6afe16`.

**Legitimate additive regression tests, but insufficient coverage.** Seven tests use a shared runner comparing local/hive open counts after each event; the eighth is local-only snapshot roundtrip. Thus the claim that all eight test local/hive agreement after every event is too broad. Counts also cannot expose different open identities or divergent step progress with equal counts. The new tests cover pure plan-addressed buffering and simple identity cases; they do not mix receipt addressing forms in one buffer or resolve a formerly contradictory incident before the other PLAN arrives. All eight pass in the one full suite.

## 6. Full suite, provenance and limits

Evidence directory: [20260927-astra-7024](../experiments/20260927-astra-7024/).

The full suite was invoked **exactly once** on a tracked-source copy under evidence to contain packaging writes. Exact argv and subprocess wait result are in [pytest-result.json](../experiments/20260927-astra-7024/pytest-result.json):

```text
/usr/bin/python3 -m pytest tests/ -v -p no:cacheprovider --basetemp=<evidence>/pytest-tmp
647 passed, 1 failed in 26.95s
true pytest exit_code: 1; timed_out: false; wall_seconds: 27.53
```

[pytest.stdout](../experiments/20260927-astra-7024/pytest.stdout) and [pytest.stderr](../experiments/20260927-astra-7024/pytest.stderr) preserve output. The runner itself exits zero after recording the child result; **zero is not the pytest exit code**.

The sole failure is `tests/test_packaging.py::test_wheel_build`: its isolated build environment attempts dependency provisioning and cannot obtain `wheel` under `PIP_NO_INDEX=1`. This is an observed environment/build-provisioning failure, not an observed product assertion regression. No dependencies were installed and no packaging retry was made. The inherited Python socket guard blocks non-loopback connections; it is not an OS sandbox. Pytest plugin autoload was disabled, matching the prior review environment.

`environment.json`, `source-sha256.json`, `verification.json`, `copy-provenance.json` and `SHA256SUMS` record the source pin, unchanged tracked worktree, versions, harness copies and evidence integrity. No production source edits, pushes or live service changes. Only the requested review report and exclusive evidence directory were authored. All failed new probe assertions are retained; they are not hidden by the passing product suite.

## Prioritized remaining fixes

1. **P0 — N5:** preserve one ordered pending-receipt stream (or a persisted arrival sequence) across plan and incident addressing. Revalidate and apply all newly eligible evidence in that order, then decide completion. Preserve order/dedup across snapshot restore. Add mixed-address success→failure and failure→retry tests with identities and step-state comparison after every event.
2. **P1 — N4 residual:** align when both reducers permanently reject buffered contradictions. Reevaluate affected pending receipts consistently when PLAN links an incident; do not let later incident resolution resurrect locally accepted evidence that hive already rejected. Add the lifecycle and snapshot counterexamples above.
3. **P1 — qualification:** after those fixes, rerun identical-stream tests and preserve public repair success/failure behavior before approving buffered/replayed reducer use in gated live repair.
4. **P2 — packaging:** qualify wheel construction separately with pre-provisioned approved build dependencies; this offline run cannot certify it.

Model (self-reported): GPT-6 (Codex)
