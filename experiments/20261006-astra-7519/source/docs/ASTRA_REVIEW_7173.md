# Astra Review 7173: cfb03f2

Selected reviewer model: **gpt-6-astra**, explicitly requested; single reviewer, no delegation. Parent owns routing verification. A Codex self-label is not evidence of a model mismatch.

Review date: 2026-09-28. Pin: `cfb03f2aa71e494ed3dd782d6179ed5f1621889b`; base: `ef18db3ab415d0eabd4e92a96d4f0d7c53d91ad5`. Checkout: `/home/openclaw/research-agent/projects/hive-appliance/repos/hive-astra-7173`.

Evidence: [20260928-astra-7173](../experiments/20260928-astra-7173/README.md). Read the pinned repository's 7160 report/evidence and relevant 7146/7133 findings. Compared production and test changes in `ef18db3..cfb03f2`. No production source, old evidence, live gate, project integration record or publication changes.

## Findings First

### 1. N10 remains PARTIAL: existing diagnostics bypass the new caps on upgrade (Medium)

Pinned source: [controller/reducer.py:530](https://github.com/bgoertzel-sing/hive-appliance/blob/cfb03f2aa71e494ed3dd782d6179ed5f1621889b/controller/reducer.py#L530), [line 554](https://github.com/bgoertzel-sing/hive-appliance/blob/cfb03f2aa71e494ed3dd782d6179ed5f1621889b/controller/reducer.py#L554), [line 317](https://github.com/bgoertzel-sing/hive-appliance/blob/cfb03f2aa71e494ed3dd782d6179ed5f1621889b/controller/reducer.py#L317), [line 284](https://github.com/bgoertzel-sing/hive-appliance/blob/cfb03f2aa71e494ed3dd782d6179ed5f1621889b/controller/reducer.py#L284).

`restore_snapshot()` copies `migration_diagnostics` without normalization. The ownerless-history cap runs only when `plan_owner` is absent; current-format snapshots from **ef18db3 already have that field**. Candidate admission refuses new keys at the limit but does not prune existing keys. Rebind history is pruned only after another successful rebind.

Reproduction uses actual e6afe16 PLAN-before-INCIDENT output, saved/read with CheckpointManager, then the real ef18db3 reducer to produce 300 candidate keys and later 300 rebind records. Both ef18db3 stages are independently saved/read through disk before cfb03f2 restore. Observed after restore and **20 additional current-format restores**:

- Candidate-stage snapshot: **300 ownerless historical IDs, 300 candidate keys, all 300 actionable quarantines retained**.
- Rebound-stage snapshot: **300 historical rebind records** remain. Previous-format histories do not acquire the new ownerless/rebind cumulative-total fields on restore.
- Restores do not multiply the records, but neither do they enforce `MAX_DIAG_ENTRIES=256`.

Evidence: `review7173.json.n10_authentic_previous_upgrade_caps`, `new-checkpoints/n10-ef18db3-candidates/`, `new-checkpoints/n10-ef18db3-audit/`; baseline module hash in `baseline-provenance.json`.

Impact: the actual upgrade path retains the growth N10 was intended to bound. This is a retention/scalability defect, not a demonstrated incident-closure bypass or practical remote denial of service. Normalize all recognized diagnostic histories and candidate maps at restore, initialize totals from pre-pruned history, and preserve **the entire separate `owner_unproven` set**. Never cap that safety-critical set.

### 2. N9 remains PARTIAL: preview/audit does not describe all consumed evidence (Medium)

Pinned source: [controller/reducer.py:229](https://github.com/bgoertzel-sing/hive-appliance/blob/cfb03f2aa71e494ed3dd782d6179ed5f1621889b/controller/reducer.py#L229), [line 219](https://github.com/bgoertzel-sing/hive-appliance/blob/cfb03f2aa71e494ed3dd782d6179ed5f1621889b/controller/reducer.py#L219), [line 279](https://github.com/bgoertzel-sing/hive-appliance/blob/cfb03f2aa71e494ed3dd782d6179ed5f1621889b/controller/reducer.py#L279).

Preview selects receipts naming p or incident-only receipts naming the chosen target. Actual rebind drains **the whole pending buffer**, including receipts inferred through other incident links. With an authentic ambiguous legacy snapshot linking both i and other to p, hold these fresh receipts while p is quarantined:

1. `valid`: plan p, index 0, verified true.
2. `invalid_index`: plan p, index 99, verified true.
3. `contradictory`: plan p plus incident other, index 1, verified true.
4. `other_link_failure`: incident-only other, index 0, verified false.

Preview of the explicit p->i override lists **three** receipts, omitting `other_link_failure`. Actual rebind removes **all four** from pending, credits only step 0, and leaves both incidents open. The audit records `held_receipts=3`, `closed=[]`; it has **no separate released/applied/rejected receipt accounting**. The field is literally named `held_receipts`, so it must not be represented as an accurate released or credited count.

`would_close=[]` is accurate in this witness. The defect is incomplete evidence disclosure/accounting, not erroneous closure prediction or loss of fail-closed behavior. Evidence: `review7173.json.n9_preview_release_coverage`. Derive preview and audit effects from the simulated before/after buffer and admission results, distinguishing applied, rejected and still-held receipts.

### 3. N9 preview returns mutable receipt-field aliases (Low)

Pinned source: [controller/reducer.py:232](https://github.com/bgoertzel-sing/hive-appliance/blob/cfb03f2aa71e494ed3dd782d6179ed5f1621889b/controller/reducer.py#L232).

`held_receipts` is newly allocated, but `step_index` and `verified` values are not copied. The reducer accepts and buffers malformed structured values while ownership is unproven. A receipt with dict/list-valued fields survives there; changing those fields through the returned preview changes `_pending_receipts` in the live reducer. The preview call itself does not mutate state, but its returned data is not detached.

Evidence: `review7173.json.n9_preview_mutable_alias_purity`, preserving before/after pending payloads. This requires malformed mutable fields; ordinary integer/bool fields are immutable. No conversion of malformed evidence into verified credit or unauthorized incident closure was demonstrated. Deep-copy or normalize exported preview fields.

## Gate Recommendations

**Current-format live repair/replay:** retain the 7160 recommendation to lift this bounded gate at the reviewed pin. H2 late-INCIDENT liveness is now repaired, N5/N6/N8 safety controls remain intact, and no new event-driven false completion was found in the reviewed schedules. These findings do not justify withdrawing the prior scoped current-format recommendation.

**Legacy recovery/rebind:** do **not** lift an unrestricted or automatic legacy-rebind gate. The new default validation is substantially better, and explicit trusted recovery succeeds. However, preview effects are incomplete, returned evidence is not fully detached, and diagnostic caps do not cover authentic upgraded histories. Keep recovery restricted to independently authorized, manually reviewed ownership decisions; actor/reason strings and event-proposed candidates are not authentication or historical proof.

These are recommendations, **not blanket deployment approval**. No live gate was changed. Packaging remains unqualified in this environment; multi-plan supersession needs an explicit operational contract. Parent owns report checking, records, integration and publication.

## Finding Statuses

CLOSED below means the named defect under the exercised contract, not certification of an entire subsystem. N8 is the other 7133 review's buffered-failure finding called N7; N7 here means migration diagnostics.

| ID | Status at cfb03f2 | Evidence/qualification |
|---|---|---|
| A1 | CLOSED, retained | Competing SQLite lease/stale-worker evidence passes. |
| A2 | CLOSED, retained | Active partial survives; orphan partial removed. |
| H1 | CLOSED, retained | Poll cannot mask critical open incidents; public repair outcomes correct. |
| H2 | CLOSED for reviewed ordering/liveness defects | Late owned INCIDENT immediately resolves after complete evidence; failures drain first; ownerless payload-only link does not reuse completion. |
| U1 | CLOSED, retained | Checkpoint create/readback faults prevent dispatch; rollback failures remain explicit. |
| U2 | CLOSED, retained | Bounded shell rollback, ordering, metadata, flags and CLI controls pass. |
| U3 | CLOSED, original scope | Incident identity/composite progress/current snapshot round trips pass; legacy authority remains separate. |
| L1 | CLOSED, retained | Timeout/stop ownership and eventual restart controls pass. |
| S1 | CLOSED, retained | Invalid terminal transitions and direct SQL values rejected. |
| P1-symlink | CLOSED, retained | Main/thumbnail rooted path and outside-creation controls pass. |
| P2-store | CLOSED, retained | Rooted production wiring, all mutators and outside sentinels pass. |
| N1-N4 | CLOSED, retained | Real public repair, indices/dedup/retry, whole-batch ordering and contradiction timing controls pass. |
| N5 | CLOSED, safety | Authentic linked/unlinked stale-progress disk fixtures need fresh affected-step evidence; quarantined plans need explicit rebind. |
| N6(a) | CLOSED, strict rejection scope | Rejected PLAN changes only intentional rejection counter in each reducer's full state. |
| N6(b) | CLOSED under explicit-authority contract | Six authentic old ownership cases safe; ordinary PLAN cannot replace a lost owner. |
| N7 | CLOSED, original visibility/durability defect | Discard warnings, cumulative counters and current restore stability retained. Retention is separately N10. |
| N8 | CLOSED, retained | Both original failure placements, all selected boundaries, and new late-completion drain controls remain safe. |
| N9 | PARTIAL | Validation/candidate/override/audit basics pass; preview evidence coverage and alias purity remain defective. |
| N10 | PARTIAL | New histories bounded with totals and full quarantine preserved; upgraded ef18db3 histories remain unbounded. |

Original eleven: eleven CLOSED for their explicitly bounded reviewed defects; this does not erase the separately tracked N9/N10 limitations.

## Direct Semantic Evidence

### H2 and N8

The change at local reducer line 155 and [hive/reducer.py:251](https://github.com/bgoertzel-sing/hive-appliance/blob/cfb03f2aa71e494ed3dd782d6179ed5f1621889b/hive/reducer.py#L251) passes all owned plans to the existing drain. Both drains apply every eligible pending receipt with completion disabled, then check touched plans. They do not complete the first plan before processing later eligible failures.

`review7173.json.h2_boundary_matrix`: **51/51 schedules**, covering seven semantic scenarios, live execution and every local JSON snapshot boundary with double restore. Direct expected final open sets cover completed late incidents, applied failures, ambiguous pending failures, failures becoming eligible only on linked late INCIDENT, fresh retry, unrelated incidents, and ownerless plans with payload-only links. The newly eligible failure fixture uses two owners so the incident-only failure really is buffered before the late INCIDENT. Local/hive open IDs, verified/failed sets and displayed counts are checked per event; health is checked after incidents arrive. No hive snapshot API is invented.

Unchanged N8 boundary helper: **14/14 safety and agreement passes**, both original failure placements x live/pre-stream/five post-event boundaries. New and old matrices overlap and must not be summed as independent discoveries.

The inherited ownership matrix improves from **47/48 to 48/48**; `late_incident_after_completed_plan` now passes. The ordinary local/hive comparison is supplementary, not the semantic oracle: expected open sets and latest-per-step truth are independently specified.

### N5/N6 authentic legacy recovery

`semantic_7133.py` loads the included authentic e6afe16 and 5de0d53 reducer modules. The old producers are not replaced with new snapshots minus fields. The original opposite-history witnesses serialize identically and are saved/read through CheckpointManager: **2/2 conservative-discard plus fresh-recovery passes**.

The **384/384** e6afe16 legacy ordering/addressing cases discard four ambiguous held receipts and require fresh step 0 and step 1. These cases generally introduce PLAN after migration; they are not substitutes for ownerless-plan recovery.

For already registered plans, `mechanism-probes.json.disk_recovery` has **6/6** linked/unlinked x direct/current-twice/legacy-twice passes, with actual disk checkpoints. In the linked case owner reconstruction is allowed but discarded newer failure invalidates stale success. In the unlinked case the plan remains quarantined; the compatibility helper now supplies actor/reason and an explicit override. Both variants remain open after only fresh step 1 and close only after fresh step 0 plus the required ownership authority.

The unchanged three stale-progress cases still report **0/3 composite passes**, because they require ordinary PLAN recovery. Their direct safety checks pass **3/3**; none closes with stale step 0. Do not call these three safety regressions. Actual explicit recovery is independently demonstrated above.

Six authentic missing-owner/ambiguous-link/resolved-link controls pass; agent-ID isolation passes. The full-state rejection probe compares both reducers before/after a conflicting PLAN with a component subject and pending evidence: **only `rejected_plan_registrations` changes**.

### N9 validation, preview and audit

New independent checks include 14 invalid actor/reason values plus missing keywords. Wrong types, empty and whitespace-only strings raise; full reducer state is unchanged. Six denial cases cover unknown, resolved, foreign-linked, empty, non-candidate and non-quarantined targets. Both preview and apply refuse without state mutation.

Six candidate/explicit-override x no-evidence/held-success/newer-failure cases pass. Preview leaves state unchanged at call time, predicts the exact closed set, and actual audit preserves actor, reason, candidate flag, held count and closed IDs. Two held successes may close the chosen owner; a newer held failure prevents it. Rebind without evidence closes nothing. Second rebind is refused. **Twenty JSON round trips per case** preserve resulting state and audit without duplication.

Candidates are recorded by ordinary PLAN events, not authenticated ownership evidence. `allow_non_candidate=True` remains a deliberate trust override. No production caller exposing `rebind_plan_owner` was found outside its definition/tests/review artifacts. No authentication claim is made. Findings 2 and 3 delimit what the positive preview tests do not establish.

### N10 new-path bounds, totals and warnings

Authentic e6afe16 input with **300** ownerless plans produces a 256-entry diagnostic history, `legacy_ownerless_total=300`, **all 300 quarantine IDs**, 256 candidate-map keys and `owner_candidates_dropped=44`. Twenty current restores preserve these values exactly. Explicitly rebinding all 300 retains the latest 256 audit entries with `owner_rebinds_total=300`; no receipts means all 300 incidents remain open. Twenty further restores retain the audit/totals. The inherited candidate-value check still caps one plan at eight candidates.

The discard counter remains 1 through 20 current restores, then becomes 2 when another legacy discarded receipt is introduced. Obsolete ordinary-PLAN recovery warning text is removed. Residual wording at reducer line 609 names `legacy_ownerless_plans` as if it were current quarantine; after pruning/rebind that is a historical sample. Operational tooling must use **`owner_unproven`**, not that diagnostic list, to enumerate actionable plans. This is guidance ambiguity, not quarantine loss.

### Multi-plan supersession

The observed policy is **any fully verified plan with immutable owner i may close i**, even when another plan owning i has failed. There is no newest-plan check, explicit supersedes relation or cancellation record. Four independent early/late INCIDENT x p/q-complete controls confirm it. A pending incident-only failure ambiguous between multiple owners conservatively blocks completion; explicit linkage plus a fresh retry recovers.

The historical `two_plans_one_incident_failure` assertion wants q retried, while fully verified p now closes i. This policy difference already existed in 7160; it is not a new regression or unsupported closure. Code comments describe retry ownership, but the delta adds no operational supersession specification. Make this policy explicit before treating old contrary expectations as universally obsolete, particularly where old and new repair plans are not interchangeable.

## Exact Test Accounting

| Primary run | Result | True exit / meaning |
|---|---|---|
| Full authored pytest, once | **692 passed, 1 failed / 693 collected** | **1**, only isolated wheel-build dependency provisioning. |
| All 11 new authored tests | **11/11 passed** | Included in that same full invocation. |
| Original expected-bug adversarial | Stops at repaired N3 expectation | 1, preserved unchanged. |
| Corrected adversarial terminal controls | 3/3 | 0. |
| Original `new_cases.py` | 397/398; 384/384 permutations | 1, multi-plan policy difference above. |
| Original `supplementary.py` | 3/4 | 1, foreign prelinked owner expectation correctly refused. |
| Original 7024 schedules combined | **400/402** | Two explained historical-policy differences, not 402 passes. |
| Current arrival-v1 snapshots | **3,072/3,072** | Semantic expectations at eight boundaries. Contains the former 1,920-boundary subset. |
| Authentic 5de0d53 ordered snapshots | **3,072/3,072** | Same overlapping finite schedule family. |
| e6afe16 fail-closed plus fresh | **384/384** | Conservative migration, not lossless legacy equivalence. |
| Authentic opposite-history disk witnesses | 2/2 | Same-byte history ambiguity retained. |
| Old unlinked stale automatic-recovery oracle | 0/3 composite; 3/3 safety | Causes semantic harness exit 1; explicit recovery passes 6/6 separately. |
| Ownership lifecycle / old owners / namespace | 48/48; 6/6; 1/1 | No lifecycle failures remain. |
| New H2 boundary matrix | 51/51 | In `review7173.json`. |
| Retained N8 boundaries | 14/14 | Observation helper exit 0; separately audited assertions. |
| New review groups | 7/10 | Exit 1; the three failures are findings 1-3, not harness crashes. |
| Prior scoped regressions | 14/14 groups plus 2/2 older groups | Both processes exit 0. |
| Independent/public repair/production paths | All assertions pass | 0. |

Original 402 schedules comprise **2,426 per-event states**; ownership lifecycle comprises **276**. Corrected audit finds zero open/step/count/health contradictions. Eleven pre-INCIDENT lifecycle states correctly remain UNKNOWN; an initial audit incorrectly required HEALTHY there and failed. Both audit versions and exits are preserved; correcting that audit required **no test or source rerun**. The unchanged semantic helper's intermediate owner-map references can alias later state; rely on its final ownership assertions and the new deep-copied traces for timing claims.

The foreign-prelink mismatch is `INCIDENT i->p`, but `PLAN p->other`: the obsolete oracle closes both. Immutable owner admission correctly leaves them open. `adaptation.diff` changes only old rebind call signatures, not these assertions. The copied mechanism helper's resolved-target acceptance becomes refusal as intended; its explicit non-candidate overrides are not evidence that default candidate restrictions failed.

## Authored Test Assessment

The delta adds 11 tests in `tests/test_astra7160.py`: four H2, five N9, two N10. They are legitimate additions. Changes in `test_astra7133.py` add actor/reason after an existing candidate proposal. Changes in `test_astra7146.py` deliberately use override because its old fixture has no candidate, and compare old identity fields plus actor/reason in the enlarged audit record. These are legitimate API/policy adaptations, not removal of old safety assertions; the new suite separately tests default candidate denial.

The new [agree helper at line 44](https://github.com/bgoertzel-sing/hive-appliance/blob/cfb03f2aa71e494ed3dd782d6179ed5f1621889b/tests/test_astra7160.py#L44) now compares open IDs, count and named-plan verified/failed sets after each event. **It does not compare health**, despite the module docstring claiming it does. It does not compare pending buffers, ownership maps or all unlisted plans. Older helpers remain narrower. The H2 snapshot test is local-only; the failure test uses already-applicable plan receipts, not a truly buffered failure made eligible at INCIDENT. This review supplies those missing checks.

The synthetic lost-owner fixture removes fields/links from new output. It does not validate old serialization. The N10 test bounds only newly generated histories and one restore, never an oversized ef18db3 snapshot or audit history above 256. The N9 preview test covers valid immutable receipt fields only and checks purity before consuming returned values. These gaps explain why 11 passes coexist with the reproduced findings.

## Full Pytest and Public Repair

Exact command recorded in `pytest-exit.json`:

```text
/usr/bin/python3 -m pytest tests/ -v -p no:cacheprovider \
  --basetemp=.../20260928-astra-7173/pytest-tmp
cwd: .../20260928-astra-7173/source
693 collected; 692 passed, 1 failed in 63.70s
actual child exit 1; timed_out false; wall 64.239s
```

Failure: `tests/test_packaging.py::test_wheel_build`. Saved stderr shows isolated build provisioning attempted `setuptools>=61` and `wheel`; pip reported no matching `setuptools>=61` distribution under recorded `PIP_NO_INDEX=1`. Environment has setuptools 59.6.0. This is observed offline provisioning failure, not an assumed explanation and not a passing build. No package installation, packaging retry or second pytest invocation occurred. A separately provisioned packaging check remains necessary.

`independent.json` exercises actual Appliance, planner/verifier, HiveAppliance and LocalAgentAdapter with a receipt-producing executor double. Success executes `[0,1]`, verifies `[true,true]`, resolves, and ends HEALTHY/0 locally and in hive. Failure verifies `[true,false]`, rolls back, and ends FAILED/1 after ticks. These are public orchestration paths, not just direct reducer calls. They do not establish physical host repair correctness. Older shell rollback probes operate only on temporary files; no live host repair was attempted.

## Reproduction and Limits

The evidence README documents `HIVE_SRC`, required writable `tmp/`, isolated child environments and portable replay. All old reducer modules/helpers needed at runtime are included. The only preparation failure was an absent untracked old socket guard, before pytest started; its true exit is preserved and a new self-contained guard was added. Runtime helpers do not depend on unpublished/colliding 7133 workspace files.

A relocated **probe-only** replay uses the exported source with no Git access or prior workspace imports. Its results are a portability check, not an additional independent schedule count or another full-suite invocation. Primary raw outputs remain unchanged. Final integrity compares pin/worktree/export/helper hashes; `SHA256SUMS` covers retained deliverable evidence and a separate manifest covers the full source export.

Research rules applied: 1 (validate oracles/harnesses), 2 (explicit semantic invariants), 5 (reproducible process/evidence), 7 (public contract checks). Single-reviewer instruction supersedes delegation. Finite event schedules do not prove arbitrary concurrency, malformed-snapshot integrity, operator authentication or physical repair validity. Findings and recommendations are limited accordingly.
