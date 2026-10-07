Model (self-reported): GPT-6 (Codex)

# Astra re-review 7003 — 44aaef8

Date: 2026-09-26. Repository: `bgoertzel-sing/hive-appliance`.
Reviewed pin: `44aaef8aa2c7a5c705601954bd353011d506c6d1`, worktree `repos/hive-astra-7003`.
The model line is self-identification, not gateway provenance. Parent verifies the gateway session record separately.

## Verdict

**Original findings: 10 CLOSED, H2 PARTIAL. N1 and N2 CLOSED for their named defects.** Ordinary public repair now works, distinct-index counting is fixed, and default production attachment admission is rooted/canonical. However, **do not yet trust hive completion under buffered failure/retry streams**: a new independently demonstrated ordering defect can display HEALTHY while a failed step is outstanding. A separate contradictory-identity stream still produces local/hive disagreement.

**Exactly one full pytest invocation: 639 passed, 1 failed, 640 collected; true exit 1.** The only failure is offline wheel-build dependency provisioning (`setuptools>=61` unavailable), not an observed source assertion regression. The claimed 640 passing tests is not reproduced in this environment.

## Findings table

| ID | Status | Observed evidence |
|---|---|---|
| A1 | CLOSED | Prior blocked-worker/concurrent SQLite claim probe: stale publication cannot replace winner's completed row or bytes. |
| A2 | CLOSED | Live partial retained, orphan removed; original reconciliation assertions pass. |
| H1 | CLOSED | Every health-poll state preserves active critical incident; partial composite stays FAILED/1; ordered completion then healthy poll clears count. |
| H2 | **PARTIAL** | Missing PLAN fails closed; normal late PLAN buffers and deduplicates correctly; boolean indices rejected. But buffered successful evidence followed by failed evidence can close hive before the buffer is fully applied (N3 below). |
| U1 | CLOSED | Checkpoint create/readback failures block execution; rollback load failures remain durable; successful metadata restoration preserved. |
| U2 | CLOSED | Prior bounded real-shell rollback probes, newest-first order, missing/failing rollback flags, metadata and CLI checks pass. |
| U3 | CLOSED | Prior checkpoint incident/dedup/composite roundtrip passes; new pending-receipt JSON snapshot roundtrip also passes. |
| L1 | CLOSED | Timeout retains live worker and stop signal; replacement refused; eventual restart and normal worker pass. |
| S1 | CLOSED | Terminal-state validation and direct-SQL invalid-state rejection pass. |
| P1-symlink | CLOSED | Planted root symlink rejects both main/thumbnail paths without external creation. |
| P2-store | CLOSED | Default and custom-folder production client stores use manager root; relative, traversal and both external symlink forms rejected; accepted paths canonicalized; download/delete preserve outside sentinel. |
| N1 | CLOSED | Real `Appliance.repair()`, unlinked recorded incident, SimplePlanner and successful two-step in-memory executor: local 0, hive HEALTHY/0. Failed second step leaves local and hive FAILED/1. |
| N2 | CLOSED | Distinct indices required locally; duplicate step 0 cannot complete; invalid indices rejected; verified retry clears failed index; snapshot preserves identities and legacy booleans cannot count. |

CLOSED is bounded to named defects and executed schedules, not general subsystem certification. H1's closure does not negate N3: N3 incorrectly marks the incident resolved before health recomputation.

## Independent reducer schedules

[`independent.py`](../experiments/20260926-astra-7003/independent.py) and [`independent.json`](../experiments/20260926-astra-7003/independent.json) run identical Event objects through local and hive reducers, asserting agreement after **every** event:

- INCIDENT → receipt 0 → receipt 1 → replay 0 → PLAN(2) → replay 0 → replay 1 → replay PLAN gives counts **1,1,1,1,0,0,0,0**, exactly one open-to-resolved transition. Seen receipt sets each contain two IDs.
- INCIDENT → receipt 0 → PLAN(2) → receipt 1 gives **1,1,1,0**.
- PLAN followed by distinct receipt IDs for step 0 twice stays open until step 1.
- True, False, -1, 2, string `"1"`, float `1.0`, and null indices cannot count for a two-step plan; valid 0 and 1 subsequently resolve.
- Failed 0 → verified 1 → verified retry 0 resolves only on retry; replaying the original failure is ignored.
- Local snapshot roundtrip while both receipts are buffered, then PLAN, resolves once and agrees with uninterrupted hive. Partial-progress snapshot followed by duplicate index remains open. Hive has no corresponding snapshot API tested here.
- A local legacy snapshot with `plan_receipts={'p':[True,True]}` discards that completion evidence; fresh verified 0 alone stays open, then fresh verified 1 resolves. This tests unresolved legacy state, not retroactive reopening of already-resolved legacy incidents.

### N3 — buffered failure can be ignored by final hive incident state (High, newly demonstrated)

**Observation:** [`adversarial.py`](../experiments/20260926-astra-7003/adversarial.py), `buffered_failure_after_verified`:

```text
INCIDENT i (unlinked)
receipt r0: plan p, step 0, verified true
receipt r1: plan p, step 1, verified true
receipt rf: plan p, step 0, verified false
PLAN p: incident i, two steps
```

Both remain open before PLAN. After PLAN, **local open=1, hive open=0**. Both reducers' failed-step sets contain index 0. A subsequent fresh verified retry of 0 brings local to zero too, proving the missing retry matters.

**Source-backed explanation:** `hive/reducer.py::_handle_plan` replays buffered receipts through `_handle_receipt`, which calls `_maybe_resolve_plan` for each receipt. Processing r1 closes the incident before rf is applied. Failure tracking then updates but does not reopen it. Local reduction applies its entire buffer before `_maybe_resolve`, correctly staying open.

**Assessment:** High for authoritative hive completion: all delivered evidence is present yet final incident state contradicts outstanding failure. This is an event-schedule reproduction, not proof that the ordered LocalAgentAdapter transport normally generates this schedule. It keeps H2 PARTIAL. Fix by applying an entire newly eligible buffer before publishing completion, with explicit retry/terminal semantics.

### N4 — contradictory incident identity counted locally (Medium, newly demonstrated; introduction unproven)

**Observation:** two incidents i and other are linked to separate registered plans p(two steps) and q(one step). After valid p/0, a verified receipt with `plan_id=p, incident_id=other, step_index=1` closes i locally. Hive rejects the contradiction. Final open counts: **local=1, hive=2** (`adversarial.json:contradictory_incident_identity`).

**Source-backed explanation:** local `_apply_receipt` validates index/verification, not payload incident identity. Hive checks contradictory identity before updating progress. Normal Receipt objects need not carry incident_id; this reproduction uses Event payloads, which both reducers accept.

**Assessment:** Medium identity/authority mismatch; no demonstrated production injector or downstream damage. Do not claim it was introduced by this commit: no baseline execution for N4 was performed. It is separate from N2's now-fixed duplicate-index defect. Define and enforce one identity contract in both reducers.

## N1 public repair and P2 production wiring

The public-repair probe uses real Appliance, SimplePlanner, ExitCodeVerifier, HiveAppliance and LocalAgentAdapter. The executor only constructs receipts and records indices: **no host commands**. Both successful and failed runs execute indices [0,1]; the incident has no preset plan id. Success receipts verify and outcome is `resolved`; failure leaves an open incident after recovery. Two hive ticks after repair confirm displayed health/count, not merely internal receipt state. This closes the record-only test caveat.

P2 uses real MessageStore plus default ConversationStoreClient wiring, with only the semantic index stubbed. It is repeated with an explicitly supplied folder manager. Real parent Message rows satisfy production foreign-key requirements. Absolute outside, absolute `../` escape, relative inside-looking path, relative escape, in-root→outside symlink and outside→root symlink all reject. Retargeting the rejected outside symlink cannot alter any saved row. An accepted in-root→in-root symlink persists its resolved target; `sub/../x` persists root/x. update_status also persists a normalized path. After chdir outside, admitted paths remain contained; real download-manager processing succeeds using an in-memory writer and store deletion leaves outside sentinel bytes untouched.

The separately rerun prior rooted-store probe checks append, update_status and finish_attempt reject external paths, including dangling external symlinks, and records rejected finish leaves the downloading row unchanged. Prior legacy-unrooted-row download/delete containment probes also pass. Explicitly constructed unrooted stores remain permissive by design; this is not the default production client anymore. Concurrent filesystem symlink races and every possible external path consumer are not certified by these probes.

## Three older test files changed

Actual diff: [`modified-tests.diff`](../experiments/20260926-astra-7003/modified-tests.diff).

- `test_reducer.py`: adds known one-step PLAN and index 0 before resolution; existing open→closed assertion retained.
- `test_hive_reducer.py`: adds registered PLAN and receipt index; health and incident assertions retained.
- `test_h1_h2_astra6882.py`: adds PLAN helper/registration and default step index for targeted/replay/resolved-health cases. Replay must still leave the other incident open; failure must still stay open; healthy polling after genuine resolution remains asserted.

**Legitimate contract updates, not weakened assertions.** Known PLAN metadata is now intentionally required. Their limitation is missing adverse buffered success→failure coverage and broad identity-agreement coverage. New test `test_n1_appliance_record_flow...` indeed does not invoke repair; this review supplies that missing end-to-end evidence. All affected tests and all 16 new tests pass in the single full suite.

## Execution evidence and limits

Evidence directory: [20260926-astra-7003](../experiments/20260926-astra-7003/).

- Prior 6986 regression harness copied with provenance retained, pin changed and active CASES restricted to the nine previously closed findings plus containment effects: **14/14 groups pass**, exit 0 (`probes-result.json`, stdout/stderr). Additional rooted-all-mutators group passes (`p2-mutators.json`). Historical unused functions still exist in the copied file and are not executed.
- Independent harness exit 0; adversarial harness exits 0 while intentionally asserting both counterexamples. PASS therefore means the expected observation held, not universal product correctness.
- Three initial independent-harness fixture errors were corrected: Severity enum, missing parent directories, and missing production parent Message. Their stderr is retained as `independent-first/second/third.stderr`. No production edits were needed. These were not pytest invocations.
- Full suite run **once**, on a tracked-source export under evidence to contain packaging outputs. Exact argv: `/usr/bin/python3 -m pytest tests/ -v -p no:cacheprovider --basetemp=<evidence>/pytest-tmp`. `pytest-result.json` records subprocess wait result **1**, no timeout, 29.39 seconds; stdout reports 639 passed/1 failed in 29.05 seconds.
- `pytest.stdout` and `pytest.stderr` preserve output. Only `tests/test_packaging.py::test_wheel_build` fails because isolated pip cannot find `setuptools>=61` with `PIP_NO_INDEX=1`. No dependency installs/retries were performed. Offline Python socket guard inherited from prior review; it is not an OS sandbox.
- `environment.json`, `source-sha256.json`, and `verification.json` record pin, versions and unchanged tracked source. No production source edits, pushes, or live service mutations. Only this review document and exclusive evidence were authored.

## Prioritized remaining fixes

1. **P0: fix N3**, replay eligible buffered evidence atomically with respect to resolution; add identical-stream success0/success1/failure0/PLAN and retry coverage.
2. **P1: fix N4**, align contradictory incident/plan identity handling before counting local evidence; expand agreement tests beyond duplicate indices.
3. **P2: qualify wheel build separately** with pre-provisioned approved build dependencies; current offline result cannot certify packaging.
4. Preserve the now-passing public repair, rooted production client, snapshot, rollback and nine original regression checks.

Model (self-reported): GPT-6 (Codex)
