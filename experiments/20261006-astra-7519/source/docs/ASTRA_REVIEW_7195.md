# Astra Review 7195: f1736e5

Selected reviewer: **gpt-6-astra**, explicitly requested; one reviewer, no delegation. Parent owns model-routing verification. A generic Codex self-label is not evidence of a model mismatch.

Review date: 2026-09-28 (America/Vancouver; some machine timestamps are 2026-09-29 UTC). Pin: `f1736e578993d96816114ab4b0dc2023a1534f9f`; base: `cfb03f2aa71e494ed3dd782d6179ed5f1621889b`. Inspected the pinned `docs/ASTRA_REVIEW_7173.md`, its tracked evidence, and `cfb03f2..f1736e5`. Worktree: `/home/openclaw/research-agent/projects/hive-appliance/repos/hive-astra-7195`.

Evidence: [20260928-astra-7195](../experiments/20260928-astra-7195/README.md). Sole output ownership here and that new directory. No production/old-evidence edits, commits, pushes, deployment, gate changes or publication. Parent handles project records and publication.

## Findings First

**No new blocking runtime defect reproduced. N9 and N10 are CLOSED for their reviewed defects.** The before/after classifier is genuinely per receipt, not a final-state classifier. Authentic ef18db3 upgrades now satisfy the diagnostic bounds without dropping actionable quarantine. The following narrow inherited follow-ups remain; they do not reopen the repaired N9/N10 findings.

### 1. Recovery guidance still misidentifies the actionable quarantine (Low, OPEN follow-up)

Source: [controller/reducer.py:683](https://github.com/bgoertzel-sing/hive-appliance/blob/f1736e578993d96816114ab4b0dc2023a1534f9f/controller/reducer.py#L683), [line 706](https://github.com/bgoertzel-sing/hive-appliance/blob/f1736e578993d96816114ab4b0dc2023a1534f9f/controller/reducer.py#L706).

The persisted recovery string says plans in `legacy_ownerless_plans` stay quarantined until rebind. That list is a capped historical sample, not current membership. In the authentic 300-plan upgrade, it lists 256 while **all 300** remain in `owner_unproven`; after rebinding all plans, it still lists 256 while quarantine is empty. This can misdirect operator enumeration, although the reducer itself uses the correct set and remains safe.

Narrow fix: name `owner_unproven` as the authoritative current set and label `legacy_ownerless_plans` as a historical sample. Acceptance: guidance remains correct before and after rebinding, including more than 256 held plans. Evidence: `review7195.json.n10_authentic_pretrim_totals_and_candidate_safety` and authentic checkpoint stages under `focused-checkpoints/`.

### 2. The agreement helper still does not assert the health contract it claims (Low, OPEN follow-up)

Source: [tests/test_astra7160.py:1](https://github.com/bgoertzel-sing/hive-appliance/blob/f1736e578993d96816114ab4b0dc2023a1534f9f/tests/test_astra7160.py#L1), [line 44](https://github.com/bgoertzel-sing/hive-appliance/blob/f1736e578993d96816114ab4b0dc2023a1534f9f/tests/test_astra7160.py#L44).

The docstring promises health comparisons after every event. `agree()` checks open IDs/counts and selected verified/failed sets, but never health. The delta does not change this helper. A health-only regression could pass it. Narrow fix: add an independently specified, severity/lifecycle-aware health assertion, including UNKNOWN before the first incident, or correct the claim and put health coverage elsewhere. This review independently checks health in 51 H2 schedules and audits the original 402 schedules plus 48 lifecycle cases; no health defect appeared there.

### 3. Multi-plan supersession remains an undocumented operational policy (OPEN policy follow-up)

Source: [controller/reducer.py:498](https://github.com/bgoertzel-sing/hive-appliance/blob/f1736e578993d96816114ab4b0dc2023a1534f9f/controller/reducer.py#L498), [line 512](https://github.com/bgoertzel-sing/hive-appliance/blob/f1736e578993d96816114ab4b0dc2023a1534f9f/controller/reducer.py#L512); the prior request is in pinned `docs/ASTRA_REVIEW_7173.md`, Multi-plan Supersession.

Any complete plan with immutable owner i can close i even if a different owned plan failed. There is no newest-plan selection or explicit supersedes/cancellation relation. Four early/late-INCIDENT x p/q-complete witnesses still confirm that behavior. The delta adds the prior review but no operational policy resolving it. This is not a newly introduced false-completion defect: the completing plan owns i and has full verified evidence. Define whether any independently sufficient repair may close, or whether replacement must be explicit; then encode that policy before retiring the contrary historical test.

## Recommendations

**Current-format live repair/replay:** retain the prior bounded recommendation to lift this gate at the reviewed pin. H2/N5-N8 controls pass and the N9/N10 repairs introduce no reproduced event-driven completion regression. This is not blanket deployment approval, nor requalification of every historical Hive subsystem.

**Unrestricted/automatic legacy rebind:** do not lift this gate. The prior implementation defects in preview and retention are repaired, so they are no longer reasons to reject a manually reviewed rebind. Nevertheless, lost ownership is not reconstructible from ambiguous legacy bytes. Candidates come from ordinary PLAN events; actor/reason strings are audit metadata, not authentication or historical proof. Retain independently authorized, trusted-operator ownership decisions with preview and retained audit. `allow_non_candidate=True` is an explicit authority override. No production caller exposing rebind was found outside the reducer API itself. Dropping a candidate for retention never enables default rebind.

Packaging is **unqualified in this environment**, not passed. A properly provisioned isolated wheel check remains outstanding. No actual gate was changed.

## Finding Statuses

Statuses are scoped to named defects and tested contracts, not universal subsystem certification.

| Finding | Status at f1736e5 | Basis |
|---|---|---|
| A1 / A2 | CLOSED, retained | Competing lease/stale worker; active versus orphan partial controls. |
| H1 | CLOSED, retained | Critical open incident cannot be masked by poll; public repair outcomes. |
| H2 | CLOSED, retained | 51 semantic H2 boundary schedules, 48 lifecycle cases, late completion and failure-first draining. |
| U1 / U2 / U3 | CLOSED, original scopes retained | Checkpoint refusal/readback, rollback failure/ordering/metadata/CLI, incident and step round trips. Legacy authority remains separate. |
| L1 / S1 | CLOSED, retained | Worker ownership/restart; terminal transition and SQL constraints. |
| P1-symlink / P2-store | CLOSED, retained | Root containment, production wiring, all relevant mutators and outside sentinels. |
| N1-N4 | CLOSED, retained | Public repair, index/dedup/retry, batch ordering, contradiction admission. |
| N5 | CLOSED, safety retained | Actual e6afe16 linked/unlinked disk snapshots invalidate stale progress and require fresh evidence. |
| N6(a) | CLOSED, strict rejection scope | Rejected PLAN changes only rejection counter in each reducer's complete state. |
| N6(b) | CLOSED, explicit-authority contract | Six authentic old-owner controls; ordinary PLAN cannot supply lost authority. |
| N7 | CLOSED, visibility/durability scope | Warnings and cumulative discards persist without current-roundtrip inflation. Recovery wording follow-up remains above. |
| N8 | CLOSED, retained | 14 original boundaries plus H2 newly eligible failure controls; no early completion. |
| N9 | CLOSED, reviewed preview/audit and alias defects | Independent receipt-level classifications, complete buffer accounting, detached output, pure preview, validations and audit. Trusted caller remains a precondition. |
| N10 | CLOSED, reviewed retention defect | Actual ef18db3 histories capped at 256 on restore, correct pretrim totals, 20 stable round trips, full quarantine retained. |

All original eleven findings remain CLOSED within their original reviewed scopes. The test/documentation/policy follow-ups above are not silently relabeled as runtime regressions.

## N9 Evidence

Source: [per-receipt drain, line 191](https://github.com/bgoertzel-sing/hive-appliance/blob/f1736e578993d96816114ab4b0dc2023a1534f9f/controller/reducer.py#L191), [classification, line 205](https://github.com/bgoertzel-sing/hive-appliance/blob/f1736e578993d96816114ab4b0dc2023a1534f9f/controller/reducer.py#L205), [preview, line 274](https://github.com/bgoertzel-sing/hive-appliance/blob/f1736e578993d96816114ab4b0dc2023a1534f9f/controller/reducer.py#L274), [audit, line 350](https://github.com/bgoertzel-sing/hive-appliance/blob/f1736e578993d96816114ab4b0dc2023a1534f9f/controller/reducer.py#L350).

`review7195.py` supplies independent expected per-ID groups. It does not derive expected effects from the final reducer state or accept preview/audit agreement as the oracle.

- **64/64 schedules:** all 16 four-receipt success/failure assignments x two index patterns x live/double-restored pending state. The abstract expectation tracks latest truth for each step at each arrival. A success later overwritten by failure remains credited; a failure later overwritten by retry remains failure_recorded. Fresh same-truth receipts produce consumed_no_effect. Final step sets and closure are additional assertions.
- **Mixed receipt witness:** valid credit, later failure, duplicate failure, retry, duplicate success, contradictory owner and inferred foreign-owner receipt, negative/out-of-range/bool/float/string/None/nested-dict index, held unknown plan/incident, and a contradictory duplicate payload with the same receipt ID. First buffered ID wins; subsequent replay changes no state. A buffered ID is counted once, not once per duplicate input event.
- **Unrelated drain:** an unknown z/i receipt becomes contradictory when rebind links i to p. It is correctly consumed_no_effect even though it does not name p; an unrelated q receipt remains still_held.
- **Bounded audit:** 160 buffered unique receipts, exactly 40 in each category. Preview contains all 160 effect records; audit counts retain 40 each and `pending_before=160`, while every audit ID list retains exactly its first **32**. The cap is on audit IDs, not the full preview. Twenty JSON round trips preserve audit and counts.
- **Purity:** recursively mutating nested values in every returned preview container does not alter live state. Allowed and refused previews produce no captured logs. The production simulation only deep-copies and reduces in memory; it does not dispatch executors, publish events or write checkpoints. Dict-valued `verified` with a valid index is treated as failure because only literal True verifies; malformed indices are consumed without credit.
- **Retained validation:** 14 invalid actor/reason values plus missing keywords, six denial cases, and six candidate/override/evidence paths pass with expected nonmutation, closure and audit. Resolved, foreign-linked, unknown, noncandidate and nonquarantined targets remain refused. These controls do not authenticate the operator.

The two adaptations to copied `review7173.py` are explicit in `adaptation.diff`: `held_receipts` audit count becomes `pending_before`; the old release-coverage expectation reads all non-held effect records rather than the still-narrow compatibility `held_receipts` field. Original pinned helper bytes remain in `source/`. No historical policy assertion was changed.

## N10 Evidence

Source: [restore normalization, line 690](https://github.com/bgoertzel-sing/hive-appliance/blob/f1736e578993d96816114ab4b0dc2023a1534f9f/controller/reducer.py#L690), [normalizer, line 695](https://github.com/bgoertzel-sing/hive-appliance/blob/f1736e578993d96816114ab4b0dc2023a1534f9f/controller/reducer.py#L695).

The actual e6afe16 reducer produces 300 PLAN-before-INCIDENT plans. Its checkpoint is created and loaded from disk, then consumed by the actual ef18db3 reducer. That producer records 300 candidates and, in a later stage, 300 successful explicit ownership rebinds. Each stage is saved and loaded through `CheckpointManager`, not synthesized by deleting current fields. Included baseline bytes are verified against their Git commits.

Current restore yields 256 historical ownerless IDs with total 300, 256 candidate keys with dropped count 44, and **all 300 actionable `owner_unproven` IDs**. The rebound checkpoint yields the newest 256 audits (`p44` through `p299`) and total 300. Twenty additional current-format JSON round trips at each stage preserve exact state and totals. No receipts were supplied, so all 300 incidents remain open after rebind. The inherited new-path test also rebinds 300 plans and verifies bounded history/totals.

An explicitly pruned held plan has no candidate admission and default rebind is refused without state mutation. A separate mixed map with 300 nonheld keys preceding held p retains p first, caps 301 keys to 256 with dropped count 45, and caps each value list at eight. Quarantine and owner maps remain unchanged; a valid retained candidate still needs explicit trusted rebind. The authored total-continuation test passes 300 -> 301. No silent safety relaxation is needed to preserve bounded diagnostics.

## Retained Evidence and Policy Differences

Authentic e6afe16 linked/unlinked stale-progress checkpoints pass **6/6** explicit disk recovery paths: direct, current-twice and legacy-twice. Fresh step 1 alone cannot reuse stale step 0; fresh step 0 plus any required owner rebind recovers. The original three automatic-PLAN-recovery expectations remain **0/3 composite passes**, while their safety checks pass **3/3**. They are not safety regressions.

The original opposite-history witnesses still serialize identically and pass **2/2** conservative discard plus fresh recovery checks through disk. Legacy ambiguous buckets pass **384/384** finite schedule cases; current arrival-v1 and authentic 5de0d53 ordered snapshots each pass **3,072/3,072** boundary cases. These share the 384 schedule family and overlapping boundaries; do not sum them as independent discoveries. Local snapshots are exercised; no nonexistent hive snapshot API is assumed.

Original `new_cases.py`: **397/398**. Original `supplementary.py`: **3/4**. The two retained policy differences are (1) a fully verified owned p closes while q has failed, and (2) a foreign prelinked incident must not close under another plan's immutable owner. Original expected-bug `adversarial.py` exits at the now-repaired N3 assertion; its three corrected terminal controls pass. Raw nonzero exits are retained, not relabeled as passing runs.

The audit checks 2,426 per-event states from the original 402 schedules and 276 lifecycle states: zero open/step/count/health contradictions. The inherited semantic helper can alias intermediate owner-map references; timing claims use the deep-copied H2 traces and explicit final semantic expectations instead. Fifty-one H2 schedules pass independently specified final open sets, and all 14 retained N8 boundary cases remain safe.

Fourteen prior regression groups plus two older groups pass. Public orchestration uses actual Appliance, planner/verifier, HiveAppliance and LocalAgentAdapter with a receipt-producing executor double: success verifies both steps and ends resolved/HEALTHY/0; failure rolls back and ends FAILED/1. Shell rollback controls only modify temporary fixtures. These tests do not certify physical host repairs or arbitrary concurrency.

## Authored Tests

All six `tests/test_astra7173.py` tests pass in the single full invocation. Four cover N9 and two cover N10. Their first receipt witness has direct semantic assertions, not only agreement; nevertheless the audit comparison alone cannot prove classification correctness. They do not cover overwritten effects, repeated same-truth evidence, all four ID lists above 32, or duplicate IDs. Their upgrade fixture is synthetic current-format data, not an ef18db3-produced checkpoint. This review adds those missing independent controls. The health-helper and supersession follow-ups remain unchanged as noted above.

## Exact Verification

| Primary invocation | Result | Actual exit |
|---|---|---|
| Full authored pytest, exactly once | **698 passed, 1 failed; 699 collected** | **1**, no timeout; 49.7487 s wall |
| New authored 7173 tests | **6/6**, included above | Same invocation |
| Adapted retained 7173 review | **10/10 groups**, including 51 H2 schedules | 0 |
| Independent 7195 review | **7/7 groups**, including 64 receipt schedules | 0 |
| Original adversarial / corrected terminal controls | Old repaired-bug expectation / 3 of 3 | 1 / 0 |
| Original new-cases / supplementary | 397/398 and 3/4 | 1 / 1 |
| Semantic restore/ownership harness | All scoped safety families pass; three obsolete recovery expectations fail | 1 |
| Boundary/disk / mechanism helpers | 14 N8 boundaries; 6 explicit recovery paths and retained controls | 0 / 0 |
| Prior / older regression groups | 14/14 and 2/2 | 0 / 0 |
| Independent public repair/paths / result audit | All assertions pass | 0 / 0 |

Exact full command is in `pytest-exit.json`:

```text
/usr/bin/python3 -m pytest tests/ -v -p no:cacheprovider \
  --basetemp=.../20260928-astra-7195/pytest-tmp
cwd: .../20260928-astra-7195/source
```

Only `tests/test_packaging.py::test_wheel_build` failed. Saved output explicitly reports no matching `setuptools>=61` distribution during isolated build dependency provisioning under recorded `PIP_NO_INDEX=1`. Installed setuptools is 59.6.0. This conclusion follows the actual failure log, not an expected-offline assumption. No global installs, dependency remediation, packaging retry or second full pytest occurred.

## Reproduction and Limits

The evidence README gives exact launcher commands, `HIVE_SRC`, writable temporary-directory setup, and a replay into a fresh directory. All needed historical reducer modules, helpers, guard and tracked source are supplied, with provenance and a compressed source archive. A relocated probe-only run, without Git or imports from prior workspace directories, matches primary summaries and child exit statuses. Its outer exit is 1 because unchanged historical assertions remain nonzero; it is a portability check, not another full-suite run or additional independent evidence count.

`final-integrity.json` verifies the clean pinned worktree, unchanged source/old evidence, source export, baseline hashes and report hash. `SHA256SUMS` covers the report evidence and compressed source; a separate full manifest covers tracked source. Recorded environment is Python 3.10.12, pytest 9.1.1, build 1.5.0, Chroma 1.5.9 and ONNX Runtime 1.23.2. No secrets or environment dumps were collected. Explicit offline flags and a Python socket guard are not an OS sandbox.

Research rules applied: 1 (validate semantic oracles), 2 (state receipt/ownership invariants), 5 (specific reproducible evidence), 7 (public contract checks). Event payloads and expectations are deterministic; generated timestamps/IDs and temporary names are not used as semantic truth. Finite schedules do not prove arbitrary malformed-snapshot integrity, authentication, concurrency, or physical repair correctness. No stronger claim is made.
